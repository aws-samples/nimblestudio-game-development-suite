from aws_cdk import Duration, Tags, Stack, aws_ec2 as ec2, aws_iam as iam, aws_s3 as s3
from constructs import Construct
import sys

sys.path.append("../../utils")
from utils.utils import (
    create_ssm_policy,
    replace_user_data_values,
)


class JenkinsPattern(Construct):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        stack_name: str,
        region: str,
        studio_vpc: ec2.IVpc,
        subnet: ec2.ISubnet,
        key_name: str,
        security_group: ec2.SecurityGroup,
        allow_access_from: list[ec2.IPeer],
        build_node_security_group: ec2.ISecurityGroup,
        ssm_logging_bucket: s3.IBucket,
        **kwargs,
    ) -> None:

        super().__init__(scope, construct_id, **kwargs)

        self.jenkins_security_group: ec2.SecurityGroup = security_group

        peer: ec2.IPeer
        for peer in allow_access_from:
            self.jenkins_security_group.add_ingress_rule(
                peer=peer,
                connection=ec2.Port.tcp(80),
                description="Allow access to Jenkins SG port 80",
            )
            self.jenkins_security_group.add_ingress_rule(
                peer=peer,
                connection=ec2.Port.tcp(443),
                description="Allow access to Jenkins SG port 443",
            )

        # For build nodes
        for port in [80, 443, 50000]:
            self.jenkins_security_group.add_ingress_rule(
                peer=build_node_security_group,
                connection=ec2.Port.tcp(port),
                description=f"Allow access to Jenkins SG port {port}",
            )

        self.jenkins_role: iam.IRole = iam.Role(
            self, "JenkinsRole", assumed_by=iam.ServicePrincipal("ec2.amazonaws.com")
        )

        self.jenkins_role.attach_inline_policy(
            create_ssm_policy(self, ssm_logging_bucket)
        )
        self.jenkins_role.add_managed_policy(
            iam.ManagedPolicy.from_managed_policy_arn(
                self,
                "SSMManagedInstanceManagedPolicy",
                "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore",
            )
        )

        instance_type: ec2.InstanceType = ec2.InstanceType.of(
            ec2.InstanceClass.MEMORY5, ec2.InstanceSize.XLARGE
        )

        machine_image: ec2.MachineImage = ec2.MachineImage.latest_amazon_linux(
            generation=ec2.AmazonLinuxGeneration.AMAZON_LINUX_2
        )

        jenkins_block_device: ec2.BlockDevice = ec2.BlockDevice(
            device_name="/dev/sda1",
            volume=ec2.BlockDeviceVolume(
                ebs_device=ec2.EbsDeviceProps(
                    volume_size=30, volume_type=ec2.EbsDeviceVolumeType.GP3
                )
            ),
        )

        self.instance: ec2.IInstance = ec2.Instance(
            self,
            "JenkinsInstance",
            resource_signal_timeout=Duration.minutes(15),
            vpc=studio_vpc,
            vpc_subnets=ec2.SubnetSelection(subnets=[subnet]),
            instance_type=instance_type,
            machine_image=machine_image,
            role=self.jenkins_role,
            block_devices=[jenkins_block_device],
            security_group=self.jenkins_security_group,
            key_name=key_name,
        )

        jenkins_instance_logical_id = Stack.of(self).get_logical_id(
            self.instance.node.default_child
        )

        # Read UserData Script and replace placeholders
        with open("assets/setup-jenkins-instance.sh", "r") as user_data_file:
            user_data = user_data_file.read()

        user_data_replacement_map = {
            "STACK_NAME_PLACEHOLDER": stack_name,
            "RESOURCE_LOGICAL_ID_PLACEHOLDER": jenkins_instance_logical_id,
            "REGION_PLACEHOLDER": region,
        }
        user_data = replace_user_data_values(
            user_data=user_data, replacement_map=user_data_replacement_map
        )
        self.instance.add_user_data(user_data)

        Tags.of(self.instance).add("Name", "Jenkins")
