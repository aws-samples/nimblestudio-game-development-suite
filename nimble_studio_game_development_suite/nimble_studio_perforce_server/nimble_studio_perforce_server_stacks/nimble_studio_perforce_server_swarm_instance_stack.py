from aws_cdk import (
    Duration,
    NestedStack,
    Tags,
    aws_ec2 as ec2,
    aws_iam as iam,
    aws_route53 as r53,
    aws_secretsmanager as secretsmanager,
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


class NimbleStudioPerforceServerSwarmInstanceStack(
    NimbleStudioPerforceServerCommonStack
):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        security_group: ec2.ISecurityGroup,
        secret: secretsmanager.ISecret,
        ec2_role: iam.IRole,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Instance

        perforce_server_dns_record = (
            f"{PERFORCE_SERVER_RECORD_PREFIX}{self._hosted_zone.zone_name}"
        )
        perforce_swarm_dns_record = (
            f"{PERFORCE_SWARM_RECORD_PREFIX}{self._hosted_zone.zone_name}"
        )

        self.perforce_swarm_instance_main = ec2.Instance(
            self,
            "PerforceSwarmInstance",
            resource_signal_timeout=Duration.minutes(15),
            role=ec2_role,
            availability_zone=self._subnet.availability_zone,
            machine_image=ec2.MachineImage.generic_linux(
                ami_map=self._helix_swarm_ami_map
            ),
            vpc=self._vpc,
            instance_type=ec2.InstanceType.of(
                ec2.InstanceClass.BURSTABLE3, ec2.InstanceSize.SMALL
            ),
            key_name=self._key_pair_name,
            security_group=security_group,
            vpc_subnets=ec2.SubnetSelection(subnets=[self._subnet]),
            block_devices=[
                ec2.BlockDevice(
                    device_name="/dev/sda1",
                    volume=ec2.BlockDeviceVolume.ebs(
                        20,
                        delete_on_termination=True,
                        volume_type=ec2.EbsDeviceVolumeType.GP3,
                    ),
                )
            ],
        )

        swarm_instance_logical_id = NestedStack.of(self).get_logical_id(
            self.perforce_swarm_instance_main.node.default_child
        )

        # Read UserData Script and replace placeholders
        with open("assets/setup-perforce-helix-swarm.sh", "r") as user_data_file:
            user_data = user_data_file.read()

        user_data_replacement_map = {
            "SECRET_ARN_PLACEHOLDER": secret.secret_full_arn,
            "STACK_NAME_PLACEHOLDER": self.stack_name,
            "RESOURCE_LOGICAL_ID_PLACEHOLDER": swarm_instance_logical_id,
            "REGION_PLACEHOLDER": self.region,
            "STAGE_PLACEHOLDER": self._stage,
            "PERFORCE_SERVER_DNS_RECORD_PLACEHOLDER": perforce_server_dns_record,
            "PERFORCE_SWARM_DNS_RECORD_PLACEHOLDER": perforce_swarm_dns_record,
        }
        user_data = replace_user_data_values(
            user_data=user_data, replacement_map=user_data_replacement_map
        )

        self.perforce_swarm_instance_main.add_user_data(user_data)

        Tags.of(self.perforce_swarm_instance_main).add(
            "Name", f"{self._stage}-helix-swarm"
        )
        Tags.of(self.perforce_swarm_instance_main).add("Service", "P4")

        self.perforce_swarm_record = r53.ARecord(
            self,
            "PerforceServerARecord",
            target=r53.RecordTarget.from_ip_addresses(
                self.perforce_swarm_instance_main.instance_private_ip
            ),
            zone=self._hosted_zone,
            comment="Private record for Perforce Swarm",
            record_name=perforce_swarm_dns_record,
        )
