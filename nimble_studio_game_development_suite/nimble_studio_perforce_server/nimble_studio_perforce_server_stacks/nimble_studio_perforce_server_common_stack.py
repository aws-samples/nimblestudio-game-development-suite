from aws_cdk import NestedStack
from aws_cdk import aws_ec2 as ec2, aws_route53 as r53
from constructs import Construct
import sys

sys.path.append("../../utils")
from utils.config_retriever import ConfigRetriever

PERFORCE_SERVER_RECORD_PREFIX = "perforceserver."
PERFORCE_SWARM_RECORD_PREFIX = "perforceswarm."


class NimbleStudioPerforceServerCommonStack(NestedStack):
    """
    A base CDK nested stack class
    """

    def __init__(self, scope: Construct, id: str, **kwargs):
        super().__init__(scope, id, **kwargs)
        config_retriever = ConfigRetriever()

        self._validate_config(config_retriever=config_retriever)

        # Lookup our pre-created VPC by ID
        self._vpc: ec2.IVpc = ec2.Vpc.from_lookup(
            self, "vpc", vpc_id=config_retriever.vpc_id
        )

        self._vpc_cidr = config_retriever.vpc_cidr

        # Lookup our pre-created Subnet by ID and AZ
        self._subnet: ec2.ISubnet = ec2.Subnet.from_subnet_attributes(
            self,
            "subnet",
            subnet_id=config_retriever.worker_support_subnet_id,
            availability_zone=config_retriever.worker_support_subnet_az,
        )

        # Lookup our pre-created Network ACL by ID
        self._nacl: ec2.INetworkAcl = ec2.NetworkAcl.from_network_acl_id(
            self, "nacl", network_acl_id=config_retriever.worker_support_nacl_id
        )

        # Lookup our pre-created VPC Endpoints Security Group by ID if it exists
        self._vpce_sg = None
        if config_retriever.vpce_sg_id:
            self._vpce_sg: ec2.ISecurityGroup = (
                ec2.SecurityGroup.from_security_group_id(
                    self, "vpce_sg", security_group_id=config_retriever.vpce_sg_id
                )
            )

        self._workstations_sg: ec2.ISecurityGroup = (
            ec2.SecurityGroup.from_security_group_id(
                self,
                "workstations_sg",
                security_group_id=config_retriever.workstations_sg_id,
            )
        )

        # Lookup our pre-created PrivateHostedZone by ID and Name
        self._hosted_zone: r53.IPrivateHostedZone = (
            r53.HostedZone.from_hosted_zone_attributes(
                self,
                "hosted_zone",
                hosted_zone_id=config_retriever.hosted_zone["id"],
                zone_name=config_retriever.hosted_zone["name"],
            )
        )

        self._helix_swarm_ami_map = config_retriever.helix_swarm_ami_map

        self._stage = config_retriever.stage

        self._region = config_retriever.region

        self._notification_email = config_retriever.perforce_notification_email

        self._key_pair_name = config_retriever.perforce_key_pair_name

        self._studio_id = config_retriever.studio["studioId"]

        if self._notification_email == "" or self._key_pair_name == "":
            sys.exit(1)

    def _validate_config(self, config_retriever: ConfigRetriever):
        should_exit = False

        if not config_retriever.perforce_notification_email:
            print(
                f"ERROR: Please run 'export {ConfigRetriever.PERFORCE_NOTIFICATION_EMAIL_ENV_VAR}=example@example.com'"
            )
            should_exit = True

        if not config_retriever.perforce_key_pair_name:
            print(
                f"ERROR: Please run 'export {ConfigRetriever.PERFORCE_KEY_PAIR_NAME_ENV_VAR}=ec2_key_pair_name'"
            )
            should_exit = True

        if should_exit:
            sys.exit(1)
