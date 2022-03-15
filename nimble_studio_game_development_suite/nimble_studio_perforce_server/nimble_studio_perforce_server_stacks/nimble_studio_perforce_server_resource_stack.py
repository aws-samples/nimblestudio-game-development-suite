from aws_cdk import aws_nimblestudio as nimblestudio
from constructs import Construct
from nimble_studio_perforce_server_stacks.nimble_studio_perforce_server_common_stack import (
    NimbleStudioPerforceServerCommonStack,
    PERFORCE_SERVER_RECORD_PREFIX,
)


class NimbleStudioPerforceServerResourceStack(NimbleStudioPerforceServerCommonStack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        route53entry = f"{PERFORCE_SERVER_RECORD_PREFIX}{self._hosted_zone.zone_name}"

        perforce_configuration_script = f"""
        p4 set P4IGNORE=.p4ignore
        p4 set P4PORT=ssl:{route53entry}:1666"""

        cfn_studio_component = nimblestudio.CfnStudioComponent(
            self,
            "PerforceEnvConfigStudioComponent",
            name="PerforceEnvConfigStudioComponent",
            studio_id=self._studio_id,
            type="CUSTOM",
            initialization_scripts=[
                nimblestudio.CfnStudioComponent.StudioComponentInitializationScriptProperty(
                    launch_profile_protocol_version="2021-03-31",
                    platform="LINUX",
                    run_context="USER_INITIALIZATION",
                    script=perforce_configuration_script,
                ),
                nimblestudio.CfnStudioComponent.StudioComponentInitializationScriptProperty(
                    launch_profile_protocol_version="2021-03-31",
                    platform="WINDOWS",
                    run_context="USER_INITIALIZATION",
                    script=perforce_configuration_script,
                ),
            ],
        )
