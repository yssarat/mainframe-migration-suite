# Troubleshooting Guide

This guide provides solutions for common issues you might encounter when using the Asynchronous CloudFormation Generator.

## Common Issues and Solutions

### Deployment Issues

#### CloudFormation Stack Creation Fails

**Symptoms**:
- CloudFormation stack creation fails with an error
- Deployment script reports an error during stack creation

**Possible Causes and Solutions**:

1. **Insufficient Permissions**
   - **Cause**: The IAM user or role doesn't have sufficient permissions to create the required resources
   - **Solution**: Ensure the IAM user or role has the necessary permissions to create all resources defined in the CloudFormation templates

2. **Resource Already Exists**
   - **Cause**: A resource with the same name already exists in your AWS account
   - **Solution**: Use a different environment name or stack name to avoid conflicts

3. **Service Limits**
   - **Cause**: You've reached the service limits for one or more AWS services
   - **Solution**: Request a service limit increase through AWS Support

4. **Invalid Template**
   - **Cause**: The CloudFormation template contains errors
   - **Solution**: Check the CloudFormation events in the AWS Console for specific error messages

#### S3 Bucket Creation Fails

**Symptoms**:
- Deployment script fails when creating the S3 bucket
- Error message about bucket name already in use

**Possible Causes and Solutions**:

1. **Bucket Name Already Exists**
   - **Cause**: An S3 bucket with the same name already exists (globally)
   - **Solution**: Use a different environment name or stack name to generate a unique bucket name

2. **Invalid Bucket Name**
   - **Cause**: The generated bucket name doesn't comply with S3 naming rules
   - **Solution**: Ensure the environment name and stack name only contain valid characters

### Template Generation Issues

#### Job Stuck in PENDING Status

**Symptoms**:
- Job status remains PENDING for a long time
- No Step Functions execution is visible

**Possible Causes and Solutions**:

1. **Step Functions Execution Failed to Start**
   - **Cause**: The Initial Lambda function failed to start the Step Functions execution
   - **Solution**: Check CloudWatch Logs for the Initial Lambda function for error messages

2. **IAM Permission Issues**
   - **Cause**: The Lambda execution role doesn't have permission to start Step Functions executions
   - **Solution**: Verify the IAM permissions for the Lambda execution role

#### Job Failed with ERROR Status

**Symptoms**:
- Job status is ERROR
- Error message in the job record

**Possible Causes and Solutions**:

1. **S3 Access Issues**
   - **Cause**: The Lambda function can't access the S3 bucket or objects
   - **Solution**: Verify the IAM permissions and S3 bucket policies

2. **Invalid Resource Configurations**
   - **Cause**: The resource configurations in S3 are invalid or incomplete
   - **Solution**: Check the resource configuration files for errors

3. **Bedrock Model Access Issues**
   - **Cause**: The Lambda function can't access the Bedrock model
   - **Solution**: Verify that you have access to the specified Bedrock model and that the IAM permissions are correct

4. **Lambda Timeout**
   - **Cause**: The Lambda function timed out before completing
   - **Solution**: Increase the Lambda function timeout in the CloudFormation template

#### Generated Template is Incomplete or Incorrect

**Symptoms**:
- The generated CloudFormation template is missing resources or contains errors
- The template doesn't match the resource configurations

**Possible Causes and Solutions**:

1. **Incomplete Resource Configurations**
   - **Cause**: The resource configurations in S3 are incomplete
   - **Solution**: Ensure all required configuration parameters are included in the resource configuration files

2. **Complex Resource Relationships**
   - **Cause**: The resource relationships are too complex for the generator to understand
   - **Solution**: Simplify the resource configurations or provide additional context in the configuration files

3. **Prompt Template Issues**
   - **Cause**: The prompt template doesn't provide enough guidance for the Bedrock model
   - **Solution**: Update the prompt template in the SSM Parameter Store to provide more specific instructions

### Bedrock Agent Issues

#### Agent Not Responding

**Symptoms**:
- The Bedrock agent doesn't respond to requests
- The agent returns error messages

**Possible Causes and Solutions**:

1. **Agent Configuration Issues**
   - **Cause**: The agent is not properly configured
   - **Solution**: Verify the agent configuration in the Bedrock console

2. **Lambda Function Errors**
   - **Cause**: The Lambda functions invoked by the agent are returning errors
   - **Solution**: Check CloudWatch Logs for the Lambda functions for error messages

3. **IAM Permission Issues**
   - **Cause**: The agent doesn't have permission to invoke the Lambda functions
   - **Solution**: Verify the IAM permissions for the agent role

#### Agent Returns Invalid Responses

**Symptoms**:
- The agent returns responses that don't match the expected format
- The agent doesn't understand user requests

**Possible Causes and Solutions**:

1. **Agent Instruction Issues**
   - **Cause**: The agent instructions are not clear or comprehensive
   - **Solution**: Update the agent instructions in the CloudFormation template

2. **Action Group Schema Issues**
   - **Cause**: The action group OpenAPI schema doesn't match the Lambda function expectations
   - **Solution**: Verify that the OpenAPI schema in the CloudFormation template matches the Lambda function input/output format

## Debugging Tools

### CloudWatch Logs

CloudWatch Logs are the primary tool for debugging Lambda function issues:

1. Go to the CloudWatch console
2. Navigate to Log groups
3. Find the log group for the relevant Lambda function:
   - `/aws/lambda/CFNGenerator-Initial-<env>`
   - `/aws/lambda/CFNGenerator-Status-<env>`
   - `/aws/lambda/CFNGenerator-Generator-<env>`
   - `/aws/lambda/CFNGenerator-Completion-<env>`
4. Look for error messages and stack traces

### Step Functions Execution History

Step Functions execution history provides insights into the workflow execution:

1. Go to the Step Functions console
2. Find the state machine: `CFNGeneratorWorkflow-<env>`
3. Click on the relevant execution
4. View the execution history and event details
5. Look for failed states and error messages

### DynamoDB Table

The DynamoDB table contains job records with status information:

1. Go to the DynamoDB console
2. Find the table: `CFNGeneratorJobs-<env>`
3. Query the table using the job ID
4. Check the job status, error messages, and timestamps

### Bedrock Agent Testing

The Bedrock agent testing interface helps debug agent issues:

1. Go to the Bedrock console
2. Navigate to Agents
3. Find your agent: `CFNGeneratorAgent-<env>`
4. Click on the agent to open the Test window
5. Test the agent with various inputs and observe the responses

## Getting Help

If you're unable to resolve an issue using this troubleshooting guide:

1. Check the project documentation for additional information
2. Review the AWS service documentation for the affected services
3. Check AWS service health in the AWS Health Dashboard
4. Contact AWS Support if you have a support plan
5. File an issue in the project repository with detailed information about the problem
