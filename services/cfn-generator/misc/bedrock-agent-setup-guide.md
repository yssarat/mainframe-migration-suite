# Amazon Bedrock Agent Setup Guide for CloudFormation Generator

This guide provides step-by-step instructions for setting up an Amazon Bedrock agent to interact with the CloudFormation Generator system.

## Prerequisites

Before you begin, ensure you have:

1. Deployed the CloudFormation Generator stack successfully
2. Access to the Amazon Bedrock console
3. Appropriate IAM permissions to create and configure Bedrock agents
4. The ARNs of the Initial and Status Lambda functions

## Step 1: Enable Amazon Bedrock Models

1. Navigate to the Amazon Bedrock console
2. Go to "Model access" in the left navigation pane
3. Request access to a model (Claude 3 Sonnet or Haiku recommended)
4. Wait for access approval (this may be immediate or take some time)

## Step 2: Create a New Bedrock Agent

1. In the Amazon Bedrock console, go to "Agents" in the left navigation pane
2. Click "Create agent"
3. Enter basic information:
   - **Name**: CloudFormation Generator Agent
   - **Description**: Agent for generating CloudFormation templates from S3 resource configurations
   - **IAM role**: Create a new role or select an existing role with appropriate permissions
4. Select a foundation model (Claude 3 Sonnet or Haiku recommended)
5. Click "Next"

## Step 3: Configure Agent Instructions

1. In the "Instructions" section, paste the contents of the `bedrock-agent-instructions.md` file
2. Click "Next"

## Step 4: Create Action Groups

### Generate Action Group

1. Click "Add action group"
2. Enter basic information:
   - **Name**: GenerateTemplate
   - **Description**: Start CloudFormation template generation
3. For API schema, select "Upload OpenAPI schema"
4. Upload the `initial-lambda-openapi.yaml` file from the `openapi` directory
5. For "Action group execution function", select the Initial Lambda function:
   - ARN: `arn:aws:lambda:{region}:{account-id}:function:CFNGenerator-Initial-{environment}`
6. Click "Create"

### Status Action Group

1. Click "Add action group"
2. Enter basic information:
   - **Name**: CheckStatus
   - **Description**: Check status of CloudFormation template generation jobs
3. For API schema, select "Upload OpenAPI schema"
4. Upload the `status-lambda-openapi.yaml` file from the `openapi` directory
5. For "Action group execution function", select the Status Lambda function:
   - ARN: `arn:aws:lambda:{region}:{account-id}:function:CFNGenerator-Status-{environment}`
6. Click "Create"

## Step 5: Review and Create Agent

1. Review all configurations
2. Click "Create agent"
3. Wait for the agent to be created (this may take a few minutes)

## Step 6: Create an Agent Alias

1. Once the agent is created, go to the "Aliases" tab
2. Click "Create alias"
3. Enter basic information:
   - **Name**: latest
   - **Description**: Latest version of the CloudFormation Generator Agent
4. For "Agent version", select "DRAFT"
5. Click "Create"

## Step 7: Test the Agent

1. Go to the "Test" tab
2. In the chat interface, test the agent with sample queries:
   - "I want to generate a CloudFormation template"
   - "Check the status of my job with ID [job-id]"
3. Verify that the agent correctly calls the Lambda functions and returns appropriate responses

## Step 8: Deploy the Agent (Optional)

If you want to integrate the agent with other applications:

1. Go to the "Aliases" tab
2. Select the alias you created
3. Click "Deploy"
4. Follow the instructions to deploy the agent to your application

## Troubleshooting

### Common Issues

1. **Lambda Invocation Errors**:
   - Check that the Lambda functions are deployed correctly
   - Verify that the Bedrock agent's IAM role has permission to invoke the Lambda functions

2. **OpenAPI Schema Errors**:
   - Ensure the OpenAPI schemas are valid and correctly formatted
   - Check that the paths and operations match what the Lambda functions expect

3. **Agent Not Understanding Instructions**:
   - Review and refine the agent instructions
   - Add more example dialogues to help the agent understand the expected behavior

4. **Model Access Issues**:
   - Ensure you have requested and received access to the foundation model
   - Check that your AWS account has the necessary permissions for Bedrock

## Next Steps

After setting up your Bedrock agent, consider:

1. **Monitoring**: Set up CloudWatch alarms to monitor Lambda function invocations and errors
2. **Logging**: Review CloudWatch logs for detailed information about agent-Lambda interactions
3. **Refinement**: Continuously improve the agent instructions based on user interactions
4. **Integration**: Integrate the agent with your applications or workflows

For more information, refer to the [Amazon Bedrock documentation](https://docs.aws.amazon.com/bedrock/)
