from aws_cdk import (
    NestedStack,
    Tags,
    aws_ec2 as ec2,
    aws_iam as iam,
    aws_s3 as s3,
)
from constructs import Construct
from typing import List
import sys

sys.path.append("../../utils")
from utils.utils import (
    create_ssm_policy,
    replace_user_data_values,
)


class BuildNodeImageStack(NestedStack):
    def __init__(
        self,
        scope: Construct,
        id: str,
        vpc: ec2.IVpc,
        subnet: ec2.ISubnet,
        ami_id: str,
        key_name: str,
        vpce_security_group: ec2.ISecurityGroup or None,
        perforce_security_group: ec2.ISecurityGroup or None,
        artifact_bucket: s3.IBucket,
        allow_access_from: List[ec2.IPeer],
        ssm_log_bucket: s3.IBucket,
        **kwargs,
    ):
        super().__init__(scope, id, **kwargs)

        self.build_instance_role: iam.IRole = iam.Role(
            self,
            "BuildInstanceRole",
            assumed_by=iam.ServicePrincipal("ec2.amazonaws.com"),
        )

        artifact_bucket.grant_put(self.build_instance_role)
        self.build_instance_role.attach_inline_policy(
            create_ssm_policy(self, ssm_log_bucket)
        )
        self.build_instance_role.add_managed_policy(
            iam.ManagedPolicy.from_managed_policy_arn(
                self,
                "SSMManagedInstanceManagedPolicy",
                "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore",
            )
        )

        self.build_node_instance_sg = ec2.SecurityGroup(
            self,
            "BuildInstanceSG",
            vpc=vpc,
            security_group_name="JenkinsBuildInstanceSG",
        )

        if vpce_security_group:
            vpce_security_group.add_ingress_rule(
                self.build_node_instance_sg,
                ec2.Port.tcp(443),
                description=f"from {self.build_node_instance_sg.unique_id}:443",
            )

        if perforce_security_group:
            perforce_security_group.add_ingress_rule(
                self.build_node_instance_sg,
                ec2.Port.tcp(1666),
                description=f"from {self.build_node_instance_sg.unique_id}:1666",
            )

        for peer in allow_access_from:
            self.build_node_instance_sg.add_ingress_rule(
                peer, ec2.Port.tcp(3389), description="Allow RDP access"
            )

        instance_type: ec2.InstanceType = ec2.InstanceType.of(
            ec2.InstanceClass.COMPUTE5, ec2.InstanceSize.XLARGE4
        )

        machine_image: ec2.MachineImage = ec2.MachineImage.generic_windows(
            ami_map={self.region: ami_id}
        )

        self.build_node_instance_sg.add_ingress_rule(
            peer=ec2.Peer.ipv4(vpc.vpc_cidr_block),
            connection=ec2.Port.tcp(50000),
            description="Allow port 50000 access from VPC CIDR",
        )

        build_node_block_device: ec2.BlockDevice = ec2.BlockDevice(
            device_name="/dev/sda1",
            volume=ec2.BlockDeviceVolume(
                ebs_device=ec2.EbsDeviceProps(
                    volume_size=500, volume_type=ec2.EbsDeviceVolumeType.GP3
                )
            ),
        )

        # Read UserData Script and replace placeholders
        with open("assets/setup-build-node-instance.ps1", "r") as user_data_file:
            user_data = user_data_file.read()

        user_data_replacement_map = {
            "ARTIFACT_BUCKET_ARN_PLACEHOLDER": artifact_bucket.bucket_arn
        }
        user_data = replace_user_data_values(
            user_data=user_data, replacement_map=user_data_replacement_map
        )

        self.instance: ec2.IInstance = ec2.Instance(
            self,
            "JenkinsBuildNode",
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(subnets=[subnet]),
            instance_type=instance_type,
            machine_image=machine_image,
            user_data=ec2.UserData.custom(user_data),
            role=self.build_instance_role,
            block_devices=[build_node_block_device],
            security_group=self.build_node_instance_sg,
            key_name=key_name,
        )
        Tags.of(self.instance).add("Name", "JenkinsBuildNode")
