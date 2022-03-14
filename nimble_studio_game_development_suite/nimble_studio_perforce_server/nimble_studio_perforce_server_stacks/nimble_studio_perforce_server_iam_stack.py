from aws_cdk import Tags, aws_iam as iam, aws_secretsmanager as secretsmanager
from constructs import Construct
from nimble_studio_perforce_server_stacks.nimble_studio_perforce_server_common_stack import (
    NimbleStudioPerforceServerCommonStack,
)


class NimbleStudioPerforceServerIamStack(NimbleStudioPerforceServerCommonStack):
    def __init__(
        self, scope: Construct, construct_id: str, sns_topic_arn: str, **kwargs
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        perforce_sns_publish_managed_policy = iam.ManagedPolicy(
            self,
            "PerforceServerSNSPublishManagedPolicy",
            description="Policy to allow EC2 instances access to publish alerts to Perforce SNS topic",
            statements=[
                iam.PolicyStatement(
                    actions=["sns:Publish"],
                    effect=iam.Effect.ALLOW,
                    resources=[sns_topic_arn],
                )
            ],
        )

        self.ec2_role = iam.Role(
            self,
            "PerforceServerEC2Role",
            assumed_by=iam.ServicePrincipal("ec2.amazonaws.com"),
            description="Perforce Server EC2 service role for access to AWS APIs",
            managed_policies=[
                iam.ManagedPolicy.from_managed_policy_arn(
                    self,
                    "S3ReadOnlyManagedPolicy",
                    "arn:aws:iam::aws:policy/AmazonS3ReadOnlyAccess",
                ),
                iam.ManagedPolicy.from_managed_policy_arn(
                    self,
                    "SSMManagedInstanceManagedPolicy",
                    "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore",
                ),
                perforce_sns_publish_managed_policy,
            ],
        )

        Tags.of(self.ec2_role).add("Name", f"{self._stage}-Perforce-Role")

        secret_generator = secretsmanager.SecretStringGenerator(
            exclude_characters="'\"",
            exclude_punctuation=True,
            include_space=False,
            password_length=32,
        )

        self.secret = secretsmanager.Secret(
            self,
            "PerforceHelixCorePassword",
            description="Perforce Helix Core Password",
            generate_secret_string=secret_generator,
        )
        self.secret.grant_read(self.ec2_role)
