from aws_cdk import CfnOutput, Stack, Environment
from constructs import Construct
import os

from nimble_studio_perforce_server_stacks.nimble_studio_perforce_server_network_stack import (
    NimbleStudioPerforceServerNetworkStack,
)
from nimble_studio_perforce_server_stacks.nimble_studio_perforce_server_notification_stack import (
    NimbleStudioPerforceServerNotificationStack,
)
from nimble_studio_perforce_server_stacks.nimble_studio_perforce_server_iam_stack import (
    NimbleStudioPerforceServerIamStack,
)
from nimble_studio_perforce_server_stacks.nimble_studio_perforce_server_main_instance_stack import (
    NimbleStudioPerforceServerMainInstanceStack,
)
from nimble_studio_perforce_server_stacks.nimble_studio_perforce_server_swarm_instance_stack import (
    NimbleStudioPerforceServerSwarmInstanceStack,
)
from nimble_studio_perforce_server_stacks.nimble_studio_perforce_server_resource_stack import (
    NimbleStudioPerforceServerResourceStack,
)


# default values here for testing build synthesis
ACCOUNT = os.environ.get("CDK_DEFAULT_ACCOUNT", "111111111111")
REGION = os.environ.get("CDK_DEFAULT_REGION", "us-west-2")
VPC_ID = os.environ.get("CDK_STUDIO_VPC_ID", "vpc-11111111111111111")

AWS_ENV = Environment(account=ACCOUNT, region=REGION)


class NimbleStudioPerforceServerStack(Stack):
    """
    Root CDK stack for Perforce Server
    """

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, env=AWS_ENV, **kwargs)

        network_stack = NimbleStudioPerforceServerNetworkStack(
            self, "NimbleStudioPerforceServerNetworkStack"
        )

        notification_stack = NimbleStudioPerforceServerNotificationStack(
            self, "NimbleStudioPerforceServerNotificationStack"
        )

        iam_stack = NimbleStudioPerforceServerIamStack(
            self,
            "NimbleStudioPerforceServerIamStack",
            sns_topic_arn=notification_stack.perforce_sns_topic.topic_arn,
        )
        iam_stack.add_dependency(notification_stack)

        main_instance_stack = NimbleStudioPerforceServerMainInstanceStack(
            self,
            "NimbleStudioPerforceServerMainInstanceStack",
            security_group=network_stack.perforce_server_security_group,
            ec2_role=iam_stack.ec2_role,
            secret=iam_stack.secret,
            sns_topic_arn=notification_stack.perforce_sns_topic.topic_arn,
        )
        main_instance_stack.add_dependency(iam_stack)

        swarm_instance_stack = NimbleStudioPerforceServerSwarmInstanceStack(
            self,
            "NimbleStudioPerforceServerSwarmInstanceStack",
            security_group=network_stack.perforce_server_security_group,
            ec2_role=iam_stack.ec2_role,
            secret=iam_stack.secret,
        )
        swarm_instance_stack.add_dependency(main_instance_stack)

        resource_stack = NimbleStudioPerforceServerResourceStack(
            self, "NimbleStudioPerforceServerResourceStack"
        )
        resource_stack.add_dependency(main_instance_stack)

        CfnOutput(
            self,
            "HelixCoreInstanceID",
            value=main_instance_stack.perforce_server_instance_main.instance_id,
        )
        CfnOutput(
            self,
            "P4CommitPrivateIp",
            value=main_instance_stack.perforce_server_instance_main.instance_private_ip,
        )
        CfnOutput(
            self,
            "P4PrivateRecordName",
            value=main_instance_stack.perforce_server_record.domain_name,
        )
        CfnOutput(
            self,
            "SwarmPrivateRecordName",
            value=swarm_instance_stack.perforce_swarm_record.domain_name,
        )
