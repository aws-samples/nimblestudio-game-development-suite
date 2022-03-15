#!/usr/bin/env python3

from aws_cdk import App

from nimble_studio_perforce_server_stacks.nimble_studio_perforce_server_stack import (
    NimbleStudioPerforceServerStack,
)

app = App()
NimbleStudioPerforceServerStack(
    app,
    "NimbleStudioPerforceServerStack",
    description="A stack created for running a Perforce Server on AWS with Nimble Studio",
)
app.synth()
