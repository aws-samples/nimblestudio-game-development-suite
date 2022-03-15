import json
from typing import List

from aws_cdk import (
    CfnOutput,
    Duration,
    Stack,
    Tags,
)

from aws_cdk.aws_ec2 import (
    AclCidr,
    AclTraffic,
    Instance,
    InstanceClass,
    InstanceSize,
    InstanceType,
    NetworkAcl,
    Port,
    SecurityGroup,
    Subnet,
    SubnetSelection,
    TrafficDirection,
    UserData,
    Vpc,
    WindowsImage,
    WindowsVersion,
)

from aws_cdk.aws_iam import ManagedPolicy, Role, ServicePrincipal
from aws_cdk.aws_route53 import ARecord, HostedZone, RecordTarget
from aws_cdk.aws_s3_assets import Asset
from aws_cdk.aws_ssm import StringParameter

from constructs import Construct

from nimblestudio.utils import add_user_data_cloudwatch_agent


class IncredibuildCoordinator(Construct):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        incredibuild_installer: Asset,
        incredibuild_license: Asset,
        studio_hosted_zone_attributes: dict,
        vpc: Vpc,
        vpc_endpoints_sg: SecurityGroup,
        vpc_id: str,
        worker_support_network_acl: NetworkAcl,
        worker_support_subnets: List[Subnet],
        workstations_security_group: SecurityGroup,
    ):
        super().__init__(scope, construct_id)

        self.coordinator_security_group = SecurityGroup(
            self,
            "IncredibuildCoordinatorSG",
            allow_all_outbound=True,
            description="Allow IncrediBuild agents to connect to the coordinator",
            security_group_name="IncredibuildCoordinatorSG",
            vpc=vpc,
        )

        self.coordinator_security_group.connections.allow_from(
            workstations_security_group.connections, Port.all_traffic()
        )

        # Ensure the coordinator can hit the SSM endpoint
        vpc_endpoints_sg.connections.allow_from(
            self.coordinator_security_group.connections, Port.tcp(443)
        )

        # The coordinator isn't allowed to make outbound connections, so we'll add a
        # rule to allow traffic to the VPC endpoints (for services like SSM)
        self.coordinator_security_group.connections.allow_to_any_ipv4(Port.tcp(443))

        Tags.of(self.coordinator_security_group).add(
            "Name", "Incredibuild Coordinator SG"
        )

        # We need to configure the WorkerSupport subnet to allow Internet access in
        # order to reach the Incredibuild license server, so we'll need the id of
        # the Network ACL in order to allow the ephemeral outbound ports
        worker_support_network_acl.add_entry(
            "AllowEphemeralTcpOut",
            rule_number=10000,
            cidr=AclCidr.ipv4("0.0.0.0/0"),
            traffic=AclTraffic.tcp_port_range(0, 65535),
            direction=TrafficDirection.EGRESS,
        )
        worker_support_network_acl.add_entry(
            "AllowEphemeralUdpOut",
            rule_number=10010,
            cidr=AclCidr.ipv4("0.0.0.0/0"),
            traffic=AclTraffic.udp_port_range(0, 65535),
            direction=TrafficDirection.EGRESS,
        )

        # Create a role for the coordinator which allows you to connect to it via SSM
        coordinator_instance_role = Role(
            self,
            "IncredibuildCoordinatorRole",
            assumed_by=ServicePrincipal("ec2.amazonaws.com"),
            managed_policies=[
                ManagedPolicy.from_aws_managed_policy_name(
                    "AmazonSSMManagedInstanceCore"
                )
            ],
            role_name="IncredibuildCoordinatorRole",
        )

        self.coordinator_instance = Instance(
            self,
            "IncredibuildCoordinator",
            instance_type=InstanceType.of(InstanceClass.BURSTABLE3, InstanceSize.LARGE),
            machine_image=WindowsImage(
                WindowsVersion.WINDOWS_SERVER_2019_ENGLISH_FULL_BASE
            ),
            role=coordinator_instance_role,
            # The deploy will fail if the co-ordinator takes over 10 minutes to
            # configure itself
            resource_signal_timeout=Duration.minutes(10),
            security_group=self.coordinator_security_group,
            user_data=UserData.custom("<persist>true</persist>"),
            vpc=vpc,
            vpc_subnets=SubnetSelection(subnets=worker_support_subnets),
        )

        Tags.of(self.coordinator_instance).add("Name", "Incredibuild Coordinator")

        # Configure UserData to configure CloudWatch, download Incredibuild and the
        # Incredibuild license, and then automatically configure the Incredibuild
        # coordinator
        self._user_data = UserData.for_windows()
        self._add_user_data_cloudwatch_agent(
            coordinator_instance_role=coordinator_instance_role
        )
        self._add_incredibuild_installer_user_data(
            coordinator_instance_role=coordinator_instance_role,
            incredibuild_installer=incredibuild_installer,
            incredibuild_license=incredibuild_license,
        )

        self.coordinator_instance.user_data.add_commands(self._user_data.render())

        # Find the existing Route 53 hosted zone for the coordinator, and add an A
        # record in it pointing to the Incredibuild coordinator
        studio_hosted_zone = studio_hosted_zone_attributes

        self._hosted_zone = HostedZone.from_hosted_zone_attributes(
            self,
            "StudioHostedZone",
            hosted_zone_id=studio_hosted_zone["id"],
            zone_name=studio_hosted_zone["name"],
        )

        self.incredibuild_server_record = ARecord(
            self,
            "IncredibuildCoordinatorARecord",
            target=RecordTarget.from_ip_addresses(
                self.coordinator_instance.instance_private_ip
            ),
            zone=self._hosted_zone,
            comment="Private record for Incredibuild Coordinator",
            record_name=f"incredibuild.{self._hosted_zone.zone_name}",
        )

        CfnOutput(
            self,
            "IncredibuildPrivateRecordName",
            value=self.incredibuild_server_record.domain_name,
        )

    # Configure the CloudWatch agent so that we upload logs to CloudWatch
    def _add_user_data_cloudwatch_agent(self, coordinator_instance_role: Role) -> None:
        # Store the cloudwatch configuration in Parameter Store
        cloudwatch_config = {
            "logs": {
                "logs_collected": {
                    "files": {
                        "collect_list": [
                            {
                                "file_path": r"C:\ProgramData\Amazon\EC2-Windows\Launch\Log\UserdataExecution.log",
                                "log_group_name": f"/aws/nimblestudio/incredibuild",
                                "log_stream_name": "{instance_id}/Coordinator",
                            },
                        ]
                    }
                }
            }
        }

        cloudwatch_ssm_param = StringParameter(
            self,
            "IncredibuildCoordinatorCloudWatchConfig",
            description="Cloudwatch configuration for Incredibuild coordinator instance",
            string_value=json.dumps(cloudwatch_config),
        )

        add_user_data_cloudwatch_agent(
            self,
            self._user_data,
            cloudwatch_ssm_param=cloudwatch_ssm_param,
            instance_role=coordinator_instance_role,
        )

    def _add_incredibuild_installer_user_data(
        self,
        *,
        coordinator_instance_role: Role,
        incredibuild_installer: Asset,
        incredibuild_license: Asset,
    ) -> None:
        # Firstly we need to give ourselves access to the CDK bucket
        incredibuild_installer.bucket.grant_read(coordinator_instance_role)

        # Download the Incredibuild silent installer
        incredibuild_installer_local_path = r"C:\temp\IBSetupConsole.exe"
        self._user_data.add_s3_download_command(
            bucket=incredibuild_installer.bucket,
            bucket_key=incredibuild_installer.s3_object_key,
            local_file=incredibuild_installer_local_path,
        )

        # Download the Incredibuild license
        incredibuild_license_local_path = r"C:\temp\license.IB_lic"
        self._user_data.add_s3_download_command(
            bucket=incredibuild_license.bucket,
            bucket_key=incredibuild_license.s3_object_key,
            local_file=incredibuild_license_local_path,
        )

        # Install Incredibuild, and then register the Incredibuild license
        self._user_data.add_commands(
            f"{incredibuild_installer_local_path} /install /Components=Coordinator",
            f'& "C:\\Program Files (x86)\\IncrediBuild\\XLicProc.exe" /LICENSEFILE={incredibuild_license_local_path}',
        )

        # Send the success signal to CloudFormation
        self._user_data.add_commands(
            f"cfn-signal --stack {Stack.of(self).stack_name} --resource {Stack.of(self).get_logical_id(self.coordinator_instance.node.default_child)} --region {Stack.of(self).region} --success true"
        )
