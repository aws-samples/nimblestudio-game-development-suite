from aws_cdk import aws_sns as sns, aws_sns_subscriptions as subs
from constructs import Construct
from nimble_studio_perforce_server_stacks.nimble_studio_perforce_server_common_stack import (
    NimbleStudioPerforceServerCommonStack,
)


class NimbleStudioPerforceServerNotificationStack(
    NimbleStudioPerforceServerCommonStack
):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.perforce_sns_topic = sns.Topic(
            self, "PerforceServerSNSTopic", display_name=f"Perforce-Notifications-Topic"
        )

        self.perforce_sns_topic.add_subscription(
            subs.EmailSubscription(self._notification_email)
        )
