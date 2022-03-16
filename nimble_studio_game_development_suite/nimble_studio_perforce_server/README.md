## Nimble Studio Perforce Server

### Summary

This example deploys a complete stack which sets up a Perforce Server for use with a Nimble Studio.

Server setup is based on Perforce's [Enhanced Studio Pack for AWS](https://www.perforce.com/products/helix-core/install-enhanced-studio-pack-aws)

### License

This application performs a download and setup of Perforce Helix Core and Perforce Helix Swarm on EC2 instances during the deployment process. Perforce Helix Core and Perforce Helix Swarm are proprietary software and are subject to the terms and conditions of Perforce. Please refer to EULA in the following page for details.

[Perforce Terms of Use](https://www.perforce.com/terms-use)

You may bring your own Perforce License for use with this application. Refer to the 
[Perforce documentation on licensing](https://www.perforce.com/resources/vcs/cloud-version-control-guide#licensing).

### Deploy

#### Terminal
All deployment commands must be executed inside the *nimble_studio_perforce_server* folder, navigate there if you haven't already done so.

```bash
cd nimble_studio_game_development_suite/nimble_studio_perforce_server
```

Set the environment variables for the app: 
* `CDK_DEFAULT_ACCOUNT` - AWS account to deploy resources into
* `CDK_DEFAULT_REGION` - AWS region to deploy resources into
* `CDK_PERFORCE_NOTIFICATION_EMAIL` - Email address to be notified of alerts from the Perforce Server
* `CDK_PERFORCE_KEY_PAIR_NAME` - EC2 key pair to use with the Perforce Server instances

Example:
```bash
export CDK_DEFAULT_ACCOUNT=123456789012
export CDK_DEFAULT_REGION=us-west-2
export CDK_PERFORCE_NOTIFICATION_EMAIL=example@example.com
export CDK_PERFORCE_KEY_PAIR_NAME=ec2_key_pair_name
```

At this point you can now synthesize the CloudFormation template for this code.

```
$ cdk synth
```

#### CDK Bootstrap Environment

This sample uses features of the AWS CDK that require you to [Bootstrap](https://docs.aws.amazon.com/cdk/latest/guide/bootstrapping.html) your environment (a combination of an AWS account and region). The sample is configured to use us-west-2 (Oregon), so you will just need to replace the placeholder in the below command with your AWS account number.

```bash
cdk bootstrap aws://ACCOUNT-NUMBER-1/us-west-2
```

#### NimbleStudioPerforceServer Stack
1. Deploy the project using the following command from within this folder 

```bash
cdk deploy NimbleStudioPerforceServerStack
```

### Configure

#### Launch Profiles

Deployment of the NimbleStudioPerforceServer stack will create a `PerforceEnvConfigStudioComponent` resource, which will be available as a studio resource under custom configuration.

This component can be [associated with a Launch Profile](https://docs.aws.amazon.com/nimble-studio/latest/userguide/modifying-launch-profiles.html#modifying-launch-profiles-update) that has a streaming image with the Perforce client installed, in order to automatically configure the Nimble streaming workstation environment for [P4_PORT](https://www.perforce.com/manuals/cmdref/Content/CmdRef/P4PORT.html) and [P4IGNORE](https://www.perforce.com/manuals/cmdref/Content/CmdRef/P4IGNORE.html).

### Development

To add additional dependencies, for example other CDK libraries, just add
them to your `setup.py` file and rerun the `pip install -r requirements.txt`
command.

#### Useful commands

* `cdk ls`          list all stacks in the app
* `cdk synth`       emits the synthesized CloudFormation template
* `cdk deploy`      deploy this stack to your default AWS account/region
* `cdk diff`        compare deployed stack with current state
* `cdk docs`        open CDK documentation

Enjoy!
