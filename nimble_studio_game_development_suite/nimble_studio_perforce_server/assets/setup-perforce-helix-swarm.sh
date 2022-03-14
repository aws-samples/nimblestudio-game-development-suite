#!/bin/bash

set -eux -o pipefail

# Handle cfn-signal missing
if ! command -v cfn-signal &> /dev/null
then
    echo "cfn-signal could not be found. Attempting install."
    pip3 install "https://s3.amazonaws.com/cloudformation-examples/aws-cfn-bootstrap-py3-latest.tar.gz"
fi

trap 'catch $? $LINENO' ERR

catch() {
    echo ""
    echo "ERROR CAUGHT!"
    echo ""
    echo "Error code $1 occurred on line $2"
    echo ""
    cfn-signal --stack STACK_NAME_PLACEHOLDER --resource RESOURCE_LOGICAL_ID_PLACEHOLDER --region REGION_PLACEHOLDER --exit-code $1
    exit $1
}

export HOST=$(echo "STAGE_PLACEHOLDER-swarm-p4" | tr _ -)
hostname "$HOST"

# Remove AWS cli version 1 and install version 2
yum -y remove awscli
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "/tmp/awscliv2.zip"
unzip /tmp/awscliv2.zip -d /tmp
/tmp/aws/install
export PATH=$PATH:/opt/perforce/bin/

# During Swarm installation this file gets populated with this server's hostname
# /opt/perforce/etc/swarm-cron-hosts.conf\
# To work around this issue, add the ServerID into /etc/hosts
echo "127.0.0.1 $HOST" >> /etc/hosts

# By the time swarm comes up we know P4D is up. Generate a P4D ticket so that pre/post userdata can run p4 commands
export P4PORT="ssl:PERFORCE_SERVER_DNS_RECORD_PLACEHOLDER:1666"
export P4USER="perforce"
export P4TRUST=/root/.p4trust
export P4TICKETS=/root/.p4tickets
/opt/perforce/bin/p4 trust -y -f

TOKEN=$(curl -X PUT http://169.254.169.254/latest/api/token -H X-aws-ec2-metadata-token-ttl-seconds:60)
export SWARM_INSTANCE_ID=$(curl http://169.254.169.254/latest/meta-data/instance-id -H X-aws-ec2-metadata-token:$TOKEN)
export SWARM_USER="swarm"
export SWARM_GROUP="swarm"
export SWARM_PORT="80"
export P4D_SUPER_USER="perforce"
export P4D_HOST="ssl:PERFORCE_SERVER_DNS_RECORD_PLACEHOLDER"
export P4D_PORT="1666"
export SWARM_EMAIL_HOST="localhost"
export SWARM_ADDITIONAL_ARGS=""

# Retrieve password from secrets manager
export P4D_SUPER_USER_PASSWORD=$(/usr/local/bin/aws secretsmanager get-secret-value --secret-id SECRET_ARN_PLACEHOLDER --query SecretString --output text)

export P4PASSWD=$(echo "$P4D_SUPER_USER_PASSWORD" | /opt/perforce/bin/p4 login -a -p | grep -v "Enter")

mkdir -p /tmp/depots/
cd /tmp/depots/

cat <<EOF > /tmp/swarm-client.cfg
Client: swarm
Owner: perforce
Description:
        Created by perforce.
Root: /tmp/depots/esp-config
Options: noallwrite noclobber nocompress unlocked nomodtime normdir
SubmitOptions:  submitunchanged
LineEnd: local
View:
        //esp-config/... //swarm/...
EOF

cat /tmp/swarm-client.cfg | /opt/perforce/bin/p4 client -i

export P4CLIENT="swarm"

/opt/perforce/bin/p4 sync -f
export SWARM_TOKEN=$(cat /tmp/depots/esp-config/swarm.token)
export SWARM_ADMIN_PASSWORD="$(cat /tmp/depots/esp-config/swarm.password)"

_USERS=$(/opt/perforce/bin/p4 users -a)

if [[ $_USERS == *"Swarm Admin"* ]]; then
    echo "Swarm user exists...this is a restore from backup"
    /opt/perforce/swarm/sbin/configure-swarm.sh --non-interactive --swarm-port $SWARM_PORT --create-group $SWARM_GROUP --swarm-user $SWARM_USER --swarm-passwd $SWARM_ADMIN_PASSWORD --super-user $P4D_SUPER_USER --super-passwd $P4D_SUPER_USER_PASSWORD --p4port $P4D_HOST:$P4D_PORT --email-host $SWARM_EMAIL_HOST $SWARM_ADDITIONAL_ARGS
else
    echo "Swarm user does not exist, creating Swarm user during Swarm installation..."
    /opt/perforce/swarm/sbin/configure-swarm.sh --non-interactive --swarm-port $SWARM_PORT --create swarm --create-group $SWARM_GROUP --swarm-user $SWARM_USER --swarm-passwd $SWARM_ADMIN_PASSWORD --super-user $P4D_SUPER_USER --super-passwd $P4D_SUPER_USER_PASSWORD --p4port $P4D_HOST:$P4D_PORT --email-host $SWARM_EMAIL_HOST $SWARM_ADDITIONAL_ARGS
fi


# Create triggers in P4D
cat <<-EOF > /tmp/triggers.cfg
Triggers:
    swarm.job form-commit job "%quote%/opt/perforce/swarm-triggers/bin/swarm-trigger.pl%quote% -t job -v %formname%"
    swarm.user form-commit user "%quote%/opt/perforce/swarm-triggers/bin/swarm-trigger.pl%quote% -t user -v %formname%"
    swarm.userdel form-delete user "%quote%/opt/perforce/swarm-triggers/bin/swarm-trigger.pl%quote% -t userdel -v %formname%"
    swarm.group form-commit group "%quote%/opt/perforce/swarm-triggers/bin/swarm-trigger.pl%quote% -t group -v %formname%"
    swarm.groupdel form-delete group "%quote%/opt/perforce/swarm-triggers/bin/swarm-trigger.pl%quote% -t groupdel -v %formname%"
    swarm.changesave form-save change "%quote%/opt/perforce/swarm-triggers/bin/swarm-trigger.pl%quote% -t changesave -v %formname%"
    swarm.shelve shelve-commit //... "%quote%/opt/perforce/swarm-triggers/bin/swarm-trigger.pl%quote% -t shelve -v %change%"
    swarm.commit change-commit //... "%quote%/opt/perforce/swarm-triggers/bin/swarm-trigger.pl%quote% -t commit -v %change%"
    swarm.shelvedel shelve-delete //... "%quote%/opt/perforce/swarm-triggers/bin/swarm-trigger.pl%quote% -t shelvedel -v %change% -w %client% -u %user% -d %quote%%clientcwd%^^^%quote% -a %quote%%argsQuoted%%quote% -s %quote%%serverVersion%%quote%"
    swarm.enforce change-submit //... "%quote%/opt/perforce/swarm-triggers/bin/swarm-trigger.pl%quote% -t checkenforced -v %change% -u %user%"
    swarm.strict change-content //... "%quote%/opt/perforce/swarm-triggers/bin/swarm-trigger.pl%quote% -t checkstrict -v %change% -u %user%"
    swarm.shelvesub shelve-submit //... "%quote%/opt/perforce/swarm-triggers/bin/swarm-trigger.pl%quote% -t checkshelve -v %change% -u %user%"
EOF
 
cat /tmp/triggers.cfg | /opt/perforce/bin/p4 triggers -i
rm /tmp/triggers.cfg

# Create a swarm token that can be used from p4d triggers
# TODO: Swarm does NOT create a token P4D can use until a user logins AND clicks on their profile icon and About Swarm
# Work around this by pre creating the expected dir structure and pre create a token P4D is expecting to use
mkdir -p /opt/perforce/swarm/data/queue/tokens/
touch /opt/perforce/swarm/data/queue/tokens/$SWARM_TOKEN
chown -R apache:apache /opt/perforce/swarm/data/queue

/opt/perforce/bin/p4 -p "ssl:PERFORCE_SERVER_DNS_RECORD_PLACEHOLDER:1666" property -a -n P4.Swarm.URL -v "http://PERFORCE_SWARM_DNS_RECORD_PLACEHOLDER:$SWARM_PORT"

cfn-signal --stack STACK_NAME_PLACEHOLDER --resource RESOURCE_LOGICAL_ID_PLACEHOLDER --region REGION_PLACEHOLDER
