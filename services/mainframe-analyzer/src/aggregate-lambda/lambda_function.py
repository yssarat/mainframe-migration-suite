import boto3
import os
import time
import json
import logging

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def update_job_status(job_id, status, message=None):
    """Update the job status in DynamoDB"""
    try:
        logger.info(f"Updating job status for job_id={job_id}, status={status}, message={message}")
        
        # Get the DynamoDB table name from environment variable
        table_name = os.environ.get('JOBS_TABLE_NAME', 'MainframeAnalyzerJobs')
        
        # Get the table
        dynamodb = boto3.resource('dynamodb')
        table = dynamodb.Table(table_name)
        
        # Prepare update expression and attribute values
        update_expression = 'SET #status = :status, updated_at = :time'
        expression_attr_names = {'#status': 'status'}
        expression_attr_values = {
            ':status': status,
            ':time': int(time.time())
        }
        
        # Add message if provided
        if message:
            update_expression += ', status_message = :message'
            expression_attr_values[':message'] = message
        
        # Update the job record
        table.update_item(
            Key={'job_id': job_id},
            UpdateExpression=update_expression,
            ExpressionAttributeNames=expression_attr_names,
            ExpressionAttributeValues=expression_attr_values
        )
        
        logger.info(f"Successfully updated job status for job_id={job_id}")
        return {
            'status': 'success',
            'job_id': job_id,
            'updated_status': status
        }
    except Exception as e:
        logger.error(f"Error updating job status: {str(e)}")
        raise

def get_parameter(param_name):
    """Get a parameter from Parameter Store"""
    try:
        logger.info(f"Getting parameter: {param_name}")
        ssm = boto3.client('ssm')
        response = ssm.get_parameter(
            Name=param_name,
            WithDecryption=True
        )
        return response['Parameter']['Value']
    except Exception as e:
        logger.error(f"Error getting parameter {param_name}: {str(e)}")
        return None

def lambda_handler(event, context):
    """
    Aggregate the processed file contents for analysis
    """
    logger.info(f"Starting aggregate_lambda with event: {json.dumps(event)}")
    
    try:
        # Extract parameters from the event
        job_id = event.get('job_id')
        bucket_name = event.get('bucket_name')
        output_path = event.get('output_path', 'output')
        file_results = event.get('file_results', [])
        
        # Get configuration from environment variables or Parameter Store
        param_store_path = os.environ.get('PARAMETER_STORE_PREFIX', '/mainframe-modernization/documentation-agent/updated-prompt')
        max_combined_chars = int(os.environ.get('MAX_COMBINED_CHARS', 100000))
        
        logger.info(f"Using Parameter Store path: {param_store_path}")
        logger.info(f"Using max_combined_chars: {max_combined_chars}")
        
        # Get the prompt template from Parameter Store
        prompt_template = get_parameter(param_store_path)
        
        if not prompt_template:
            logger.warning("Could not retrieve prompt template from Parameter Store, using default")
            prompt_template = """
            You are an expert mainframe documentation analyzer. Please analyze the following mainframe documentation and provide:
            
            1. A high-level overview of the system described
            2. Key components and their relationships
            3. Data structures and their fields
            4. Business rules and logic
            5. Potential modernization challenges
            6. Recommendations for modernization approach
            
            Please format your response in markdown with appropriate sections and code blocks.
            
            DOCUMENTATION:
            """
        
        logger.info(f"Processing job_id={job_id}, bucket={bucket_name}, output_path={output_path}")
        logger.info(f"Received {len(file_results)} file results")
        
        # Update job status to aggregating
        update_job_status(job_id, 'AGGREGATING', 'Combining processed file contents')
        
        # Check if any files were successfully processed
        successful_files = [result for result in file_results if result.get('status') != 'error']
        logger.info(f"Found {len(successful_files)} successfully processed files out of {len(file_results)}")
        
        if not successful_files:
            error_msg = 'No files were successfully processed'
            logger.error(error_msg)
            update_job_status(job_id, 'ERROR', error_msg)
            return {
                'status': 'error',
                'error': error_msg,
                'job_id': job_id  # Include job_id in the error response
            }
        
        # Combine the processed file contents
        print(prompt_template)
        s3 = boto3.client('s3')
        combined_text = prompt_template + "\n\n"  # Start with the prompt template
        file_count = 0
        processed_files = []
        error_count = 0
        
        for result in successful_files:
            try:
                # Get the processed file content from S3
                file_key = result.get('extracted_text_key')  or result.get('output_key')# Use extracted_text_key instead of output_key
                if not file_key:
                    logger.warning(f"Missing extracted_text_key in result: {json.dumps(result)}")
                    continue
                
                logger.info(f"Getting file content from S3: bucket={bucket_name}, key={file_key}")
                response = s3.get_object(Bucket=bucket_name, Key=file_key)
                file_content = response['Body'].read().decode('utf-8')
                
                # Check if adding this file would exceed the maximum size
                if len(combined_text) + len(file_content) > max_combined_chars:
                    logger.warning(f"Adding file would exceed max_combined_chars ({max_combined_chars})")
                    # If we already have some content, stop adding more
                    if combined_text != prompt_template + "\n\n":
                        logger.info("Already have content, stopping here")
                        break
                    # If this is the first file and it's too large, truncate it
                    logger.info(f"Truncating first file from {len(file_content)} to {max_combined_chars - len(combined_text)} chars")
                    file_content = file_content[:max_combined_chars - len(combined_text)]
                
                # Add file content to combined text
                file_name = result.get('file_name', file_key.split('/')[-1])
                combined_text += f"\n\n--- FILE: {file_name} ---\n\n"
                combined_text += file_content
                file_count += 1
                processed_files.append(file_name)
                logger.info(f"Added file {file_name} to combined text (total files: {file_count})")
                
            except Exception as e:
                error_count += 1
                logger.error(f"Error processing file {result.get('file_key')}: {str(e)}")
                continue
        
        # If no content was aggregated beyond the prompt template, return error
        if combined_text == prompt_template + "\n\n":
            error_msg = 'Failed to aggregate any file content'
            logger.error(error_msg)
            update_job_status(job_id, 'ERROR', error_msg)
            return {
                'status': 'error',
                'error': error_msg,
                'job_id': job_id
            }
        
        # Save the combined content to S3
        full_prompt_key = f"{output_path}/{job_id}/full_prompt.txt"
        logger.info(f"Saving combined content to S3: bucket={bucket_name}, key={full_prompt_key}")
        s3.put_object(
            Bucket=bucket_name,
            Key=full_prompt_key,
            Body=combined_text.encode('utf-8'),
            ContentType='text/plain'
        )
        
        # Update job status
        status_message = f"Combined {file_count} files ({len(combined_text)} characters)"
        if error_count > 0:
            status_message += f", {error_count} files had errors"
        
        update_job_status(job_id, 'AGGREGATED', status_message)
        
        logger.info(f"Successfully aggregated content: {file_count} files, {len(combined_text)} characters")
        return {
            'status': 'success',
            'job_id': job_id,
            'bucket_name': bucket_name,
            'full_prompt_key': full_prompt_key,
            'output_path': output_path,
            'file_count': file_count,
            'char_count': len(combined_text),
            'processed_files': processed_files,
            'error_count': error_count
        }
        
    except Exception as e:
        error_message = f"Aggregation failed: {str(e)}"
        logger.error(error_message)
        
        # Try to update job status
        try:
            if job_id:  # Make sure job_id is available
                update_job_status(job_id, 'ERROR', error_message)
        except Exception as status_error:
            logger.error(f"Failed to update job status: {str(status_error)}")
        
        # Return error with job_id if available
        error_response = {
            'status': 'error',
            'error': error_message
        }
        if job_id:
            error_response['job_id'] = job_id
            
        return error_response
