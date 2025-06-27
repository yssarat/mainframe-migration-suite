import json
import boto3
import os
import logging
import traceback
from decimal import Decimal

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Custom JSON encoder to handle Decimal objects
class CustomJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        # Also handle datetime objects from DynamoDB
        if hasattr(obj, 'isoformat'):
            return obj.isoformat()
        return super(CustomJSONEncoder, self).default(obj)

def get_job_status(job_id):
    """
    Retrieves the status of a job from DynamoDB.
    
    Args:
        job_id (str): Unique job identifier
        
    Returns:
        tuple: (bool, dict or str) - (success, job_data or error_message)
    """
    logger.info(f"Getting job status for job_id: {job_id}")
    dynamodb = boto3.resource('dynamodb')
    table_name = os.environ.get('JOBS_TABLE_NAME', 'CFNGeneratorJobs')
    table = dynamodb.Table(table_name)
    
    try:
        # Get job record
        response = table.get_item(
            Key={
                'job_id': job_id
            }
        )
        
        # Check if job exists
        if 'Item' not in response:
            logger.error(f"Job not found: {job_id}")
            return False, f"Job not found: {job_id}"
        
        # Return job data
        job_data = response['Item']
        logger.info(f"Job status retrieved: {job_data['status']}")
        return True, job_data
    except Exception as e:
        logger.error(f"Error getting job status: {str(e)}")
        return False, str(e)

def get_step_function_execution_status(job_id):
    """
    Retrieves the status of a Step Functions execution.
    
    Args:
        job_id (str): Unique job identifier
        
    Returns:
        tuple: (bool, dict or str) - (success, execution_data or error_message)
    """
    logger.info(f"Getting Step Functions execution status for job_id: {job_id}")
    sfn = boto3.client('stepfunctions')
    state_machine_arn = os.environ.get('STATE_MACHINE_ARN')
    
    if not state_machine_arn:
        logger.warning("STATE_MACHINE_ARN environment variable not set, skipping Step Functions status check")
        return False, "STATE_MACHINE_ARN environment variable not set"
    
    try:
        # List executions for the state machine
        response = sfn.list_executions(
            stateMachineArn=state_machine_arn,
            statusFilter='ALL',
            maxResults=100
        )
        
        # Find the execution for this job
        execution_arn = None
        execution_status = None
        for execution in response['executions']:
            if execution['name'] == f"cfn-generator-{job_id}":
                execution_arn = execution['executionArn']
                execution_status = execution['status']
                break
        
        if not execution_arn:
            logger.warning(f"No Step Functions execution found for job_id: {job_id}")
            return False, "No Step Functions execution found"
        
        # Get execution details
        execution_details = sfn.describe_execution(
            executionArn=execution_arn
        )
        
        logger.info(f"Step Functions execution status: {execution_status}")
        return True, execution_details
    except Exception as e:
        logger.error(f"Error getting Step Functions execution status: {str(e)}")
        return False, str(e)

def format_bedrock_agent_response(status_code, response_body, event):
    """
    Formats the response according to Bedrock agent requirements.
    
    Args:
        status_code (int): HTTP status code
        response_body (dict): The response body to be returned
        event (dict): The original event object
        
    Returns:
        dict: Formatted response for Bedrock agent
    """
    # Format the response body for Bedrock agent
    formatted_body = {"application/json": {"body": json.dumps(response_body, cls=CustomJSONEncoder)}}
    
    action_response = {
        "actionGroup": event.get("actionGroup"),
        "apiPath": event.get("apiPath"),
        "httpMethod": event.get("httpMethod"),
        "httpStatusCode": status_code,
        "responseBody": formatted_body
    }
    
    return {
        "messageVersion": "1.0",
        "response": action_response
    }

def lambda_handler(event, context):
    """
    Lambda function handler that checks the status of CloudFormation template generation.
    Can be invoked as a regular Lambda or as a Bedrock agent action.
    
    Expected event structure for direct Lambda invocation:
    {
        "job_id": "12345678-abcd-1234-efgh-123456789012"
    }
    
    For Bedrock agent invocation, these parameters should be in the requestBody.
    """
    logger.info("Status Lambda handler started")
    logger.info(f"Received event: {json.dumps(event)}")
    
    try:
        # Determine if this is a Bedrock agent invocation
        is_bedrock_agent = "actionGroup" in event
        
        # Extract parameters from the event
        if is_bedrock_agent:
            # Check if this is the format with properties array
            if "requestBody" in event and isinstance(event["requestBody"], dict):
                content = event["requestBody"].get("content", {}).get("application/json", {})
                if "properties" in content and isinstance(content["properties"], list):
                    # Convert properties array to dictionary
                    request_body = {}
                    for prop in content["properties"]:
                        if isinstance(prop, dict) and "name" in prop and "value" in prop:
                            request_body[prop["name"]] = prop["value"]
                else:
                    request_body = event["requestBody"]
            else:
                # For Bedrock agent invocation with old format, parameters are in requestBody as JSON string
                request_body = json.loads(event.get("requestBody", "{}"))
        else:
            # Direct Lambda invocation
            request_body = event
            
        # Check if job_id is provided
        if 'job_id' not in request_body:
            logger.error("Missing required parameter: job_id")
            error_response = {'message': "Missing required parameter: job_id"}
            if is_bedrock_agent:
                return format_bedrock_agent_response(400, error_response, event)
            else:
                return {
                    'statusCode': 400,
                    'body': json.dumps(error_response)
                }
            
        # Extract job_id
        job_id = request_body['job_id']
        
        # Get job status from DynamoDB
        job_found, job_data_or_error = get_job_status(job_id)
        if not job_found:
            logger.error(f"Failed to get job status: {job_data_or_error}")
            error_response = {'message': job_data_or_error}
            if is_bedrock_agent:
                return format_bedrock_agent_response(404, error_response, event)
            else:
                return {
                    'statusCode': 404,
                    'body': json.dumps(error_response)
                }
        
        # Get Step Functions execution status (optional)
        sfn_found, sfn_data_or_error = get_step_function_execution_status(job_id)
        
        # Prepare response data
        response_data = {
            'job_id': job_id,
            'status': job_data_or_error['status'],
            'created_at': job_data_or_error.get('created_at'),
            'updated_at': job_data_or_error.get('updated_at')
        }
        
        # Add additional fields if available
        if 'message' in job_data_or_error:
            response_data['message'] = job_data_or_error['message']
        
        if 's3_location' in job_data_or_error:
            response_data['s3_location'] = job_data_or_error['s3_location']
        
        if 'zip_location' in job_data_or_error:
            response_data['zip_location'] = job_data_or_error['zip_location']
        
        if 'config_zip_location' in job_data_or_error:
            response_data['config_zip_location'] = job_data_or_error['config_zip_location']
        
        if 'error' in job_data_or_error:
            response_data['error'] = job_data_or_error['error']
        
        # Add Step Functions execution status if available
        if sfn_found and isinstance(sfn_data_or_error, dict):
            response_data['execution_status'] = sfn_data_or_error.get('status')
            response_data['execution_started_at'] = sfn_data_or_error.get('startDate')
            if 'stopDate' in sfn_data_or_error:
                response_data['execution_stopped_at'] = sfn_data_or_error['stopDate']
        
        logger.info(f"Job status response prepared for job_id: {job_id}")
        
        if is_bedrock_agent:
            return format_bedrock_agent_response(200, response_data, event)
        else:
            return {
                'statusCode': 200,
                'body': json.dumps(response_data, cls=CustomJSONEncoder)
            }
            
    except Exception as e:
        logger.error(f"Error occurred: {str(e)}")
        logger.error(f"Error type: {type(e).__name__}")
        logger.error(f"Traceback:\n{traceback.format_exc()}")
        error_response = {'message': str(e)}
        if is_bedrock_agent:
            return format_bedrock_agent_response(500, error_response, event)
        else:
            return {
                'statusCode': 500,
                'body': json.dumps({'message': str(e)})
            }
