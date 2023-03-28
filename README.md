# crowdstrike-ecs-cloudformation-samples
Add Falcon Sensor to your ECS workloads using CloudFormation templates.

## EC2 Cluster
The Falcon Sensor needs to be installed on each EC2 host. We can use do that by adding an [ECS Daemon Service](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/ecs_services.html#service_scheduler_daemon) to your ECS EC2 cluster.

### Pre-requisites
You will need to 
- Copy your CID from the falcon platform; Host setup and management > Deploy > Sensor downloads page
- Copy the falcon-sensor image for linux to your ECR registry using this [script](https://github.com/CrowdStrike/falcon-scripts/tree/main/bash/containers/falcon-container-sensor-pull).

You can run the following commands in 
- Upload templates to the [AWS GUI](https://console.aws.amazon.com/cloudformation/home?#/stacks/create)
- [AWS Cloudshell](https://ap-south-1.console.aws.amazon.com/cloudshell) or
- Your own environment

> If using AWS CLI, ensure the region is set correctly so the CloudFormation Stacks are run in the correct region.

### AWS CLI
```
# Get the templates
git clone https://github.com/TomRyan-321/crowdstrike-ecs-cloudformation-samples.git
cd crowdstrike-ecs-cloudformation-samples

# Configure
ECS_EC2_CLUSTER_NAME=your-ecs-cluster-name
FALCON_CID=XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX-XX
FALCON_FULL_IMAGE_PATH=1234567890.dkr.ecr.ap-southeast-1.amazonaws.com/falcon-sensor:6.46.0-14306.falcon-linux.x86_64.Release.US-2

# Example deploy with options in json file
aws cloudformation deploy \
    --stack-name falcon-ecs-ec2-daemon-$ECS_EC2_CLUSTER_NAME \
    --template-file falcon-ecs-ec2-daemon-template.yaml \
    --parameter-overrides file://falcon-ecs-ec2-daemon-parameters.json

# Example deploy with options in-line
aws cloudformation deploy \
    --stack-name falcon-ecs-ec2-daemon-$ECS_EC2_CLUSTER_NAME \
    --template-file falcon-ecs-ec2-daemon-template.yaml \
    --parameter-overrides \
        "ECSClusterName=$ECS_EC2_CLUSTER_NAME" \
        "CID=$FALCON_CID" \
        "FalconImagePath=$FALCON_FULL_IMAGE_PATH" \
        "TAGS=ecs-ec2-daemon,ecs-appname-1" \
        "Trace=warn"

# Remove falcon sensor Daemon
aws cloudformation delete-stack --stack-name falcon-ecs-ec2-daemon-$ECS_EC2_CLUSTER_NAME
```