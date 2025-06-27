# OpenAPI Specifications for CloudFormation Generator

This directory contains OpenAPI specifications for the Lambda functions that are used as action groups in the Amazon Bedrock agent.

## Files

- `initial-lambda-openapi.yaml`: OpenAPI specification for the Initial Lambda function that starts CloudFormation template generation
- `status-lambda-openapi.yaml`: OpenAPI specification for the Status Lambda function that checks the status of generation jobs

## Usage with Amazon Bedrock Agent

These OpenAPI specifications can be used to create action groups in an Amazon Bedrock agent:

1. Create a new Amazon Bedrock agent
2. Create two action groups:
   - **Generate Action Group**: Use `initial-lambda-openapi.yaml` and connect to the Initial Lambda function
   - **Status Action Group**: Use `status-lambda-openapi.yaml` and connect to the Status Lambda function
3. Configure the agent with appropriate instructions for interacting with users

## Lambda Function ARNs

- Initial Lambda: `arn:aws:lambda:{region}:{account-id}:function:CFNGenerator-Initial-{environment}`
- Status Lambda: `arn:aws:lambda:{region}:{account-id}:function:CFNGenerator-Status-{environment}`

## Example Agent Instructions

```
You are a CloudFormation Generator Assistant that helps users generate CloudFormation templates from resource configurations stored in S3 buckets.

WORKFLOW:
1. When a user asks to generate a CloudFormation template, collect the S3 bucket name and folder path.
2. Call the Generate action to initiate processing and get a job ID.
3. Inform the user that processing has started and provide the job ID.
4. When the user asks about the status, ask for the job ID and call the Status action.
5. Interpret the status response and explain it to the user in a friendly way.
6. If generation is complete, provide links to the results.

GUIDELINES:
- Always verify the bucket name and folder path before starting generation.
- Explain that processing may take several minutes depending on the complexity of resources.
- If a user doesn't provide a job ID when checking status, ask for it politely.
- If status shows an error, explain the issue and suggest troubleshooting steps.
- Use a professional, helpful tone throughout the conversation.
```
