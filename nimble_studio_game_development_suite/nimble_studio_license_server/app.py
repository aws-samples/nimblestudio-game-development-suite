#!/usr/bin/env python3
from aws_cdk import App

from nimble_studio_license_server_stacks.nimble_studio_license_server_main_instance_stack import (
    NimbleStudioLicenseServerMainInstanceStack,
)

app = App()
NimbleStudioLicenseServerMainInstanceStack(
    app,
    "NimbleStudioLicenseServerStack",
    description="A stack created for running a License Server on AWS with Nimble Studio",
)
app.synth()
