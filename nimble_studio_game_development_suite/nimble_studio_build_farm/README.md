## Nimble Studio Build Farm

### Summary

This example deploys a complete stack which installs an Incredibuild server as well as supporting infrastructure for use within a Nimble Studio VPC.

### Setup

Follow the instructions in the main repository [README](https://github.com/aws-samples/nimblestudio-game-development-suite/blob/main/README.md) to set up
this GitHub package and python environment locally.

### Prerequisites

#### Incredibuild License

Place your Incredibuild License file in the `nimble_studio_game_development_suite/nimble_studio_build_farm/incredibuild` folder. 

You can download a free trial license from the [Incredibuild website](https://www.incredibuild.com/free-trial).

### Deploy

#### Terminal

All deployment commands must be executed inside the *nimble_studio_build_farm* folder, navigate there if you haven't already done so.

```bash
cd nimble_studio_game_development_suite/nimble_studio_build_farm
```

By default, the CDK will use the credentials and region that you configured earlier for the AWS CLI. If you want to override the region, you can `export AWS_REGION=<region>` prior to running the CDK.

Another option is to set the following environment variables for the app: 
* `CDK_DEFAULT_ACCOUNT` - AWS account to deploy resources into
* `CDK_DEFAULT_REGION` - AWS region to deploy resources into

Example:
```bash
export CDK_DEFAULT_ACCOUNT=123456789012
export CDK_DEFAULT_REGION=us-west-2
```

If you would like to take advantage of the Incredibuild worker farm, you can create your own AMI containing all of the software you require. Once created, you can set the following environment variable and redeploy, and your workers will use that AMI instead of the default Windows AMI:

Example:
```bash
export WORKER_AMI=ami-123456789012
```

You can also specify the instance type used by the Incredibuild Auto Scaling Group using the worker_instance_type environment variable:

Example:
```bash
export WORKER_INSTANCE_TYPE=c6a.4xlarge
```

#### CDK Bootstrap Environment

If you have already deployed using StudioBuilder, you can skip this step. If not, you will be required to [Bootstrap](https://docs.aws.amazon.com/cdk/latest/guide/bootstrapping.html) your environment - which creates an S3 bucket in your account. This will be created in the default account and region by running:

```bash
cdk bootstrap
```

You can specify the account and region by using the below command with your AWS account number.

```bash
cdk bootstrap aws://<account-number>/<region>
```

#### NimbleStudioBuildFarmStack Stack
1. Deploy the project using the following command in the root of the NimbleStudioBuildFarmStack folder 

```bash
cdk deploy NimbleStudioBuildFarmStack
```

### Configure

#### Launch Profiles

Deployment of the NimbleStudioBuildFarmStack stack will create an `Incredibuild` studio component resource, which will be available as a studio resource under custom configuration.

This component can be [associated with a Launch Profile](https://docs.aws.amazon.com/nimble-studio/latest/userguide/modifying-launch-profiles.html#modifying-launch-profiles-update) in order to automatically configure the Incredibuild coordinator URL on the Nimble streaming workstation environment.

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