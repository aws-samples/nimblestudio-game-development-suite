from aws_cdk import aws_iam as iam, aws_s3 as s3
from constructs import Construct

def create_ssm_policy(scope: Construct, ssm_log_bucket: s3.IBucket):
    return iam.Policy(
        scope=scope,
        id=f"SSMPolicy",
        document=iam.PolicyDocument(
            statements=[
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    resources=["*"],
                    actions=[
                        "ssmmessages:CreateControlChannel",
                        "ssmmessages:CreateDataChannel",
                        "ssmmessages:OpenControlChannel",
                        "ssmmessages:OpenDataChannel",
                        "ssm:UpdateInstanceInformation",
                    ],
                ),
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    resources=[ssm_log_bucket.bucket_arn],
                    actions=["s3:PutObject"],
                ),
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    resources=["*"],
                    actions=[
                        "logs:CreateLogStream",
                        "logs:PutLogEvents",
                        "logs:DescribeLogGroups",
                        "logs:DescribeLogStreams",
                    ],
                ),
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    resources=["*"],
                    actions=["s3:GetEncryptionConfiguration"],
                ),
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    resources=["*"],
                    actions=["kms:GenerateDataKey"],
                ),
            ]
        ),
    )

def replace_user_data_values(user_data: str, replacement_map: dict) -> str:
    """Replaces userdata with a map of replacement_map.key -> replacement_map.value"""
    for key, value in replacement_map.items():
        user_data = user_data.replace(key, value)
    return user_data
