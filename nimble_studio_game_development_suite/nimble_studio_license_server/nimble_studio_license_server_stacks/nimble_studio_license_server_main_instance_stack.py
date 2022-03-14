import os
from aws_cdk import (
    Stack,
    Tags,
    CfnTag,
    Environment,
    aws_ec2 as ec2,
    aws_iam as iam,
    aws_s3 as s3,
)
from constructs import Construct
from nimble_studio_license_server_stacks.constants import Constants

import sys

sys.path.append("../../utils")
from utils.config_retriever import ConfigRetriever

ACCOUNT = os.environ.get("CDK_DEFAULT_ACCOUNT", "111111111111")
REGION = os.environ.get("CDK_DEFAULT_REGION", "us-west-2")

AWS_ENV = Environment(account=ACCOUNT, region=REGION)


class NimbleStudioLicenseServerMainInstanceStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, env=AWS_ENV, **kwargs)

        config_retriever = ConfigRetriever()
        studio_license_bucket = s3.Bucket(
            self,
            Constants.BUCKET_NAME,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
        )

        license_server_s3_bucket_access_policy = iam.ManagedPolicy(
            self,
            "licenseServerS3BucketAccess",
            managed_policy_name="licenseServerS3BucketAccess",
            statements=[
                iam.PolicyStatement(
                    actions=[
                        "s3:ListBucket",
                    ],
                    effect=iam.Effect.ALLOW,
                    resources=[studio_license_bucket.bucket_arn],
                ),
                iam.PolicyStatement(
                    actions=["s3:GetObject"],
                    effect=iam.Effect.ALLOW,
                    resources=[studio_license_bucket.bucket_arn + "/*"],
                ),
            ],
        )

        nimble_studio_license_server_role = iam.Role(
            self,
            "Nimble_Studio_LicenseServer",
            role_name="Nimble_Studio_LicenseServer",
            assumed_by=iam.ServicePrincipal("ec2.amazonaws.com"),
        )

        nimble_studio_license_server_role.add_managed_policy(
            license_server_s3_bucket_access_policy
        )
        nimble_studio_license_server_role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name(
                "AmazonSSMManagedInstanceCore"
            )
        )

        linux_image = ec2.MachineImage.latest_amazon_linux(
            generation=ec2.AmazonLinuxGeneration.AMAZON_LINUX_2
        )
        license_server_security_group = ec2.SecurityGroup.from_security_group_id(
            self,
            "license_server_security_group",
            config_retriever.license_server_security_group_id,
        )

        root_block_device = ec2.BlockDevice(
            device_name="/dev/sda1",
            volume=ec2.BlockDeviceVolume.ebs(
                volume_type=ec2.EbsDeviceVolumeType.GP2,
                volume_size=100,
                delete_on_termination=True,
            ),
        )

        self._subnet: ec2.ISubnet = ec2.Subnet.from_subnet_attributes(
            self,
            "subnet",
            subnet_id=config_retriever.worker_support_subnet_id,
            availability_zone=config_retriever.worker_support_subnet_az,
        )

        nimble_studio_license_server_instance = ec2.Instance(
            self,
            "NimbleStudioLicenseServerInstance",
            role=nimble_studio_license_server_role,
            machine_image=linux_image,
            instance_type=ec2.InstanceType("t3.medium"),
            vpc=ec2.Vpc.from_lookup(self, "vpc", vpc_id=config_retriever.vpc_id),
            vpc_subnets=ec2.SubnetSelection(subnets=[self._subnet]),
            security_group=license_server_security_group,
            block_devices=[root_block_device],
        )

        Tags.of(nimble_studio_license_server_instance).add(
            "Name",
            f"{config_retriever.studio_name}_licenseServer",
        )

        license_server_network_interface = ec2.CfnNetworkInterface(
            self,
            "license_server_network_interface",
            subnet_id=config_retriever.worker_support_subnet_id,
            description="License Server Network Interface",
            group_set=[config_retriever.license_server_security_group_id],
            tags=[CfnTag(key="Name", value="LicenseServerNetworkInterface")],
        )

        license_server_network_interface_attachment = ec2.CfnNetworkInterfaceAttachment(
            self,
            "license_server_network_interface_attachment",
            device_index="1",
            instance_id=nimble_studio_license_server_instance.instance_id,
            network_interface_id=license_server_network_interface.attr_id,
        )
