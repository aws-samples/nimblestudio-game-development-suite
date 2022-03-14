import boto3
import os
import random
import sys
from typing import Any, Dict


class ConfigRetriever:
    def __init__(self):
        self.existing_subnets = {"WorkerSupport": [], "Workstations": []}
        self.workstation_subnet_azs = []

        self.studio = self.get_studio()
        self.studio_id = self.studio['studioId']
        self.studio_name = self.studio["studioName"]
        self.region = self.studio["homeRegion"]
        self.vpc_id = self.get_vpc_id(self.studio_name)
        self.vpc_cidr = self.get_vpc_cidr(self.vpc_id)
        self.vpce_sg_id = self.get_vpc_interface_endpoint_sg_id(self.studio_name)
        self.render_worker_subnet = self.find_subnet_by_name("RenderWorkers", self.vpc_id)
        self.workstations_sg_id = self.get_workstations_sg_id(self.studio_name)
        self.worker_support_subnet = self.find_worker_support_subnet(self.vpc_id)
        self.worker_support_subnet_id = self.find_worker_support_subnet_id(self.vpc_id)
        self.worker_support_subnet_az = self.find_worker_support_subnet_az(self.vpc_id)
        self.worker_support_nacl_id = self.find_subnet_network_acl_id(vpc_id=self.vpc_id, subnet_id=self.worker_support_subnet_id)
        self.hosted_zone = self.find_studio_hosted_zone(self.vpc_id)
        self.helix_swarm_ami_map = self.retrieve_helix_swarm_ami_map(self.region)
        self.perforce_sg_id = self.get_perforce_sg_id()
        self.license_server_security_group_id = (
            self.get_license_server_security_group_id()
        )
        # parameters get from user
        self.perforce_notification_email = self.get_perforce_notification_email()
        self.perforce_key_pair_name = self.get_perforce_key_pair_name()
        self.stage = os.environ.get("CDK_STAGE", "DEV")
        self.jenkins_key_pair_name = self.get_jenkins_key_pair_name()
        self.build_node_ami_id = self.get_build_node_ami_id()

    def get_studio(self):
        client = boto3.client("nimble")
        response = client.list_studios()
        studios = response["studios"]
        if not studios:
            print("ERROR: No studios were found in your account.")
            sys.exit(1)
        return studios[0]

    def find_cloudformation_stack(self, studio_name: str, stack_type: str):
        stack_name = f"{studio_name}{stack_type}"
        client = boto3.client("cloudformation")
        response = client.describe_stacks(StackName=stack_name)
        return response["Stacks"][0]

    def find_output_value(
        self, stack_data: Dict[str, Any], export_name: str, value_prefix: str = ""
    ):
        outputs = stack_data["Outputs"]
        for output in outputs:
            if output["OutputKey"].startswith(export_name):
                if value_prefix:
                    if not output["OutputValue"].startswith(value_prefix):
                        continue
                return output["OutputValue"]
        raise ValueError(
            f"Couldn't find export name '{export_name}' in stack '{stack_data['StackName']}'"
        )

    def get_vpc_id(self, studio_name: str):
        network_stack = self.find_cloudformation_stack(studio_name, "Network")
        vpc_id = self.find_output_value(
            network_stack, "ExportsOutputRefStudioDefaultVpc", "vpc-"
        )
        return vpc_id

    def get_vpc_cidr(self, vpc_id: str):
        client = boto3.client("ec2")
        response = client.describe_vpcs(
            VpcIds=[vpc_id],
        )
        vpcs = response["Vpcs"]
        if not response or len(vpcs) != 1:
            print(f"ERROR: Unable to determine CIDR for VPC {vpc_id}.")
            sys.exit(1)
        return vpcs[0]["CidrBlock"]

    def get_vpc_interface_endpoint_sg_id(self, studio_name: str):
        network_stack = self.find_cloudformation_stack(studio_name, "Network")
        try:
            sg_id = self.find_output_value(
                network_stack,
                "ExportsOutputFnGetAttStudioDefaultVpcInterfaceEndpointSG",
                "sg-",
            )
        except ValueError as e:
            print(e)
            sg_id = None
        return sg_id

    def get_workstations_sg_id(self, studio_name: str):
        data_stack = self.find_cloudformation_stack(studio_name, "Data")
        sg_id = self.find_output_value(
            data_stack,
            "ExportsOutputFnGetAttWorkstationEgress",
            "sg-",
        )
        return sg_id

    def get_perforce_sg_id(self) -> str or None:
        client = boto3.client("ec2")
        response = client.describe_security_groups(
            Filters=[
                {
                    "Name": "group-name",
                    "Values": [
                        "NimbleStudioPerforceServerStack-NimbleStudioPerforceServerNetworkStack*",
                    ],
                },
            ],
        )
        if response and len(response["SecurityGroups"]) == 1:
            return response["SecurityGroups"][0]["GroupId"]
        return None

    def get_subnets(self, vpc_id: str, subnet_name: str):

        # If we've already fetched the subnet, let's not query for it again
        subnets = self.existing_subnets.get(subnet_name)
        if subnets:
            return subnets

        subnet_values = (
            [subnet_name]
            if self.existing_subnets["WorkerSupport"]
            else ["WorkerSupport", "Workstations", subnet_name]
        )

        client = boto3.client("ec2")
        response = client.describe_subnets(
            Filters=[
                {
                    "Name": "vpc-id",
                    "Values": [
                        vpc_id,
                    ],
                },
                {
                    "Name": "tag:Name",
                    "Values": subnet_values,
                },
            ],
        )

        other_subnets = []
        worker_support_subnets = []
        workstation_subnets = []
        self.workstation_subnet_azs = {}

        for subnet in response["Subnets"]:
            for tag in subnet["Tags"]:
                if tag.get("Key", "") == "Name":
                    if tag["Value"] == "Workstations":
                        workstation_subnets.append(subnet)
                        self.workstation_subnet_azs[subnet["AvailabilityZoneId"]] = subnet
                    elif tag["Value"] == "WorkerSupport":
                        worker_support_subnets.append(subnet)
                    else:
                        other_subnets.append(subnet)

        if worker_support_subnets:
            self.existing_subnets["WorkerSupport"] = worker_support_subnets
        if workstation_subnets:
            self.existing_subnets["Workstations"] = workstation_subnets
        if other_subnets:
            self.existing_subnets[subnet_name] = other_subnets

        return self.existing_subnets[subnet_name]


    def find_subnet_by_name(
        self, subnet_name: str, vpc_id: str, matching_workstations_az: bool = True
    ):
        subnets = self.get_subnets(vpc_id, subnet_name)

        if matching_workstations_az:
            # Local zones will introduce multiple "Workstations" subnets, so we need
            # to find the WorkerSupport subnet in the same AZ
            for subnet in subnets:
                if subnet["AvailabilityZoneId"] in self.workstation_subnet_azs:
                    return subnet

        return None


    def find_worker_support_subnet(self, vpc_id: str):
        worker_support_subnets = self.get_subnets(vpc_id, "WorkerSupport")

        # Local zones will introduce multiple "Workstations" subnets, so we need
        # to find the WorkerSupport subnet in the same AZ
        for subnet in worker_support_subnets:
            if subnet["AvailabilityZoneId"] in self.workstation_subnet_azs:
                return subnet

        return None


    def find_worker_support_subnet_id(self, vpc_id: str):
        subnet = self.find_worker_support_subnet(vpc_id)

        if not subnet:
            print(f"ERROR: Couldn't find WorkerSupport subnet in studio VPC {vpc_id}.")
            sys.exit(1)

        return subnet["SubnetId"]

    def find_worker_support_subnet_az(self, vpc_id: str):
        subnet = self.find_worker_support_subnet(vpc_id)

        if not subnet:
            print(f"ERROR: Couldn't find WorkerSupport subnet in studio VPC {vpc_id}.")
            sys.exit(1)

        return subnet["AvailabilityZone"]

    def get_worker_support_subnet(self, vpc_id: str):
        client = boto3.client("ec2")
        response = client.describe_subnets(
            Filters=[
                {
                    "Name": "vpc-id",
                    "Values": [
                        vpc_id,
                    ],
                },
                {
                    "Name": "tag:Name",
                    "Values": [
                        "WorkerSupport",
                        "Workstations",
                    ],
                },
            ],
        )
        worker_support_subnets = []
        workstation_subnet_azs = {}
        for subnet in response["Subnets"]:
            for tag in subnet["Tags"]:
                if tag.get("Key", "") == "Name":
                    if tag["Value"] == "Workstations":
                        workstation_subnet_azs[subnet["AvailabilityZoneId"]] = subnet
                    else:
                        worker_support_subnets.append(subnet)
        # Local zones will introduce multiple "Workstations" subnets, so we need
        # to find the WorkerSupport subnet in the same AZ
        for subnet in worker_support_subnets:
            if subnet["AvailabilityZoneId"] in workstation_subnet_azs:
                return subnet
        return None

    def find_subnet_network_acl_id(self, vpc_id: str, subnet_id: str):
        client = boto3.client("ec2")
        response = client.describe_network_acls(
            Filters=[
                {"Name": "vpc-id", "Values": [vpc_id]},
                {"Name": "association.subnet-id", "Values": [subnet_id]},
            ],
        )

        if not response or len(response["NetworkAcls"]) == 0:
            print("ERROR: No Netork ACLs associated by VPC were found in your account.")
            sys.exit(1)

        return response["NetworkAcls"][0]["Associations"][0]["NetworkAclId"]

    def find_studio_hosted_zone(self, vpc_id: str):
        account_id = boto3.client("sts").get_caller_identity().get("Account")

        session = boto3.session.Session()
        region = session.region_name

        client = session.client("route53")

        hosted_zones = client.list_hosted_zones_by_vpc(VPCId=vpc_id, VPCRegion=region)

        valid_hosted_zones = []
        for hosted_zone in hosted_zones["HostedZoneSummaries"]:
            owner = hosted_zone["Owner"]

            # Make sure we only return the hosted zones owned by the account (otherwise)
            # the results include things like EFS
            try:
                if owner["OwningAccount"] == account_id:
                    valid_hosted_zones.append(
                        {"id": hosted_zone["HostedZoneId"], "name": hosted_zone["Name"]}
                    )
            except KeyError:
                pass
        if len(valid_hosted_zones) == 0:
            print("ERROR: No hosted zone associated by VPC were found in your account.")
            sys.exit(1)   

        return random.choice(valid_hosted_zones)

    def retrieve_helix_swarm_ami_map(self, region: str):
        client = boto3.client("ec2")

        # AMI name coming from:
        # https://s3.us-east-1.amazonaws.com/perforce-cf-templates/releases/33e4c88e555cf40c7b0851d22b02def4.template
        response = client.describe_images(
            Filters=[
                {
                    "Name": "name",
                    "Values": [
                        "Perforce-Swarm-SDP-AMI-Base*",
                    ],
                }
            ],
        )

        if len(response["Images"]) == 0:
            print(
                f"ERROR: Could not determine latest AMI ID with name prefix 'Perforce-Swarm-SDP-AMI-BASE' for region {region}."
            )
            sys.exit(1)

        # Sort Images by Creation Date to get latest image
        amis = sorted(response["Images"], key=lambda k: k["CreationDate"], reverse=True)

        return {region: amis[0]["ImageId"]}

    def get_license_server_security_group_id(self):
        ec2 = boto3.client("ec2")
        group_name = self.studio_name + "Network-LicenseServers"
        response = ec2.describe_security_groups(
            Filters=[dict(Name="group-name", Values=[group_name + "*"])]
        )
        group_id = response["SecurityGroups"][0]["GroupId"]
        return group_id

    def get_perforce_notification_email(self):
        notification_email = os.environ.get("CDK_PERFORCE_NOTIFICATION_EMAIL", "")
        if notification_email == "":
            print(
                "ERROR: Please run 'export CDK_PERFORCE_NOTIFICATION_EMAIL=example@example.com'"
            )
        return notification_email

    def get_perforce_key_pair_name(self):
        key_pair_name = os.environ.get("CDK_PERFORCE_KEY_PAIR_NAME", "")
        if key_pair_name == "":
            print("ERROR: Please run 'export CDK_PERFORCE_KEY_PAIR_NAME=ec2_key_pair_name'")
        return key_pair_name

    def get_build_node_ami_id(self):
        build_node_ami_id = os.environ.get("CDK_JENKINS_BUILD_NODE_AMI_ID", "")
        if build_node_ami_id == "":
            print(
                "ERROR: Jenkins build node AMI ID could not be determined. Please run\nexport CDK_JENKINS_BUILD_NODE_AMI_ID=<ami_id>"
            )
        return build_node_ami_id

    def get_jenkins_key_pair_name(self):
        key_pair_name = os.environ.get("CDK_BUILD_PIPELINE_KEY_PAIR_NAME", "")
        if key_pair_name == "":
            print(
                "ERROR: Please run 'export CDK_BUILD_PIPELINE_KEY_PAIR_NAME=ec2_key_pair_name'"
            )
        return key_pair_name