import boto3
import json
import http.client
import urllib.parse
from botocore.exceptions import ClientError

ecs = boto3.client("ecs")


def handler(event, context):
    # Print incoming request event for debugging
    print("Received event:", json.dumps(event, indent=4))

    request_type = event["RequestType"]

    if request_type != "Delete":
        print(f"Ignoring {request_type} event.")
        send_response(
            event,
            context,
            "SUCCESS",
            "Non Delete event type receieved, no cleanup required.",
        )
    elif request_type == "Delete":
        print("Cleanup triggered after ECS Service deletion.")

        # Get properties from event
        cluster_name = event["ResourceProperties"].get("ClusterName")
        task_definition = event["ResourceProperties"].get("TaskDefinition")

        # Check if cluster still exists
        try:
            ecs.describe_clusters(clusters=[cluster_name])
        except ClientError as e:
            if e.response["Error"]["Code"] == "ClusterNotFoundException":
                print(f"Cluster {cluster_name} not found.")
                send_response(
                    event, context, "SUCCESS", "Cluster not found. No cleanup required."
                )
        else:
            log_and_fail(event, context, e)

        # List all container instances in the ECS cluster
        try:
            instance_arns = ecs.list_container_instances(cluster=cluster_name)[
                "containerInstanceArns"
            ]
            # If no container instances are found, exit
            if not instance_arns:
                print("No container instances found in cluster. No cleanup necessary.")
                send_response(
                    event,
                    context,
                    "SUCCESS",
                    "No container instances found. No cleanup necessary.",
                )
                return
            num_instances = len(instance_arns)
        except ClientError as e:
            log_and_fail(event, context, e)



        # Describe container instances
        try:
            container_details = ecs.describe_container_instances(
                cluster=cluster_name, containerInstances=instance_arns
            )["containerInstances"]
        except ClientError as e:
            log_and_fail(event, context, e)

        # Collect running instance IDs and add custom attribute for cleanup job to execute
        instance_ids = []
        for container in container_details:
            if container["status"] == "ACTIVE":
                instance_id = container["ec2InstanceId"]
                container_instance_arn = container["containerInstanceArn"]
                instance_ids.append(instance_id)

                # Register custom attribute for the instance ID
                print(f"Registering custom attribute for instance ID: {instance_id}")
                try:
                    response = ecs.put_attributes(
                        cluster=cluster_name,
                        attributes=[
                            {
                                'name': 'instanceId',
                                'value': instance_id,
                                'targetType': 'container-instance',
                                'targetId': container_instance_arn,
                            }
                        ],
                    )
                    print(
                        f"Successfully register attribute for instance {instance_id}."
                    )
                except ClientError as e:
                    print(
                        f"Failed to register attribute for instance {instance_id}: {e}"
                    )

        # Log active instance IDs
        print(f"Active instances in the cluster: {instance_ids}")

        # Check if there are active instances to run task
        if not instance_ids:
            print("No active instances found in the cluster. No cleanup tasks to run.")
            send_response(
                event,
                context,
                "SUCCESS",
                "No active instances found. No cleanup required.",
            )
            return

        # Run the cleanup task on each instance
        for instance_id in instance_ids:
            try:
                response = ecs.run_task(
                    cluster=cluster_name,
                    taskDefinition=task_definition,
                    count=1,
                    placementConstraints=[
                        {
                            "type": "memberOf",
                            "expression": f"attribute:instanceId == {instance_id}",
                        }
                    ],
                    launchType="EC2",
                )
                print(f"Clean task triggered on instance {instance_id}: {response}")
            except ClientError as e:
                print(f"Failed to run task on instance {instance_id}: {e}")
                continue  # Log but continue to next instance

        print(f"Cleanup tasks triggered on {len(instance_ids)} instances.")
        send_response(
            event,
            context,
            "SUCCESS",
            f"Cleanup tasks triggered on {len(instance_ids)} instances.",
        )
    else:
        print(f"Unknown event type: {request_type}")
        send_response(event, context, "FAILED", "Unknown request type.")


def send_response(event, context, response_status, reason):
    response_body = json.dumps(
        {
            "Status": response_status,
            "Reason": reason,
            "PhysicalResourceId": context.log_stream_name,
            "StackId": event["StackId"],
            "RequestId": event["RequestId"],
            "LogicalResourceId": event["LogicalResourceId"],
        }
    )

    # Parse the response URL
    response_url = urllib.parse.urlparse(event["ResponseURL"])

    # Set up the connection to the pre-signed URL
    connection = http.client.HTTPSConnection(response_url.hostname)

    headers = {"Content-Type": "", "Content-Length": str(len(response_body))}

    # Send the PUT request to the pre-signed S3 URL
    connection.request(
        "PUT",
        response_url.path + "?" + response_url.query,
        body=response_body,
        headers=headers,
    )

    response = connection.getresponse()
    print(f"Response sent with status code {response.status}")
    connection.close()


def log_and_fail(event, context, error):
    print(f"Response sent with status code {error}")
    send_response(event, context, "FAILED", str(error))
