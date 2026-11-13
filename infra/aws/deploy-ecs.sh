#!/usr/bin/env bash
# Deploy images already pushed to ECR. Keep Terraform for infrastructure and
# let this script own ECS task-definition revisions after the initial apply.
set -euo pipefail

if [[ $# -ne 2 || -z ${AWS_REGION:-} ]]; then
  echo "Usage: AWS_REGION=ap-southeast-1 $0 API_IMAGE WEB_IMAGE" >&2
  exit 2
fi

api_image=$1
web_image=$2
cluster=${ECS_CLUSTER:-warrantytrack}
service=${ECS_SERVICE:-warrantytrack}
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT

service_json=$(aws ecs describe-services --cluster "$cluster" --services "$service" --output json)
if [[ $(jq -r '.services[0].status // empty' <<< "$service_json") != ACTIVE ]]; then
  echo "ECS service $cluster/$service is not ACTIVE" >&2
  exit 1
fi

app_source=$(jq -r '.services[0].taskDefinition' <<< "$service_json")
jq -e '.services[0].networkConfiguration.awsvpcConfiguration' <<< "$service_json" \
  | jq '{awsvpcConfiguration: .}' > "$work/network.json"

render_task() {
  local source=$1 output=$2
  aws ecs describe-task-definition --task-definition "$source" --query taskDefinition --output json \
    | jq --arg api "$api_image" --arg web "$web_image" '
        del(.taskDefinitionArn, .revision, .status, .requiresAttributes,
            .compatibilities, .registeredAt, .registeredBy, .deregisteredAt)
        | .containerDefinitions |= map(
            if .name == "api" then .image = $api
            elif .name == "web" then .image = $web
            else . end)
      ' > "$output"
}

# Migrate with the new API image while the previous app revision still serves.
render_task "$cluster-job" "$work/job.json"
job_td=$(aws ecs register-task-definition --cli-input-json "file://$work/job.json" \
  --query 'taskDefinition.taskDefinitionArn' --output text)
job_task=$(aws ecs run-task --cluster "$cluster" --task-definition "$job_td" \
  --launch-type FARGATE --network-configuration "file://$work/network.json" \
  --query 'tasks[0].taskArn' --output text)
if [[ -z $job_task || $job_task == None ]]; then
  echo "Could not start the migration task" >&2
  exit 1
fi
aws ecs wait tasks-stopped --cluster "$cluster" --tasks "$job_task"
job_exit=$(aws ecs describe-tasks --cluster "$cluster" --tasks "$job_task" \
  --query 'tasks[0].containers[?name==`api`].exitCode | [0]' --output text)
if [[ $job_exit != 0 ]]; then
  echo "Migration task failed (exit $job_exit): $job_task" >&2
  exit 1
fi

render_task "$app_source" "$work/app.json"
app_td=$(aws ecs register-task-definition --cli-input-json "file://$work/app.json" \
  --query 'taskDefinition.taskDefinitionArn' --output text)
aws ecs update-service --cluster "$cluster" --service "$service" \
  --task-definition "$app_td" --query 'service.taskDefinition' --output text
aws ecs wait services-stable --cluster "$cluster" --services "$service"

alb_dns=$(aws elbv2 describe-load-balancers --names "$cluster" \
  --query 'LoadBalancers[0].DNSName' --output text)
curl --fail --silent --show-error --retry 8 --retry-delay 5 \
  "http://$alb_dns/api/health"
echo
echo "Deployed $app_td"
