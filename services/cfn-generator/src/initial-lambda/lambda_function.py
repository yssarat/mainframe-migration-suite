import json
import boto3
import os
import re
import uuid
import time
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

def validate_input_parameters(params):
    """
    Validates the input parameters for CloudFormation template generation.
    
    Args:
        params (dict): Dictionary containing input parameters
        
    Returns:
        tuple: (bool, str) - (is_valid, error_message)
    """
    logger.info("Validating input parameters")
    
    # Check for bucket_name parameter
    if 'bucket_name' not in params:
        return False, "Missing required parameter: bucket_name"
    
    # Validate bucket name format
    if not re.match(r'^[a-z0-9][a-z0-9.-]*[a-z0-9]$', params['bucket_name']):
        return False, "Invalid S3 bucket name format"
    
    # Check for s3_folder parameter
    if 's3_folder' not in params:
        return False, "Missing required parameter: s3_folder"
    
    # Validate folder path doesn't start with /
    if params['s3_folder'].startswith('/'):
        return False, "S3 folder path should not start with '/'"
    
    return True, ""

def verify_s3_bucket_exists(bucket_name):
    """
    Verifies that the specified S3 bucket exists and is accessible.
    
    Args:
        bucket_name (str): S3 bucket name
        
    Returns:
        tuple: (bool, str) - (exists, error_message)
    """
    logger.info(f"Verifying S3 bucket exists: {bucket_name}")
    s3 = boto3.client('s3')
    
    try:
        # Check if bucket exists
        s3.head_bucket(Bucket=bucket_name)
        return True, ""
    except Exception as e:
        logger.error(f"Error verifying S3 bucket: {str(e)}")
        return False, f"Error accessing S3 bucket {bucket_name}: {str(e)}"

def verify_s3_folder_exists(bucket_name, folder_path):
    """
    Verifies that the specified S3 folder exists and contains files.
    
    Args:
        bucket_name (str): S3 bucket name
        folder_path (str): S3 folder path
        
    Returns:
        tuple: (bool, str, int) - (exists, error_message, file_count)
    """
    logger.info(f"Verifying S3 folder exists: {bucket_name}/{folder_path}")
    s3 = boto3.client('s3')
    
    # Ensure folder path ends with a slash if it's not empty
    if folder_path and not folder_path.endswith('/'):
        folder_path = folder_path + '/'
    
    try:
        # List objects in the folder
        response = s3.list_objects_v2(
            Bucket=bucket_name,
            Prefix=folder_path,
            MaxKeys=10  # Just check if there are any files
        )
        
        # Check if the folder contains any files
        if 'Contents' in response:
            file_count = response['KeyCount']
            if file_count > 0:
                return True, "", file_count
            else:
                return False, f"S3 folder is empty: {folder_path}", 0
        else:
            return False, f"S3 folder not found or empty: {folder_path}", 0
    except Exception as e:
        logger.error(f"Error verifying S3 folder: {str(e)}")
        return False, f"Error accessing S3 folder {folder_path}: {str(e)}", 0

def create_job_record(job_id, bucket_name, s3_folder):
    """
    Creates a new job record in DynamoDB.
    
    Args:
        job_id (str): Unique job identifier
        bucket_name (str): S3 bucket name
        s3_folder (str): S3 folder path
        
    Returns:
        bool: True if successful, False otherwise
    """
    logger.info(f"Creating job record for job_id: {job_id}")
    dynamodb = boto3.resource('dynamodb')
    table_name = os.environ.get('JOBS_TABLE_NAME', 'CFNGeneratorJobs')
    table = dynamodb.Table(table_name)
    
    # Calculate TTL (30 days from now)
    ttl = int(time.time()) + (30 * 24 * 60 * 60)
    
    try:
        # Create job record
        table.put_item(
            Item={
                'job_id': job_id,
                'bucket_name': bucket_name,
                's3_folder': s3_folder,
                'status': 'PENDING',
                'created_at': int(time.time()),
                'updated_at': int(time.time()),
                'ttl': ttl
            }
        )
        return True
    except Exception as e:
        logger.error(f"Error creating job record: {str(e)}")
        return False

def start_step_function(job_id, bucket_name, s3_folder):
    """
    Starts the Step Functions state machine for template generation.
    
    Args:
        job_id (str): Unique job identifier
        bucket_name (str): S3 bucket name
        s3_folder (str): S3 folder path
        
    Returns:
        tuple: (bool, str) - (success, execution_arn or error_message)
    """
    logger.info(f"Starting Step Functions execution for job_id: {job_id}")
    sfn = boto3.client('stepfunctions')
    state_machine_arn = os.environ.get('STATE_MACHINE_ARN')
    
    if not state_machine_arn:
        logger.error("STATE_MACHINE_ARN environment variable not set")
        return False, "STATE_MACHINE_ARN environment variable not set"
    
    try:
        # Start execution
        response = sfn.start_execution(
            stateMachineArn=state_machine_arn,
            name=f"cfn-generator-{job_id}",
            input=json.dumps({
                'job_id': job_id,
                'bucket_name': bucket_name,
                's3_folder': s3_folder
            })
        )
        
        execution_arn = response['executionArn']
        logger.info(f"Step Functions execution started: {execution_arn}")
        return True, execution_arn
    except Exception as e:
        logger.error(f"Error starting Step Functions execution: {str(e)}")
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
    Lambda function handler that initiates CloudFormation template generation.
    Can be invoked as a regular Lambda or as a Bedrock agent action.
    
    Expected event structure for direct Lambda invocation:
    {
        "bucket_name": "my-resource-configs",
        "s3_folder": "resources/lambda"
    }
    
    For Bedrock agent invocation, these parameters should be in the requestBody.
    """
    logger.info("Initial Lambda handler started")
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
            
        # Validate input parameters
        logger.info(f"Validating input parameters: {json.dumps(request_body)}")
        is_valid, error_message = validate_input_parameters(request_body)
        if not is_valid:
            logger.error(f"Input validation failed: {error_message}")
            error_response = {'message': error_message}
            if is_bedrock_agent:
                return format_bedrock_agent_response(400, error_response, event)
            else:
                return {
                    'statusCode': 400,
                    'body': json.dumps(error_response)
                }
            
        # Extract validated parameters
        bucket_name = request_body['bucket_name']
        s3_folder = request_body['s3_folder'].rstrip('/')
        
        # Verify S3 bucket exists
        bucket_exists, error_message = verify_s3_bucket_exists(bucket_name)
        if not bucket_exists:
            logger.error(f"S3 bucket verification failed: {error_message}")
            error_response = {'message': error_message}
            if is_bedrock_agent:
                return format_bedrock_agent_response(404, error_response, event)
            else:
                return {
                    'statusCode': 404,
                    'body': json.dumps(error_response)
                }
        
        # Verify S3 folder exists and contains files
        folder_exists, error_message, file_count = verify_s3_folder_exists(bucket_name, s3_folder)
        if not folder_exists:
            logger.error(f"S3 folder verification failed: {error_message}")
            error_response = {'message': error_message}
            if is_bedrock_agent:
                return format_bedrock_agent_response(404, error_response, event)
            else:
                return {
                    'statusCode': 404,
                    'body': json.dumps(error_response)
                }
        
        # Generate a unique job ID
        job_id = str(uuid.uuid4())
        
        # Create job record in DynamoDB
        job_created = create_job_record(job_id, bucket_name, s3_folder)
        if not job_created:
            logger.error("Failed to create job record")
            error_response = {'message': "Failed to create job record"}
            if is_bedrock_agent:
                return format_bedrock_agent_response(500, error_response, event)
            else:
                return {
                    'statusCode': 500,
                    'body': json.dumps(error_response)
                }
        
        # Start Step Functions execution
        sfn_started, execution_arn_or_error = start_step_function(job_id, bucket_name, s3_folder)
        if not sfn_started:
            logger.error(f"Failed to start Step Functions execution: {execution_arn_or_error}")
            error_response = {'message': f"Failed to start template generation: {execution_arn_or_error}"}
            if is_bedrock_agent:
                return format_bedrock_agent_response(500, error_response, event)
            else:
                return {
                    'statusCode': 500,
                    'body': json.dumps(error_response)
                }
        
        # Prepare success response
        response_data = {
            'job_id': job_id,
            'status': 'PENDING',
            'message': f'CloudFormation template generation started. Use the job_id to check status.',
            'files_found': file_count
        }
        
        logger.info(f"Template generation initiated successfully for job_id: {job_id}")
        
        if is_bedrock_agent:
            return format_bedrock_agent_response(202, response_data, event)
        else:
            return {
                'statusCode': 202,
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
