from aws_cdk import (
    CfnOutput,
    Stack,
    aws_ec2 as ec2,
    aws_route53 as r53,
)
from nimble_studio_build_pipeline_stacks.build_node_image_stack import (
    BuildNodeImageStack,
)
from constructs import Construct
from nimble_studio_build_pipeline_stacks.jenkins_stack import JenkinsStack
from nimble_studio_build_pipeline_stacks.setup_stack import SetupStack

import sys

sys.path.append("../../utils")
from utils.config_retriever import ConfigRetriever


class NimbleStudioBuildPipelineStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:

        super().__init__(scope, construct_id, **kwargs)

        config_retriever = ConfigRetriever()

        self._validate_config(config_retriever=config_retriever)

        vpc: ec2.IVpc = ec2.Vpc.from_lookup(
            self, "StudioVPC", vpc_id=config_retriever.vpc_id
        )

        # Lookup our pre-created Subnet by ID and AZ
        subnet: ec2.ISubnet = ec2.Subnet.from_subnet_attributes(
            self,
            "Subnet",
            subnet_id=config_retriever.worker_support_subnet_id,
            availability_zone=config_retriever.worker_support_subnet_az,
        )

        hosted_zone: r53.IHostedZone = r53.HostedZone.from_hosted_zone_attributes(
            self,
            "HostedZone",
            hosted_zone_id=config_retriever.hosted_zone["id"],
            zone_name=config_retriever.hosted_zone["name"],
        )

        # Lookup our pre-created VPC Endpoints Security Group by ID if it exists
        vpce_sg = None
        if config_retriever.vpce_sg_id:
            vpce_sg: ec2.ISecurityGroup = ec2.SecurityGroup.from_security_group_id(
                self, "VPCESecurityGroup", security_group_id=config_retriever.vpce_sg_id
            )

        perforce_sg = None
        if config_retriever.perforce_sg_id:
            perforce_sg: ec2.ISecurityGroup = ec2.SecurityGroup.from_security_group_id(
                self,
                "PerforceSecurityGroup",
                security_group_id=config_retriever.perforce_sg_id,
            )

        workstations_sg: ec2.ISecurityGroup = ec2.SecurityGroup.from_security_group_id(
            self,
            "WorkstationsSecurityGroup",
            security_group_id=config_retriever.workstations_sg_id,
        )

        setup_stack = SetupStack(self, "SetupStack")

        artifact_bucket = setup_stack.artifact_bucket
        ssm_logging_bucket = setup_stack.ssm_logging_bucket

        allow_access_from = [workstations_sg]

        build_node_image_stack = BuildNodeImageStack(
            self,
            "BuildNodeImageStack",
            vpc=vpc,
            subnet=subnet,
            ami_id=config_retriever.build_node_ami_id,
            key_name=config_retriever.jenkins_key_pair_name,
            vpce_security_group=vpce_sg,
            perforce_security_group=perforce_sg,
            artifact_bucket=artifact_bucket,
            allow_access_from=allow_access_from,
            ssm_log_bucket=ssm_logging_bucket,
        )
        build_node_image_stack.add_dependency(setup_stack)

        jenkins_stack: Stack = JenkinsStack(
            self,
            "JenkinsStack",
            vpc=vpc,
            subnet=subnet,
            hosted_zone=hosted_zone,
            key_name=config_retriever.jenkins_key_pair_name,
            vpce_security_group=vpce_sg,
            perforce_security_group=perforce_sg,
            allow_access_from=allow_access_from,
            build_node_security_group=build_node_image_stack.build_node_instance_sg,
            ssm_logging_bucket=ssm_logging_bucket,
        )

        jenkins_stack.add_dependency(target=build_node_image_stack)

        CfnOutput(
            self,
            "JenkinsRecordName",
            value=jenkins_stack.jenkins_record.domain_name,
        )

    def _validate_config(self, config_retriever: ConfigRetriever):
        should_exit = False
        if config_retriever.jenkins_key_pair_name == "":
            print(
                "ERROR: Please run 'export CDK_BUILD_PIPELINE_KEY_PAIR_NAME=ec2_key_pair_name'"
            )
            should_exit = True

        if config_retriever.build_node_ami_id == "":
            print(
                "ERROR: Jenkins build node AMI ID could not be determined. Please run 'export CDK_JENKINS_BUILD_NODE_AMI_ID=<ami_id>'"
            )
            should_exit = True

        if should_exit:
            sys.exit(1)
