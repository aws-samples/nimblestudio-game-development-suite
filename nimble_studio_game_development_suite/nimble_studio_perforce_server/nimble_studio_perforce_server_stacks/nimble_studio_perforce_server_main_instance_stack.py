from aws_cdk import (
    Duration,
    NestedStack,
    Tags,
    aws_ec2 as ec2,
    aws_iam as iam,
    aws_route53 as r53,
    aws_secretsmanager as secretsmanager,
    aws_efs as efs,
)
from constructs import Construct

from nimble_studio_perforce_server_stacks.nimble_studio_perforce_server_common_stack import (
    NimbleStudioPerforceServerCommonStack,
    PERFORCE_SERVER_RECORD_PREFIX,
    PERFORCE_SWARM_RECORD_PREFIX,
)
import sys

sys.path.append("../../utils")
from utils.utils import replace_user_data_values


class NimbleStudioPerforceServerMainInstanceStack(
    NimbleStudioPerforceServerCommonStack
):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        security_group: ec2.ISecurityGroup,
        ec2_role: iam.IRole,
        secret: secretsmanager.ISecret,
        sns_topic_arn: str,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Setup logs volume

        log_block_device = ec2.BlockDevice(
            device_name="/dev/sdc",
            volume=ec2.BlockDeviceVolume.ebs(
                volume_type=ec2.EbsDeviceVolumeType.GP3,
                volume_size=128,
                delete_on_termination=True,
            ),
        )

        # Setup depot efs volume
        depot_filesystem = efs.FileSystem(
            self,
            "EFS-Perforce-Depots",
            vpc=self._vpc,
            lifecycle_policy=efs.LifecyclePolicy.AFTER_14_DAYS,  # files are not transitioned to infrequent access (IA) storage by default
            performance_mode=efs.PerformanceMode.GENERAL_PURPOSE,  # default
            out_of_infrequent_access_policy=efs.OutOfInfrequentAccessPolicy.AFTER_1_ACCESS,
        )

        # Setup metadata volume
        metadata_block_device = ec2.BlockDevice(
            device_name="/dev/sdd",
            volume=ec2.BlockDeviceVolume.ebs(
                volume_type=ec2.EbsDeviceVolumeType.GP3,
                volume_size=64,
                delete_on_termination=True,
            ),
        )

        # Lookup latest Amazon Linux2 AMI
        linux_image = ec2.MachineImage.latest_amazon_linux(
            generation=ec2.AmazonLinuxGeneration.AMAZON_LINUX_2
        )

        # Instance

        self.perforce_server_instance_main = ec2.Instance(
            self,
            "PerforceServerInstance",
            resource_signal_timeout=Duration.minutes(15),
            role=ec2_role,
            availability_zone=self._subnet.availability_zone,
            machine_image=linux_image,
            vpc=self._vpc,
            instance_type=ec2.InstanceType.of(
                ec2.InstanceClass.COMPUTE5, ec2.InstanceSize.XLARGE4
            ),
            key_name=self._key_pair_name,
            security_group=security_group,
            vpc_subnets=ec2.SubnetSelection(subnets=[self._subnet]),
            block_devices=[log_block_device, metadata_block_device],
        )

        # Allow access to EFS
        depot_filesystem.connections.allow_default_port_from(security_group)

        perforce_instance_logical_id = NestedStack.of(self).get_logical_id(
            self.perforce_server_instance_main.node.default_child
        )

        # ensure efs is ready
        self.perforce_server_instance_main.node.add_dependency(depot_filesystem)

        # Read UserData Script and replace placeholders
        with open("assets/setup-perforce-helix-core.sh", "r") as user_data_file:
            user_data = user_data_file.read()

        user_data_replacement_map = {
            "SERVER_ID_PLACEHOLDER": "master.1",
            "PERFORCE_PASSWORD_ARN_PLACEHOLDER": secret.secret_full_arn,
            "SNS_ALERT_TOPIC_ARN_PLACEHOLDER": sns_topic_arn,
            "STACK_NAME_PLACEHOLDER": self.stack_name,
            "RESOURCE_LOGICAL_ID_PLACEHOLDER": perforce_instance_logical_id,
            "REGION_PLACEHOLDER": self._region,
            "SWARM_IP_PLACEHOLDER": f"{PERFORCE_SWARM_RECORD_PREFIX}{self._hosted_zone.zone_name}",
            "LOCAL_P4_PORT_PLACEHOLDER": "ssl:localhost:1666",
            "FILESYSTEMID": depot_filesystem.file_system_id,
        }
        user_data = replace_user_data_values(
            user_data=user_data, replacement_map=user_data_replacement_map
        )

        self.perforce_server_instance_main.add_user_data(user_data)

        Tags.of(self.perforce_server_instance_main).add(
            "Name",
            f"{self._stage}-helix-core",
        )
        Tags.of(self.perforce_server_instance_main).add("Service", "P4")

        self.perforce_server_record = r53.ARecord(
            self,
            "PerforceServerARecord",
            target=r53.RecordTarget.from_ip_addresses(
                self.perforce_server_instance_main.instance_private_ip
            ),
            zone=self._hosted_zone,
            comment="Private record for Perforce Server",
            record_name=f"{PERFORCE_SERVER_RECORD_PREFIX}{self._hosted_zone.zone_name}",
        )
