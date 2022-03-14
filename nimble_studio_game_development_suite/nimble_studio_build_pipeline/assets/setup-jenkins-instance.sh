#!/usr/bin/env bash
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

yum update -y
yum install -y python3 java-11-amazon-corretto-headless
pip3 install boto3

alternatives --install /usr/bin/java java /usr/lib/jvm/java-11-amazon-corretto.x86_64/bin/java 20000
update-alternatives --auto java
java -version
amazon-linux-extras install epel -y

# Remove AWS cli version 1 and install version 2
yum -y remove awscli

curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "/tmp/awscliv2.zip" 
unzip /tmp/awscliv2.zip -d /tmp
/tmp/aws/install

# Add Jenkins YUM repository
cat <<'EOF' >> /etc/yum.repos.d/jenkins.repo
[jenkins]
name=Jenkins-stable
baseurl=https://pkg.jenkins.io/redhat-stable
enabled=1
gpgcheck=1
EOF

rpm --import https://pkg.jenkins.io/redhat-stable/jenkins.io.key
yum upgrade -y
yum install -y jenkins
rpm -qa | grep jenkins
JENKINS_HOME="/var/lib/jenkins/"

# Configure Jenkins service
mkdir -p /etc/systemd/system/jenkins.service.d
touch /etc/systemd/system/jenkins.service.d/override.conf
cat <<'EOF' > /etc/systemd/system/jenkins.service.d/override.conf
[Service]
Environment="JENKINS_PORT=80"
User=root
EOF

systemctl enable jenkins
systemctl start jenkins

/opt/aws/bin/cfn-signal --stack STACK_NAME_PLACEHOLDER --resource RESOURCE_LOGICAL_ID_PLACEHOLDER --region REGION_PLACEHOLDER
