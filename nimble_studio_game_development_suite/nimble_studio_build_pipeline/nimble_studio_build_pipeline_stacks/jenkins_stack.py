from aws_cdk import (
    NestedStack,
    aws_ec2 as ec2,
    aws_route53 as r53,
    aws_s3 as s3,
)
from constructs import Construct
from typing import List
from nimble_studio_build_pipeline.patterns.jenkins_pattern import JenkinsPattern


class JenkinsStack(NestedStack):
    def __init__(
        self,
        scope: Construct,
        id: str,
        vpc: ec2.IVpc,
        subnet: ec2.ISubnet,
        hosted_zone: r53.IHostedZone,
        key_name: str,
        vpce_security_group: ec2.ISecurityGroup or None,
        perforce_security_group: ec2.ISecurityGroup or None,
        allow_access_from: List[ec2.IPeer],
        build_node_security_group: ec2.ISecurityGroup,
        ssm_logging_bucket: s3.IBucket,
        **kwargs,
    ):
        super().__init__(scope, id, **kwargs)

        jenkins_security_group: ec2.ISecurityGroup = ec2.SecurityGroup(
            self, "JenkinsSG", vpc=vpc
        )

        if vpce_security_group:
            vpce_security_group.add_ingress_rule(
                jenkins_security_group,
                ec2.Port.tcp(443),
                description=f"from {jenkins_security_group.unique_id}:443",
            )

        if perforce_security_group:
            perforce_security_group.add_ingress_rule(
                jenkins_security_group,
                ec2.Port.tcp(1666),
                description=f"from {jenkins_security_group.unique_id}:1666",
            )

        self.jenkins: JenkinsPattern = JenkinsPattern(
            self,
            "Jenkins",
            stack_name=self.stack_name,
            region=self.region,
            studio_vpc=vpc,
            subnet=subnet,
            key_name=key_name,
            security_group=jenkins_security_group,
            allow_access_from=allow_access_from,
            build_node_security_group=build_node_security_group,
            ssm_logging_bucket=ssm_logging_bucket,
        )

        jenkins_instance: ec2.Instance = self.jenkins.instance

        self.jenkins_record = r53.ARecord(
            self,
            "JenkinsRecord",
            zone=hosted_zone,
            record_name=f"jenkins.{hosted_zone.zone_name}",
            target=r53.RecordTarget.from_ip_addresses(
                jenkins_instance.instance_private_ip
            ),
        )
