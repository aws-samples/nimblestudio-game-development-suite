import json
import os
from typing import List

from aws_cdk.aws_autoscaling import AutoScalingGroup

from aws_cdk import (
    Stack,
    Tags,
)

from aws_cdk.aws_ec2 import (
    InstanceClass,
    InstanceSize,
    InstanceType,
    MachineImage,
    Port,
    SecurityGroup,
    Subnet,
    SubnetSelection,
    UserData,
    WindowsImage,
    WindowsVersion,
)

from aws_cdk.aws_iam import ManagedPolicy, Role, ServicePrincipal
from aws_cdk.aws_s3_assets import Asset
from aws_cdk.aws_ssm import StringParameter

from constructs import Construct

from nimblestudio.utils import add_user_data_cloudwatch_agent, is_valid_instance_type


class IncredibuildWorkers(Construct):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        incredibuild_coordinator_domain_name: str,
        incredibuild_coordinator_security_group: SecurityGroup,
        incredibuild_installer_location: str,
        vpc: str,
        vpc_endpoints_sg: SecurityGroup,
        worker_subnets: List[Subnet],
        workstations_security_group: SecurityGroup,
    ):
        super().__init__(scope, construct_id)

        # Create a new Security Group to be used by Incredibuild workers
        incredibuild_workers_security_group = SecurityGroup(
            self,
            "IncredibuildWorkersSG",
            allow_all_outbound=True,
            description="Allow IncrediBuild workers to connect to the coordinator",
            security_group_name="IncredibuildWorkersSG",
            vpc=vpc,
        )

        # Make sure that the Incredibuild workers can connect to the coordinator
        incredibuild_coordinator_security_group.connections.allow_from(
            incredibuild_workers_security_group.connections,
            Port.all_traffic(),
            "Allow the Incredibuild coordinator to accept connections from workers on any port.",
        )

        # Make sure that Incredibuild workers can communicate with Workstations
        incredibuild_workers_security_group.connections.allow_from(
            workstations_security_group.connections,
            Port.all_traffic(),
            "Allow the Incredibuild workers to accept connections from workstations on any port.",
        )

        # Ensure the coordinator can hit the SSM endpoint
        vpc_endpoints_sg.connections.allow_from(
            incredibuild_workers_security_group.connections, Port.tcp(443)
        )

        # Create a role for the workers which allows you to connect to them via SSM
        workers_role = Role(
            self,
            "IncredibuildWorkersRole",
            assumed_by=ServicePrincipal("ec2.amazonaws.com"),
            managed_policies=[
                ManagedPolicy.from_aws_managed_policy_name(
                    "AmazonSSMManagedInstanceCore"
                )
            ],
            role_name="IncredibuildWorkersRole",
        )

        # Configure UserData to configure CloudWatch, download Incredibuild, and then
        # configure the workers to connect to the Incredibuild coordinator automatically
        self._user_data = UserData.for_windows()
        self._add_user_data_cloudwatch_agent(coordinator_instance_role=workers_role)
        self._add_incredibuild_installer_user_data(
            coordinator_domain_name=incredibuild_coordinator_domain_name,
            incredibuild_installer_location=incredibuild_installer_location,
        )

        user_data = UserData.custom("<persist>true</persist>")
        user_data.add_commands(self._user_data.render())

        # You can set the WORKER_AMI environment variable to the id of an AMI that will
        # be used by Incredibuild workers. This AMI may have Visual Studio installed,
        # and any other software you want Incredibuild to use
        worker_ami = os.getenv("WORKER_AMI")
        worker_machine_image = (
            MachineImage.generic_windows(
                {
                    f"{Stack.of(self).region}": worker_ami,
                }
            )
            if worker_ami
            else WindowsImage(WindowsVersion.WINDOWS_SERVER_2022_ENGLISH_FULL_BASE)
        )

        # Use the instance type specified in the WORKER_INSTANCE_TYPE environment
        # variable if possible, otherwise default to c5.xlarge4
        specified_worker_instance_type = os.getenv("WORKER_INSTANCE_TYPE")
        worker_instance_type = (
            InstanceType(specified_worker_instance_type)
            if specified_worker_instance_type
            and is_valid_instance_type(specified_worker_instance_type)
            else InstanceType.of(
                InstanceClass.COMPUTE5_HIGH_PERFORMANCE, InstanceSize.XLARGE4
            )
        )

        # Create an ASG that can help speed up Incredibuild build jobs even when there
        # are no other Workstations available
        self.incredibuild_workers = AutoScalingGroup(
            self,
            "IncredibuildWorkerFleet",
            instance_type=worker_instance_type,
            machine_image=worker_machine_image,
            min_capacity=0,
            max_capacity=40,
            role=workers_role,
            security_group=incredibuild_workers_security_group,
            user_data=user_data,
            vpc=vpc,
            vpc_subnets=SubnetSelection(subnets=worker_subnets),
        )

        Tags.of(self.incredibuild_workers).add("Name", "Incredibuild Worker")

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
                                "log_stream_name": "{instance_id}/Worker",
                            },
                        ]
                    }
                }
            }
        }
        cloudwatch_ssm_param = StringParameter(
            self,
            "IncredibuildWorkerCloudWatchConfig",
            description="Cloudwatch configuration for Incredibuild worker instances",
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
        coordinator_domain_name: str,
        incredibuild_installer_location: str,
    ) -> None:

        # Download the Incredibuild silent installer
        incredibuild_installer_local_path = r"C:\temp\IBSetupConsole.exe"

        self._user_data.add_commands(
            f'if (-Not (Test-Path "C:\\temp")) {{ New-Item "C:\\temp" -ItemType Directory }}'
        )

        self._user_data.add_commands(
            f'wget -Uri "{incredibuild_installer_location}" -Outfile "{incredibuild_installer_local_path}"'
        )

        # Install Incredibuild, and then configure it to connect to the coordinator
        self._user_data.add_commands(
            f'{incredibuild_installer_local_path} /install /Components=Agent /Coordinator="{coordinator_domain_name}"'
        )
