## Nimble Studio License Server

### Summary

This example deploys a complete CloudFormation stack which sets up a License Server for use with a Nimble Studio.

License server setup is based on Nimble Studio's [Create license server documentation](https://docs.aws.amazon.com/nimble-studio/latest/userguide/creating-license-server.html)

### Deploy

#### Terminal
All deployment commands must be executed inside this folder, navigate there if you haven't already done so.

```bash
cd nimble_studio_game_development_suite/nimble_studio_license_server
```

Set the environment variables for the app: 
* `CDK_DEFAULT_ACCOUNT` - AWS account to deploy resources into
* `CDK_DEFAULT_REGION` - AWS region to deploy resources into

Example:
```bash
export CDK_DEFAULT_ACCOUNT=123456789012
export CDK_DEFAULT_REGION=us-west-2
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
cdk deploy NimbleStudioLicenseServerStack
```

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