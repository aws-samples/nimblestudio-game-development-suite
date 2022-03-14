from aws_cdk import NestedStack, RemovalPolicy, aws_s3 as s3
from constructs import Construct


class SetupStack(NestedStack):
    def __init__(self, scope: Construct, id: str, **kwargs):
        super().__init__(scope, id, **kwargs)

        self.artifact_bucket = s3.Bucket(
            self, "JenkinsArtifactBucket", removal_policy=RemovalPolicy.DESTROY
        )
        self.ssm_logging_bucket = s3.Bucket(
            self, "SSMLoggingBucket", removal_policy=RemovalPolicy.DESTROY
        )
