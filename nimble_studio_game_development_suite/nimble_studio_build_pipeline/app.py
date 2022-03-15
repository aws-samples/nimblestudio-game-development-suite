#!/usr/bin/env python3
from aws_cdk import App, Environment
import os

from nimble_studio_build_pipeline_stacks.nimble_studio_build_pipeline_stack import (
    NimbleStudioBuildPipelineStack,
)

app = App()
NimbleStudioBuildPipelineStack(
    app,
    "NimbleStudioBuildPipelineStack",
    env=Environment(
        account=os.getenv("CDK_DEFAULT_ACCOUNT"), region=os.getenv("CDK_DEFAULT_REGION")
    ),
)

app.synth()
