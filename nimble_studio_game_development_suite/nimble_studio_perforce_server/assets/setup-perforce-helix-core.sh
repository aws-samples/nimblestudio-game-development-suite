#!/bin/bash
## Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
## SPDX-License-Identifier: MIT-0

# Script derived from
# https://github.com/aws-samples/game-production-in-the-cloud-example-pipeline/blob/main/assets/setup-perforce-helix-core.sh

# stop ssm agent if active to prevent interruptions from patching 
systemctl is-active --quiet amazon-ssm-agent && systemctl stop amazon-ssm-agent && echo ssm service stopped

set -eux -o pipefail

trap 'catch $? $LINENO' ERR

catch() {
  echo ""
  echo "ERROR CAUGHT!"
  echo ""
  echo "Error code $1 occurred on line $2"
  echo ""
  /opt/aws/bin/cfn-signal --stack STACK_NAME_PLACEHOLDER --resource RESOURCE_LOGICAL_ID_PLACEHOLDER --region REGION_PLACEHOLDER --exit-code $1 
  exit $1
}

# Add Perforce YUM repository and install Perforce
cat <<'EOF' >> /etc/yum.repos.d/perforce.repo
[perforce]
name=Perforce
baseurl=https://package.perforce.com/yum/rhel/7/x86_64/
enabled=1
gpgcheck=1
EOF

chown root:root /etc/yum.repos.d/perforce.repo
chmod 0644 /etc/yum.repos.d/perforce.repo

rpm --import https://package.perforce.com/perforce.pubkey

yum upgrade -y                        
yum install -y amazon-efs-utils helix-p4d helix-swarm-triggers uuid perl-Digest-MD5 perl-Sys-Syslog perl-JSON mailx

# Remove AWS cli version 1 and install version 2
yum -y remove awscli

curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "/tmp/awscliv2.zip" 
unzip /tmp/awscliv2.zip -d /tmp
/tmp/aws/install

# Mount EFS
efs_mount_point_1=/hxdepots
mkdir -p ${efs_mount_point_1}
mount -t efs -o tls fs-${FILESYSTEMID}:/ ${efs_mount_point_1}

# Modify /etc/fstab to mount device when booting up
echo "fs-${FILESYSTEMID}:/ ${efs_mount_point_1} efs defaults,_netdev 0 0" >> /etc/fstab

# Create filesystem on each of the block devices and mount them
mkfs -t xfs /dev/sdc && mkdir /hxlogs && mount /dev/sdc /hxlogs
mkfs -t xfs /dev/sdd && mkdir /hxmetadata && mount /dev/sdd /hxmetadata

# Modify /etc/fstab to mount device when booting up
blkid /dev/sdc | awk -v OFS="   " '{print $2,"/hxlogs","xfs","defaults,nofail","0","2"}' >> /etc/fstab
blkid /dev/sdd | awk -v OFS="   " '{print $2,"/hxmetadata","xfs","defaults,nofail","0","2"}' >> /etc/fstab

# Create P4admin user
adduser -g perforce -G adm,wheel p4admin

# Download an untar SDP
wget -O /tmp/sdp.tgz https://swarm.workshop.perforce.com/downloads/guest/perforce_software/sdp/downloads/sdp.Unix.tgz?v=%2314

tar xvfz /tmp/sdp.tgz --directory /hxdepots

# Modify mkdirs.cfg
cp /hxdepots/sdp/Server/Unix/setup/mkdirs.cfg /hxdepots/sdp/Server/Unix/setup/mkdirs.cfg.bak

INSTANCE_PRIVATE_DNS_NAME=$(hostname)

sed -i -e 's/DB1=.*/DB1=hxmetadata/g' /hxdepots/sdp/Server/Unix/setup/mkdirs.cfg
sed -i -e 's/DB2=.*/DB2=hxmetadata/g' /hxdepots/sdp/Server/Unix/setup/mkdirs.cfg
sed -i -e 's/DD=.*/DD=hxdepots/g' /hxdepots/sdp/Server/Unix/setup/mkdirs.cfg
sed -i -e 's/LG=.*/LG=hxlogs/g' /hxdepots/sdp/Server/Unix/setup/mkdirs.cfg
sed -i -e 's/OSUSER=.*/OSUSER=p4admin/g' /hxdepots/sdp/Server/Unix/setup/mkdirs.cfg
sed -i -e 's/OSGROUP=.*/OSGROUP=perforce/g' /hxdepots/sdp/Server/Unix/setup/mkdirs.cfg
sed -i -e 's/CASE_SENSITIVE=.*/CASE_SENSITIVE=0/g' /hxdepots/sdp/Server/Unix/setup/mkdirs.cfg
sed -i -e 's/MAILHOST=.*/MAILHOST=localhost/g' /hxdepots/sdp/Server/Unix/setup/mkdirs.cfg
sed -i -e 's/SSL_PREFIX=.*/SSL_PREFIX=ssl:/g' /hxdepots/sdp/Server/Unix/setup/mkdirs.cfg
sed -i -e "s/P4DNSNAME=.*/P4DNSNAME=$INSTANCE_PRIVATE_DNS_NAME/g" /hxdepots/sdp/Server/Unix/setup/mkdirs.cfg
sed -i -e 's/COMPLAINFROM_DOMAIN=.*/COMPLAINFROM_DOMAIN=amazonaws.com/g' /hxdepots/sdp/Server/Unix/setup/mkdirs.cfg

# Create symlinks
ln -s /opt/perforce/bin/p4 /hxdepots/sdp/Server/Unix/p4/common/bin/p4
ln -s /opt/perforce/sbin/p4d /hxdepots/sdp/Server/Unix/p4/common/bin/p4d

# Run SDP
/hxdepots/sdp/Server/Unix/setup/mkdirs.sh 1

# Add systemd configuration file for Perforce Helix Code
cat <<'EOF' >> /etc/systemd/system/p4d_1.service
[Unit]
Description=Helix Server Instance 1
Documentation=https://www.perforce.com/perforce/doc.current/manuals/p4sag/index.html
Requires=network.target network-online.target
After=network.target network-online.target
[Service]
Type=forking
TimeoutStartSec=60s
TimeoutStopSec=60s
ExecStart=/p4/1/bin/p4d_1_init start
ExecStop=/p4/1/bin/p4d_1_init stop
User=p4admin
[Install]
WantedBy=multi-user.target
EOF

chown p4admin:perforce /etc/systemd/system/p4d_1.service
chmod 0400 /etc/systemd/system/p4d_1.service

# Enable and start the Perforce Helix Code daemon
systemctl enable p4d_1
systemctl start p4d_1

# Persist ServerID
echo SERVER_ID_PLACEHOLDER > /p4/1/root/server.id

export P4PORT=LOCAL_P4_PORT_PLACEHOLDER

# Generate Cert
/p4/common/bin/p4master_run 1 /p4/1/bin/p4d_1 -Gc

# Configure Server
/hxdepots/sdp/Server/setup/configure_new_server.sh 1

# Load Perforce environment variables, set the password persisted in the AWS Secrets Manager and put security measaurements in place
source /p4/common/bin/p4_vars 1

p4 configure set dm.password.minlength=32
p4 configure set dm.user.noautocreate=2
p4 configure set run.users.authorize=1
p4 configure set dm.keys.hide=2
p4 configure set security=3

perforce_default_password=$(/usr/local/bin/aws secretsmanager get-secret-value --secret-id PERFORCE_PASSWORD_ARN_PLACEHOLDER --query SecretString --output text)

# p4 passwd -P is not supported w/ security level set to 3 (See above)
echo -en "$perforce_default_password\n$perforce_default_password\n" | p4 passwd

# Configure password and protection

sudo -i -u perforce p4 -p LOCAL_P4_PORT_PLACEHOLDER trust -y
echo -en "$perforce_default_password" | sudo -i -u perforce p4 -p LOCAL_P4_PORT_PLACEHOLDER login

cat <<EOF > /tmp/protection-table.txt
Protections:
        write user * * //...
        super user perforce * //...
EOF

cat /tmp/protection-table.txt | sudo -i -u perforce p4 -p LOCAL_P4_PORT_PLACEHOLDER protect -i

sudo -i -u perforce p4 -p LOCAL_P4_PORT_PLACEHOLDER configure set net.parallel.max=50

# Creating a swarm token
mkdir -p /tmp/depots/esp-config
chown -R perforce:perforce /tmp/depots
cd /tmp/depots/esp-config/

cat <<EOF > /tmp/esp-config.cfg
Depot:  esp-config
Owner:  perforce
Date:   2021/05/07 20:14:18
Description:
    Created by perforce.
Type:   local
Address:        local
Suffix: .p4s
StreamDepth:    //esp-config/1
Map:    esp-config/...
EOF

cat /tmp/esp-config.cfg | sudo -i -u perforce p4 -p LOCAL_P4_PORT_PLACEHOLDER depot -i

cat <<EOF > /tmp/helix-core-client.cfg
Client: helix-core
Owner:  perforce
Description:
        Created by perforce.
Root:   /tmp/depots/esp-config
Options:        noallwrite noclobber nocompress unlocked nomodtime normdir
SubmitOptions:  submitunchanged
LineEnd:        local
View:
        //esp-config/... //helix-core/...
EOF

cat /tmp/helix-core-client.cfg | sudo -i -u perforce p4 -p LOCAL_P4_PORT_PLACEHOLDER client -i

# If this is a restore the swarm.token file may already exist
sudo P4CLIENT="helix-core" -i -u perforce p4 -p LOCAL_P4_PORT_PLACEHOLDER sync -f

# swarm.token allows trigger on p4d to authenticate to swarm
export SWARM_TOKEN_FILE="/tmp/depots/esp-config/swarm.token"
# swarm.password is the password for the swarm user in p4d
export SWARM_USER_PASSWORD_FILE="/tmp/depots/esp-config/swarm.password"
if [[ -f "$SWARM_TOKEN_FILE" ]]; then
    echo "Swarm token file does exist"
    export SWARM_TOKEN=$(cat $SWARM_TOKEN_FILE)
else
    echo "Swarm token file does not exist, creating one now..."
        export SWARM_TOKEN=$(uuid)
        echo $SWARM_TOKEN > $SWARM_TOKEN_FILE

    # Pre create a password for the swarm user
    # We do this so that if we ever restore from a backup the new swarm instance can come up and find the original password
    uuid > $SWARM_USER_PASSWORD_FILE

        sudo P4CLIENT="helix-core" -i -u perforce p4 -p LOCAL_P4_PORT_PLACEHOLDER add /tmp/depots/esp-config/*
        chown -R perforce:perforce /tmp/depots/
        sudo P4CLIENT="helix-core" -i -u perforce p4 -p LOCAL_P4_PORT_PLACEHOLDER submit -d "Adding swarm token and password"
fi

mkdir -p /opt/perforce/etc
cat <<-EOF > /opt/perforce/etc/swarm-trigger.conf
SWARM_HOST='http://SWARM_IP_PLACEHOLDER'
SWARM_TOKEN='$SWARM_TOKEN'
ADMIN_USER=''
ADMIN_TICKET_FILE=''
P4_PORT=''
P4='p4'
EXEMPT_FILE_COUNT=0
EXEMPT_EXTENSIONS=''
VERIFY_SSL=0
TIMEOUT=30
IGNORE_TIMEOUT=0
IGNORE_NOSERVER=0
EOF

# SNS_ALERT_TOPIC
cat <<-EOF >> /p4/common/config/p4_1.vars

# SNS Alert Configurations
# Two methods of authentication are supported: key pair (on prem, azure, etc) and IAM role (AWS deployment)
# In the case of IAM role the AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY environment variables must not be set, not even empty strings

# To test SNS delivery use the following command: aws sns publish --topic-arn SNS_ALERT_TOPIC_ARN --subject test --message "this is a test"

# export AWS_ACCESS_KEY_ID=""
# export AWS_SECRET_ACCESS_KEY=""

export AWS_DEFAULT_REGION="REGION_PLACEHOLDER"
export SNS_ALERT_TOPIC_ARN="SNS_ALERT_TOPIC_ARN_PLACEHOLDER"

EOF

systemctl start amazon-ssm-agent
/opt/aws/bin/cfn-signal --stack STACK_NAME_PLACEHOLDER --resource RESOURCE_LOGICAL_ID_PLACEHOLDER --region REGION_PLACEHOLDER
