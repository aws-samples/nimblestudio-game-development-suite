#!/usr/bin/env python3
import os

from aws_cdk import App, Environment

from nimblestudio.constructs.build_farm import NimbleStudioBuildFarmStack

app = App()

# If you don't specify 'env', this stack will be environment-agnostic.
# Account/Region-dependent features and context lookups will not work,
# but a single synthesized template can be deployed anywhere.

# Uncomment the next line to specialize this stack for the AWS Account
# and Region that are implied by the current CLI configuration.
environment = Environment(
    account=os.getenv("CDK_DEFAULT_ACCOUNT"), region=os.getenv("CDK_DEFAULT_REGION")
)

build_farm_stack = NimbleStudioBuildFarmStack(
    app, "NimbleStudioBuildFarm", env=environment
)

app.synth()
