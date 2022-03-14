import os
from pathlib import Path
from typing import List

from aws_cdk import aws_ec2 as ec2
from aws_cdk.aws_nimblestudio import CfnStudioComponent
from aws_cdk.aws_s3_assets import Asset
from aws_cdk import Stack
from constructs import Construct

from nimblestudio.constructs.incredibuild_coordinator import IncredibuildCoordinator
from nimblestudio.constructs.incredibuild_workers import IncredibuildWorkers

import sys

sys.path.append("../../utils")
from utils.config_retriever import ConfigRetriever


class NimbleStudioBuildFarmStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        config_retriever = ConfigRetriever()

        # Find the studio in this account, and retrieve the studio id
        studio_id = config_retriever.studio_id

        # Get the studio's VPC from the Network CloudFormation stack
        vpc_id = config_retriever.vpc_id

        # Get the workstation Security Group from the Data Cloudformation Stack
        workstations_sg_id = config_retriever.workstations_sg_id

        # Create a Security Group construct using the existing Security Group
        workstations_sg = ec2.SecurityGroup.from_security_group_id(
            self,
            "WorkstationEgress",
            workstations_sg_id,
            allow_all_outbound=True,
            mutable=True,
        )

        # Modify the Workstations Security Group to allow instances using it it to
        # connect to other instances also using it
        workstations_sg.add_ingress_rule(
            workstations_sg,
            ec2.Port.all_traffic(),
            "Allows workstations to be able to connect to each other",
        )

        # Find the VPC Endpoints Security Group so that we can ensure that the Incredibuild
        # instances can connect via Systems Manager
        vpc_endpoints_sg_id = config_retriever.vpce_sg_id

        # Create a Security Group construct using the VPC Endpoints Security Group
        vpc_endpoints_sg = ec2.SecurityGroup.from_security_group_id(
            self,
            "VpcInterfaceEndpoints",
            vpc_endpoints_sg_id,
            allow_all_outbound=False,
            mutable=True,
        )

        # Now we find the RenderWorkers and WorkerSupport subnets and create constructs
        # referencing those existing subnets
        render_worker_subnet_info = config_retriever.render_worker_subnet
        render_worker_subnet_id = render_worker_subnet_info["SubnetId"]
        render_worker_subnet = ec2.Subnet.from_subnet_attributes(
            self,
            render_worker_subnet_id,
            availability_zone=render_worker_subnet_info["AvailabilityZone"],
            ipv4_cidr_block=render_worker_subnet_info["CidrBlock"],
            subnet_id=render_worker_subnet_id,
        )

        worker_support_subnet_info = config_retriever.worker_support_subnet
        worker_support_subnet_id = config_retriever.worker_support_subnet_id
        worker_support_subnet = ec2.Subnet.from_subnet_attributes(
            self,
            worker_support_subnet_id,
            availability_zone=worker_support_subnet_info["AvailabilityZone"],
            ipv4_cidr_block=worker_support_subnet_info["CidrBlock"],
            subnet_id=worker_support_subnet_id,
        )

        self.render_worker_subnets: List[ec2.Subnet] = [render_worker_subnet]
        self.worker_support_subnets: List[ec2.Subnet] = [worker_support_subnet]

        # Create a VPC construct referencing the studio's VPC
        self.vpc = ec2.Vpc.from_lookup(self, "Vpc", vpc_id=vpc_id)

        # We need to configure the WorkerSupport subnet to allow Internet access in
        # order to reach the Incredibuild license server, so we'll need the id of
        # the Network ACL in order to allow the ephemeral outbound ports
        worker_support_network_acl_id = config_retriever.worker_support_nacl_id

        worker_support_network_acl = ec2.NetworkAcl.from_network_acl_id(
            self, "WorkerSupportNetworkACL", worker_support_network_acl_id
        )

        # We locate the Incredibuild installer and an Incredibuild license file
        incredibuild_path = self._get_incredibuild_path()
        incredibuild_installer_path = self._get_incredibuild_installer_path(
            incredibuild_path
        )

        if not Path.exists(incredibuild_installer_path):
            print(
                f"ERROR: Failed to find the Incredibuild installer at {incredibuild_installer_path}"
            )
            sys.exit(1)

        # Upload the Incredibuild installer to the CDK's S3 bucket in your account
        self.incredibuild_installer = Asset(
            self, "IncredibuildInstaller", path=str(incredibuild_installer_path)
        )

        incredibuild_license_path = self._get_incredibuild_license_path(
            incredibuild_path
        )

        # Upload the Incredibuild license to the CDK's S3 bucket in your account
        self.incredibuild_license = Asset(
            self, "IncredibuildLicense", path=str(incredibuild_license_path)
        )

        # Create an Incredibuild coordinator
        self.incredibuild_coordinator = IncredibuildCoordinator(
            self,
            "IncredibuildCoordinatorConstruct",
            incredibuild_installer=self.incredibuild_installer,
            incredibuild_license=self.incredibuild_license,
            studio_hosted_zone_attributes=config_retriever.hosted_zone,
            vpc=self.vpc,
            vpc_endpoints_sg=vpc_endpoints_sg,
            vpc_id=vpc_id,
            worker_support_network_acl=worker_support_network_acl,
            worker_support_subnets=self.worker_support_subnets,
            workstations_security_group=workstations_sg,
        )

        # Create an ASG that creates Incredibuild workers
        self.incredibuild_workers = IncredibuildWorkers(
            self,
            "IncredibuildWorkersConstruct",
            incredibuild_coordinator_domain_name=self.incredibuild_coordinator.incredibuild_server_record.domain_name,
            incredibuild_coordinator_security_group=self.incredibuild_coordinator.coordinator_security_group,
            incredibuild_installer=self.incredibuild_installer,
            vpc=self.vpc,
            vpc_endpoints_sg=vpc_endpoints_sg,
            worker_subnets=self.render_worker_subnets,
            workstations_security_group=workstations_sg,
        )

        # Create a studio component that will auto-configure the coordinator URL on Workstations
        self.incredibuild_studio_component = CfnStudioComponent(
            self,
            "IncredibuildStudioComponent",
            name="Incredibuild",
            description="Incredibuild studio component.",
            studio_id=studio_id,
            type="CUSTOM",
            subtype="CUSTOM",
            initialization_scripts=[
                CfnStudioComponent.StudioComponentInitializationScriptProperty(
                    launch_profile_protocol_version="2021-03-31",
                    platform="WINDOWS",
                    run_context="SYSTEM_INITIALIZATION",
                    script=f"""$RegistryPath = 'HKLM:\SOFTWARE\WOW6432Node\Xoreax\IncrediBuild\BuildService'
If (-Not (Test-Path $RegistryPath)) {{
  New-Item -Path $RegistryPath -Force | Out-Null
}}

$Name = 'CoordHost'
$Value = '{self.incredibuild_coordinator.incredibuild_server_record.domain_name}'
New-ItemProperty -Path $RegistryPath -Name $Name -Value $Value -PropertyType String -Force

$Name = 'RecentCoordHosts'
$Value = '{self.incredibuild_coordinator.incredibuild_server_record.domain_name}'
New-ItemProperty -Path $RegistryPath -Name $Name -Value $Value -PropertyType String -Force

$Name = 'Group'
$Value = ''
New-ItemProperty -Path $RegistryPath -Name $Name -Value $Value -PropertyType String -Force""",
                ),
            ],
        )

    def _get_incredibuild_path(self):
        return Path(__file__).parent.parent.parent.joinpath("incredibuild").absolute()

    def _get_incredibuild_installer_path(self, incredibuild_path: Path):
        incredibuild_installer_path = incredibuild_path.joinpath("IBSetupConsole.exe")
        return incredibuild_installer_path

    def _get_incredibuild_license_path(self, incredibuild_path: Path):
        # We search the incredibuild_path for any Incredibuild license files, and return the most recent one
        license_files = incredibuild_path.glob("*.IB_lic")
        list_of_files = [license_file for license_file in license_files]

        if not list(list_of_files):
            print(
                f"ERROR: Failed to find an Incredibuild license in {incredibuild_path}"
            )
            sys.exit(1)

        latest_file = max(list_of_files, key=os.path.getctime)

        return latest_file
