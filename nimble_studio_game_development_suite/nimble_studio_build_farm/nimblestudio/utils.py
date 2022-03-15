from aws_cdk import Stack
from aws_cdk.aws_ec2 import UserData
from aws_cdk.aws_iam import Role
from aws_cdk.aws_s3 import Bucket
from aws_cdk.aws_ssm import StringParameter

import boto3
from botocore import exceptions


def is_valid_instance_type(instance_type: str):
    client = boto3.client("ec2")

    try:
        client.describe_instance_types(InstanceTypes=[instance_type])
    except exceptions.ClientError as e:
        if e.response["Error"]["Code"] == "InvalidInstanceType":
            print(f"{instance_type} is not a valid instance type.")
            return False

    return True


def add_user_data_cloudwatch_agent(
    stack: Stack,
    user_data: UserData,
    *,
    cloudwatch_ssm_param: StringParameter,
    instance_role: Role,
) -> None:
    # Firstly we need to give ourselves access to the CloudWatch agent s3 bucket
    cloudwatch_agent_bucket_name = f"amazoncloudwatch-agent-{Stack.of(stack).region}"
    cloudwatch_agent_bucket = Bucket.from_bucket_arn(
        stack,
        "CloudWatchAgentBucket",
        f"arn:aws:s3:::{cloudwatch_agent_bucket_name}",
    )
    cloudwatch_agent_bucket.grant_read(instance_role)

    # Now we'll setup the CloudWatch agent
    cloudwatch_agent_bucket_key = "windows/amd64/latest/amazon-cloudwatch-agent.msi"
    cloudwatch_agent_installer_path = r"C:\temp\amazon-cloudwatch-agent.msi"
    cloudwatch_agent_ctl_path = (
        r"C:\Program Files\Amazon\AmazonCloudWatchAgent\amazon-cloudwatch-agent-ctl.ps1"
    )

    user_data.add_s3_download_command(
        bucket=cloudwatch_agent_bucket,
        bucket_key=cloudwatch_agent_bucket_key,
        local_file=cloudwatch_agent_installer_path,
    )
    user_data.add_commands(
        f"Start-process msiexec -Wait -ArgumentList /i, {cloudwatch_agent_installer_path}"
    )
    user_data.add_commands(
        f'& "{cloudwatch_agent_ctl_path}" -a append-config -m ec2 -c ssm:{cloudwatch_ssm_param.parameter_name} -s'
    )
