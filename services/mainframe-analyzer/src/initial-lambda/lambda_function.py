import json
import boto3
import botocore
import os
import re
import uuid
import time
import logging
from typing import Dict, Any, Tuple, List
from decimal import Decimal

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize clients
s3_client = boto3.client('s3')
sfn_client = boto3.client('stepfunctions')
dynamodb = boto3.resource('dynamodb')

# Custom JSON encoder to handle Decimal objects
class CustomJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        # Also handle datetime objects from DynamoDB
        if hasattr(obj, 'isoformat'):
            return obj.isoformat()
        return super(CustomJSONEncoder, self).default(obj)

def validate_input_parameters(params: Dict[str, Any]) -> Tuple[bool, str]:
    """
    Validates the input parameters for the mainframe documentation analyzer.
    
    Args:
        params (dict): Dictionary containing input parameters
        
    Returns:
        tuple: (is_valid, error_message)
    """
    required_params = ['bucket_name', 'folder_path']
    
    # Check for missing parameters
    for param in required_params:
        if param not in params:
            return False, f"Missing required parameter: {param}"
    
    # Validate folder path doesn't start with /
    if params['folder_path'].startswith('/'):
        return False, "folder_path should not start with '/'"
    
    # Validate bucket name format
    if not re.match(r'^[a-z0-9][a-z0-9.-]*[a-z0-9]$', params['bucket_name']):
        return False, "Invalid S3 bucket name format"
    
    return True, ""

def verify_s3_bucket_exists(bucket_name: str) -> Tuple[bool, str]:
    """
    Verifies that the specified S3 bucket exists.
    
    Args:
        bucket_name (str): S3 bucket name
        
    Returns:
        tuple: (exists, error_message)
    """
    try:
        # Check if bucket exists
        s3_client.head_bucket(Bucket=bucket_name)
        return True, ""
        
    except botocore.exceptions.ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', '')
        
        if error_code == '404':
            return False, f"S3 bucket not found: {bucket_name}"
        elif error_code == '403':
            return False, f"Access denied to S3 bucket: {bucket_name}"
        else:
            return False, f"Error accessing S3 bucket: {str(e)}"

def list_files_recursively(bucket_name: str, folder_path: str, max_files: int = 100) -> List[Dict[str, Any]]:
    """
    Lists all files in the specified S3 bucket and folder recursively.
    
    Args:
        bucket_name (str): S3 bucket name
        folder_path (str): Folder path within the bucket
        max_files (int): Maximum number of files to return
        
    Returns:
        list: List of dictionaries containing file information
    """
    files = []
    
    # Ensure folder path ends with a slash if not empty
    if folder_path and not folder_path.endswith('/'):
        folder_path += '/'
    
    try:
        # List objects in the bucket with the specified prefix
        paginator = s3_client.get_paginator('list_objects_v2')
        page_iterator = paginator.paginate(Bucket=bucket_name, Prefix=folder_path)
        
        for page in page_iterator:
            if 'Contents' in page:
                for obj in page['Contents']:
                    # Skip folders (objects that end with /)
                    if not obj['Key'].endswith('/'):
                        file_extension = os.path.splitext(obj['Key'])[1].lower()
                        # Only include pdf, docx, or txt files
                        if file_extension in ['.pdf', '.docx', '.txt']:
                            files.append({
                                'key': obj['Key'],
                                'size': obj['Size'],
                                'last_modified': obj['LastModified'].isoformat(),
                                'extension': file_extension
                            })
                            
                            # Check if we've reached the maximum number of files
                            if len(files) >= max_files:
                                logger.info(f"Reached maximum file limit ({max_files}). Returning partial list.")
                                return files
        
        return files
    
    except botocore.exceptions.ClientError as e:
        logger.error(f"Error listing files in S3: {str(e)}")
        raise

def create_job_record(job_id: str, bucket_name: str, folder_path: str, files: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Creates a job record in DynamoDB.
    
    Args:
        job_id (str): Unique job ID
        bucket_name (str): S3 bucket name
        folder_path (str): Folder path within the bucket
        files (list): List of files to process
        
    Returns:
        dict: Created job record
    """
    # Get the DynamoDB table name from environment variable or use default
    table_name = os.environ.get('JOBS_TABLE_NAME', 'MainframeAnalyzerJobs')
    
    try:
        # Get the table
        table = dynamodb.Table(table_name)
        
        # Create the job record
        job_record = {
            'job_id': job_id,
            'bucket_name': bucket_name,
            'folder_path': folder_path,
            'status': 'STARTED',
            'created_at': int(time.time()),
            'updated_at': int(time.time()),
            'total_files': len(files),
            'processed_files': 0,
            'file_list': files,  # Store all files in the record
            'file_count': len(files)
        }
        
        # Put the item in the table
        table.put_item(Item=job_record)
        
        return job_record
        
    except Exception as e:
        logger.error(f"Error creating job record: {str(e)}")
        raise

def start_processing_workflow(job_id: str, bucket_name: str, folder_path: str, files: List[Dict[str, Any]]) -> str:
    """
    Starts the Step Functions workflow for processing the files.
    
    Args:
        job_id (str): Unique job ID
        bucket_name (str): S3 bucket name
        folder_path (str): Folder path within the bucket
        files (list): List of files to process
        
    Returns:
        str: Step Functions execution ARN
    """
    # Get the state machine ARN from environment variable
    state_machine_arn = os.environ.get('STATE_MACHINE_ARN')
    
    if not state_machine_arn:
        raise ValueError("STATE_MACHINE_ARN environment variable is not set")
    
    # Prepare the input for the state machine
    state_machine_input = {
        'job_id': job_id,
        'bucket_name': bucket_name,
        'folder_path': folder_path,
        'files': files,
        'output_path': f"mainframe-analysis/{job_id}"
    }
    
    # Start the execution
    response = sfn_client.start_execution(
        stateMachineArn=state_machine_arn,
        name=f"mainframe-analysis-{job_id}",
        input=json.dumps(state_machine_input)
    )
    
    return response['executionArn']

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
    # Convert the response body to a JSON string
    response_json = json.dumps(response_body, cls=CustomJSONEncoder)
    
    # Format the response body for Bedrock agent
    # Note: Bedrock expects the body to be a string, not a nested JSON object
    formatted_body = {
        "application/json": {
            "body": response_json
        }
    }
    
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
    Lambda function handler that initiates the mainframe documentation analysis process.
    
    Expected event structure for Bedrock agent invocation:
    {
        "requestBody": {
            "bucket_name": "my-bucket",
            "folder_path": "path/to/documentation"
        }
    }
    """
    logger.info("Initial Lambda handler started")
    logger.info(f"Received event: {json.dumps(event)}")
    
    try:
        # Determine if this is a Bedrock agent invocation
        is_bedrock_agent = "actionGroup" in event
        
        # Extract parameters from the event
        if is_bedrock_agent:
            # Check if this is the new format with properties array
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
        folder_path = request_body['folder_path']
        
        # Verify S3 bucket exists
        logger.info(f"Verifying S3 bucket exists: {bucket_name}")
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
        
        # List files in the bucket and folder
        logger.info(f"Listing files in bucket: {bucket_name}, folder: {folder_path}")
        max_files = int(os.environ.get('MAX_FILES', 100))
        files = list_files_recursively(bucket_name, folder_path, max_files)
        
        if not files:
            message = f"No PDF, DOCX, or TXT files found in s3://{bucket_name}/{folder_path}"
            logger.warning(message)
            response_data = {
                'message': message,
                'bucket_name': bucket_name,
                'folder_path': folder_path
            }
            if is_bedrock_agent:
                return format_bedrock_agent_response(200, response_data, event)
            else:
                return {
                    'statusCode': 200,
                    'body': json.dumps(response_data)
                }
        
        # Generate a unique job ID
        job_id = str(uuid.uuid4())
        
        # Create a job record in DynamoDB
        job_record = create_job_record(job_id, bucket_name, folder_path, files)
        
        # Start the Step Functions workflow
        execution_arn = start_processing_workflow(job_id, bucket_name, folder_path, files)
        
        # Prepare the response
        success_message = f"Processing started for {len(files)} files. Use the job_id to check status."
        logger.info(success_message)
        
        response_data = {
            'message': success_message,
            'job_id': job_id,
            'execution_arn': execution_arn,
            'files_found': len(files),
            'bucket_name': bucket_name,
            'folder_path': folder_path,
            'output_path': f"s3://{bucket_name}/mainframe-analysis/{job_id}/",
            'created_at': job_record['created_at'],
            'estimated_completion_time': f"Approximately {len(files) * 2} seconds"
        }
        
        if is_bedrock_agent:
            return format_bedrock_agent_response(202, response_data, event)
        else:
            return {
                'statusCode': 202,
                'body': json.dumps(response_data, cls=CustomJSONEncoder)
            }
            
    except Exception as e:
        logger.error(f"Error occurred: {str(e)}")
        import traceback
        logger.error(f"Traceback:\n{traceback.format_exc()}")
        
        error_response = {'message': str(e)}
        if is_bedrock_agent:
            return format_bedrock_agent_response(500, error_response, event)
        else:
            return {
                'statusCode': 500,
                'body': json.dumps({'message': str(e)})
            }
