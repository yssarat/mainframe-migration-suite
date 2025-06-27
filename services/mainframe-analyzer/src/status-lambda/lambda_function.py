import json
import boto3
import botocore
import os
import time
import logging
import traceback
import decimal
from typing import Dict, Any

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize clients
dynamodb = boto3.resource('dynamodb')
sfn_client = boto3.client('stepfunctions')
s3_client = boto3.client('s3')

# Custom JSON encoder to handle Decimal objects
class CustomJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, decimal.Decimal):
            return float(obj)
        # Also handle datetime objects from DynamoDB
        if hasattr(obj, 'isoformat'):
            return obj.isoformat()
        return super(CustomJSONEncoder, self).default(obj)

def decimal_to_float(obj):
    """Convert Decimal objects to float for JSON serialization"""
    if isinstance(obj, decimal.Decimal):
        return float(obj)
    elif isinstance(obj, dict):
        return {k: decimal_to_float(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [decimal_to_float(i) for i in obj]
    # Handle datetime objects
    elif hasattr(obj, 'isoformat'):
        return obj.isoformat()
    else:
        return obj

def get_job_status(job_id: str) -> Dict[str, Any]:
    """
    Gets the job status from DynamoDB.
    
    Args:
        job_id (str): The job ID
        
    Returns:
        dict: Job status information
    """
    # Get the DynamoDB table name from environment variable or use default
    table_name = os.environ.get('JOBS_TABLE_NAME', 'MainframeAnalyzerJobs')
    
    try:
        # Get the table
        table = dynamodb.Table(table_name)
        
        # Get the job record
        response = table.get_item(Key={'job_id': job_id})
        
        if 'Item' not in response:
            return {
                'status': 'error',
                'error': f"Job ID {job_id} not found"
            }
        
        # Convert Decimal objects to float before returning
        return decimal_to_float(response['Item'])
        
    except Exception as e:
        logger.error(f"Error getting job status: {str(e)}")
        return {
            'status': 'error',
            'error': f"Error retrieving job status: {str(e)}"
        }

def check_step_functions_status(execution_arn: str) -> Dict[str, Any]:
    """
    Checks the status of a Step Functions execution.
    
    Args:
        execution_arn (str): The execution ARN
        
    Returns:
        dict: Execution status information
    """
    try:
        # Describe the execution
        response = sfn_client.describe_execution(executionArn=execution_arn)
        
        # Extract relevant information
        status = response['status']
        start_date = response['startDate'].isoformat()
        
        result = {
            'status': status,
            'start_date': start_date
        }
        
        # Add additional information based on status
        if status == 'SUCCEEDED':
            result['end_date'] = response['stopDate'].isoformat()
            result['output'] = json.loads(response.get('output', '{}'))
            result['execution_duration'] = (response['stopDate'] - response['startDate']).total_seconds()
        elif status == 'FAILED':
            result['end_date'] = response['stopDate'].isoformat()
            result['error'] = response.get('error', 'Unknown error')
            result['cause'] = response.get('cause', 'Unknown cause')
            result['execution_duration'] = (response['stopDate'] - response['startDate']).total_seconds()
        elif status == 'RUNNING':
            # Get execution history to determine progress
            history = sfn_client.get_execution_history(
                executionArn=execution_arn,
                maxResults=100,
                reverseOrder=True
            )
            
            # Extract the most recent state transitions
            recent_events = []
            for event in history['events']:
                if event['type'].startswith('TaskState'):
                    state_name = event.get('stateEnteredEventDetails', {}).get('name', '')
                    if state_name:
                        recent_events.append({
                            'timestamp': event['timestamp'].isoformat(),
                            'state': state_name
                        })
                
                if len(recent_events) >= 5:
                    break
            
            result['recent_events'] = recent_events
            result['execution_duration_so_far'] = (time.time() - response['startDate'].timestamp())
        
        # Convert any Decimal objects to float
        return decimal_to_float(result)
        
    except Exception as e:
        logger.error(f"Error checking Step Functions status: {str(e)}")
        return {
            'status': 'error',
            'error': f"Error checking execution status: {str(e)}"
        }

def list_output_files(bucket_name: str, output_path: str) -> Dict[str, Any]:
    """
    Lists all output files in the specified S3 bucket and path.
    
    Args:
        bucket_name (str): S3 bucket name
        output_path (str): Output path within the bucket
        
    Returns:
        dict: Dictionary containing output file information
    """
    try:
        # Ensure output path ends with a slash if not empty
        if output_path and not output_path.endswith('/'):
            output_path += '/'
        
        # List objects in the bucket with the specified prefix
        paginator = s3_client.get_paginator('list_objects_v2')
        page_iterator = paginator.paginate(Bucket=bucket_name, Prefix=output_path)
        
        output_files = []
        total_size = 0
        
        for page in page_iterator:
            if 'Contents' in page:
                for obj in page['Contents']:
                    # Skip folders (objects that end with /)
                    if not obj['Key'].endswith('/'):
                        output_files.append({
                            'key': obj['Key'],
                            'size': obj['Size'],
                            'last_modified': obj['LastModified'].isoformat(),
                            's3_location': f"s3://{bucket_name}/{obj['Key']}"
                        })
                        total_size += obj['Size']
        
        return {
            'files': output_files,
            'file_count': len(output_files),
            'total_size_bytes': total_size
        }
        
    except Exception as e:
        logger.error(f"Error listing output files: {str(e)}")
        return {
            'error': f"Error listing output files: {str(e)}",
            'error_type': type(e).__name__
        }

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
    Lambda function handler that checks the status of a mainframe documentation analysis job.
    
    Expected event structure for Bedrock agent invocation:
    {
        "requestBody": {
            "job_id": "12345"
        }
    }
    """
    logger.info("Status Lambda handler started")
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
        if 'job_id' not in request_body:
            error_message = "Missing required parameter: job_id"
            logger.error(error_message)
            
            error_response = {'message': error_message}
            if is_bedrock_agent:
                return format_bedrock_agent_response(400, error_response, event)
            else:
                return {
                    'statusCode': 400,
                    'body': json.dumps(error_response)
                }
            
        # Extract validated parameters
        job_id = request_body['job_id']
        
        # Get the job status from DynamoDB
        job_status = get_job_status(job_id)
        
        if job_status.get('status') == 'error':
            logger.error(f"Error getting job status: {job_status.get('error')}")
            
            error_response = {'message': job_status.get('error')}
            if is_bedrock_agent:
                return format_bedrock_agent_response(404, error_response, event)
            else:
                return {
                    'statusCode': 404,
                    'body': json.dumps(error_response)
                }
        
        # Check Step Functions execution status if available
        execution_arn = job_status.get('execution_arn')
        sfn_status = {}
        if execution_arn:
            sfn_status = check_step_functions_status(execution_arn)
        
        # Get output files if job is completed
        output_files = {}
        if job_status.get('status') == 'COMPLETED':
            bucket_name = job_status.get('bucket_name')
            output_path = f"mainframe-analysis/{job_id}"
            output_files = list_output_files(bucket_name, output_path)
        
        # Calculate progress percentage
        progress_percentage = 0
        if job_status.get('total_files', 0) > 0:
            progress_percentage = min(
                int((job_status.get('processed_files', 0) / job_status.get('total_files', 1)) * 100),
                99  # Cap at 99% until fully complete
            )
        
        # If job is completed, set to 100%
        if job_status.get('status') == 'COMPLETED':
            progress_percentage = 100
        
        # Prepare the response data
        response_data = {
            'job_id': job_id,
            'status': job_status.get('status', 'UNKNOWN'),
            'created_at': job_status.get('created_at'),
            'updated_at': job_status.get('updated_at'),
            'bucket_name': job_status.get('bucket_name'),
            'folder_path': job_status.get('folder_path'),
            'total_files': job_status.get('total_files'),
            'processed_files': job_status.get('processed_files'),
            'progress_percentage': progress_percentage,
            'status_message': job_status.get('status_message')
        }
        
        # Add output location and files if job is completed
        if job_status.get('status') == 'COMPLETED':
            response_data['message'] = "Analysis completed successfully. Results are available at the output_path."
            response_data['output_path'] = f"s3://{job_status.get('bucket_name')}/mainframe-analysis/{job_id}/"
            response_data['output_files'] = output_files
            
            # Add direct links to important output files if they exist
            if 'files' in output_files:
                for file in output_files['files']:
                    if 'analysis_result.txt' in file['key']:
                        response_data['analysis_result_location'] = file['s3_location']
                    elif 'full_prompt.txt' in file['key']:
                        response_data['full_prompt_location'] = file['s3_location']
        elif job_status.get('status') == 'ERROR':
            response_data['message'] = f"Analysis failed: {job_status.get('status_message')}"
            response_data['error_details'] = {
                'error': job_status.get('error', 'Unknown error'),
                'timestamp': job_status.get('updated_at')
            }
        else:
            # Job is still in progress
            response_data['message'] = f"Analysis is in progress. Current status: {job_status.get('status')}"
            
            # Add estimated completion time
            if 'total_files' in job_status and 'processed_files' in job_status:
                total_files = job_status.get('total_files', 0)
                processed_files = job_status.get('processed_files', 0)
                remaining_files = total_files - processed_files
                
                if remaining_files > 0 and processed_files > 0:
                    # Calculate time per file based on elapsed time
                    elapsed_time = time.time() - job_status.get('created_at', time.time())
                    if processed_files > 0 and elapsed_time > 0:
                        time_per_file = elapsed_time / processed_files
                        estimated_remaining_time = remaining_files * time_per_file
                        response_data['estimated_remaining_seconds'] = int(estimated_remaining_time)
                        response_data['estimated_completion_time'] = time.strftime(
                            '%Y-%m-%d %H:%M:%S', 
                            time.localtime(time.time() + estimated_remaining_time)
                        )
        
        # Add execution status if available
        if sfn_status:
            response_data['execution_status'] = sfn_status
        
        # Return the response
        if is_bedrock_agent:
            return format_bedrock_agent_response(200, response_data, event)
        else:
            return {
                'statusCode': 200,
                'body': json.dumps(response_data, cls=CustomJSONEncoder)
            }
            
    except Exception as e:
        logger.error(f"Error occurred: {str(e)}")
        logger.error(f"Traceback:\n{traceback.format_exc()}")
        
        error_response = {'message': str(e)}
        if is_bedrock_agent:
            return format_bedrock_agent_response(500, error_response, event)
        else:
            return {
                'statusCode': 500,
                'body': json.dumps({'message': str(e)})
            }
