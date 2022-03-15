## NimbleStudioBuildPipeline

### Summary

This example deploys a stack which sets up a [Jenkins](https://www.jenkins.io/) server and build node for use with Nimble Studio.

### Deploy

#### Terminal

All deployment commands must be executed inside the *repo* folder, navigate there if you haven't already done so.

```bash
 cd nimble_studio_game_development_suite/nimble_studio_build_pipeline
```

Set the Environment variables for the app:

* `CDK_BUILD_PIPELINE_KEY_PAIR_NAME` - EC2 key pair to use with the Jenkins Server instances
* `CDK_JENKINS_BUILD_NODE_AMI_ID` - EC2 AMI ID to use for launching the Jenkins build node

```bash
export CDK_BUILD_PIPELINE_KEY_PAIR_NAME=ec2_key_pair_name
export CDK_JENKINS_BUILD_NODE_AMI_ID=ami-00000000000000000
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

#### NimbleStudioBuildPipeline Stack
1. Deploy the project using the following command in the root of the nimble_studio_build_pipeline folder 

```bash
cdk deploy "*"
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