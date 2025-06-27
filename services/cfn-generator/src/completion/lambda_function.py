import json
import boto3
import os
import logging
import traceback
import time
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

def update_job_status(job_id, status, additional_data=None):
    """
    Updates the status of a job in DynamoDB.
    
    Args:
        job_id (str): Unique job identifier
        status (str): New job status
        additional_data (dict): Additional data to update
        
    Returns:
        bool: True if successful, False otherwise
    """
    logger.info(f"Updating job status for job_id: {job_id} to {status}")
    dynamodb = boto3.resource('dynamodb')
    table_name = os.environ.get('JOBS_TABLE_NAME', 'CFNGeneratorJobs')
    table = dynamodb.Table(table_name)
    
    # Prepare update expression and attribute values
    update_expression = "SET #status = :status, updated_at = :updated_at"
    expression_attribute_names = {"#status": "status"}
    expression_attribute_values = {
        ":status": status,
        ":updated_at": int(time.time())
    }
    
    # Add additional data if provided
    if additional_data and isinstance(additional_data, dict):
        for key, value in additional_data.items():
            if key not in ['job_id', 'status', 'updated_at']:
                update_expression += f", {key} = :{key.replace('-', '_')}"
                expression_attribute_values[f":{key.replace('-', '_')}"] = value
    
    try:
        # Update job record
        table.update_item(
            Key={
                'job_id': job_id
            },
            UpdateExpression=update_expression,
            ExpressionAttributeNames=expression_attribute_names,
            ExpressionAttributeValues=expression_attribute_values
        )
        return True
    except Exception as e:
        logger.error(f"Error updating job status: {str(e)}")
        return False

def lambda_handler(event, context):
    """
    Lambda function handler that completes CloudFormation template generation.
    
    Expected event structure:
    {
        "job_id": "12345678-abcd-1234-efgh-123456789012",
        "s3_location": "s3://bucket/path/to/template.yaml",
        "zip_location": "s3://bucket/path/to/template.zip",
        "config_zip_location": "s3://bucket/path/to/configs.zip"
    }
    
    Or for error handling:
    {
        "job_id": "12345678-abcd-1234-efgh-123456789012",
        "status": "ERROR",
        "error": {
            "Error": "ErrorType",
            "Cause": "Error message"
        }
    }
    
    Or for validation error handling:
    {
        "job_id": "12345678-abcd-1234-efgh-123456789012",
        "status": "VALIDATION_FAILED",
        "error": "Validation error message",
        "s3_location": "s3://bucket/path/to/template.yaml"
    }
    """
    logger.info("Completion Lambda handler started")
    logger.info(f"Received event: {json.dumps(event)}")
    
    try:
        # Check if job_id is provided
        if 'job_id' not in event:
            logger.error("Missing required parameter: job_id")
            return {
                'statusCode': 400,
                'body': json.dumps({'message': "Missing required parameter: job_id"})
            }
        
        # Extract job_id
        job_id = event['job_id']
        
        # Check if this is an error case
        if 'status' in event and event['status'] == 'ERROR':
            # Update job status to ERROR with error details
            error_data = {
                'error': event.get('error', 'Unknown error'),
                'message': 'CloudFormation template generation failed'
            }
            
            update_success = update_job_status(job_id, 'ERROR', error_data)
            if not update_success:
                logger.error("Failed to update job status for error case")
                return {
                    'statusCode': 500,
                    'body': json.dumps({'message': "Failed to update job status"})
                }
            
            logger.info(f"Job status updated to ERROR for job_id: {job_id}")
            return {
                'statusCode': 200,
                'body': json.dumps({
                    'job_id': job_id,
                    'status': 'ERROR',
                    'message': 'CloudFormation template generation failed',
                    'error': error_data['error']
                }, cls=CustomJSONEncoder)
            }
        
        # Check if this is a validation error case
        if 'status' in event and event['status'] == 'VALIDATION_FAILED':
            # Update job status to VALIDATION_FAILED with error details
            error_data = {
                'error': event.get('error', 'Unknown validation error'),
                'message': 'CloudFormation template validation failed',
                's3_location': event.get('s3_location', '')
            }
            
            update_success = update_job_status(job_id, 'VALIDATION_FAILED', error_data)
            if not update_success:
                logger.error("Failed to update job status for validation error case")
                return {
                    'statusCode': 500,
                    'body': json.dumps({'message': "Failed to update job status"})
                }
            
            logger.info(f"Job status updated to VALIDATION_FAILED for job_id: {job_id}")
            return {
                'statusCode': 200,
                'body': json.dumps({
                    'job_id': job_id,
                    'status': 'VALIDATION_FAILED',
                    'message': 'CloudFormation template validation failed',
                    'error': error_data['error'],
                    's3_location': error_data['s3_location']
                }, cls=CustomJSONEncoder)
            }
            
        # Check if this is a validation error case from Step Functions
        if 'status' in event and event['status'] == 'VALIDATION_ERROR':
            # Update job status to VALIDATION_FAILED with error details
            error_data = {
                'error': event.get('error', 'Unknown validation error'),
                'message': 'CloudFormation template validation failed',
                's3_location': event.get('s3_location', '')
            }
            
            update_success = update_job_status(job_id, 'VALIDATION_FAILED', error_data)
            if not update_success:
                logger.error("Failed to update job status for validation error case")
                return {
                    'statusCode': 500,
                    'body': json.dumps({'message': "Failed to update job status"})
                }
            
            logger.info(f"Job status updated to VALIDATION_FAILED for job_id: {job_id}")
            return {
                'statusCode': 200,
                'body': json.dumps({
                    'job_id': job_id,
                    'status': 'VALIDATION_FAILED',
                    'message': 'CloudFormation template validation failed',
                    'error': error_data['error'],
                    's3_location': error_data['s3_location']
                }, cls=CustomJSONEncoder)
            }
        
        # For successful case, check required parameters
        required_params = ['s3_location']  # Only s3_location is required
        missing_params = [param for param in required_params if param not in event]
        if missing_params:
            logger.error(f"Missing required parameters: {', '.join(missing_params)}")
            return {
                'statusCode': 400,
                'body': json.dumps({'message': f"Missing required parameters: {', '.join(missing_params)}"})
            }
        
        # Extract parameters
        s3_location = event['s3_location']
        # Make zip_location and config_zip_location optional, defaulting to s3_location
        zip_location = event.get('zip_location', s3_location)
        config_zip_location = event.get('config_zip_location', s3_location)
        
        # Update job status to COMPLETED with output locations
        additional_data = {
            's3_location': s3_location,
            'zip_location': zip_location,
            'config_zip_location': config_zip_location,
            'message': 'CloudFormation template generation completed successfully'
        }
        
        update_success = update_job_status(job_id, 'COMPLETED', additional_data)
        if not update_success:
            logger.error("Failed to update job status for completion case")
            return {
                'statusCode': 500,
                'body': json.dumps({'message': "Failed to update job status"})
            }
        
        logger.info(f"Job status updated to COMPLETED for job_id: {job_id}")
        return {
            'statusCode': 200,
            'body': json.dumps({
                'job_id': job_id,
                'status': 'COMPLETED',
                'message': 'CloudFormation template generation completed successfully',
                's3_location': s3_location,
                'zip_location': zip_location,
                'config_zip_location': config_zip_location
            }, cls=CustomJSONEncoder)
        }
            
    except Exception as e:
        logger.error(f"Error occurred: {str(e)}")
        logger.error(f"Error type: {type(e).__name__}")
        logger.error(f"Traceback:\n{traceback.format_exc()}")
        return {
            'statusCode': 500,
            'body': json.dumps({'message': str(e)})
        }
