import json
import boto3
import botocore
import botocore.config
import os
import re
import time
import zipfile
import io
import logging
import traceback
import decimal
from collections import defaultdict

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize global variable for throttling
time_last = 0

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

def update_job_status(job_id, status, message=None):
    """
    Updates the status of a job in DynamoDB.
    
    Args:
        job_id (str): Unique job identifier
        status (str): New job status
        message (str): Optional status message
        
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
    
    # Add message if provided
    if message:
        update_expression += ", message = :message"
        expression_attribute_values[":message"] = message
    
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

def get_prompt_from_parameter_store():
    """
    Retrieves the CloudFormation template generation prompt from Parameter Store.
    If not found, uses the default prompt.
    
    Returns:
        str: The prompt template
    """
    try:
        # Get parameter store path from environment variable or use default
        parameter_name = os.environ.get('PROMPT_PARAMETER_NAME', '/mainframe-modernization/cfn-generator/template-prompt')
        
        logger.info(f"Retrieving prompt from Parameter Store: {parameter_name}")
        ssm = boto3.client('ssm')
        response = ssm.get_parameter(
            Name=parameter_name,
            WithDecryption=True
        )
        return response['Parameter']['Value']
    except Exception as e:
        logger.warning(f"Failed to retrieve prompt from Parameter Store: {str(e)}")
        logger.info("Using default prompt")
        
        # Default prompt with both {bucket_name} and {s3_folder} placeholders
        return """
You are an AWS Solutions Architect. Create a CloudFormation template for the AWS resources in S3 bucket: {bucket_name}, folder: {s3_folder}.
The S3 folder contains the following resource configurations:
{chunk_contents}

Create a CloudFormation template with all necessary resources.
Include all necessary properties, IAM roles, and security settings.
Output the template in YAML format.
"""

def scan_s3_folder_recursively(bucket_name, prefix):
    """
    Recursively scans an S3 folder and returns a list of all objects with their contents.
    
    Args:
        bucket_name (str): S3 bucket name
        prefix (str): Prefix (folder path) to scan
        
    Returns:
        list: List of dictionaries containing object information and contents
    """
    logger.info(f"Scanning S3 folder recursively: s3://{bucket_name}/{prefix}")
    s3 = boto3.client('s3')
    objects = []
    
    # Ensure prefix ends with a slash if it's not empty
    if prefix and not prefix.endswith('/'):
        prefix = prefix + '/'
    
    # Initialize pagination
    continuation_token = None
    
    # Maximum file size to download (in bytes) - 1MB
    MAX_FILE_SIZE = 1024 * 1024
    
    try:
        while True:
            # Prepare list_objects_v2 parameters
            list_params = {
                'Bucket': bucket_name,
                'Prefix': prefix,
                'MaxKeys': 1000  # Maximum allowed by S3 API
            }
            
            # Add continuation token if we have one
            if continuation_token:
                list_params['ContinuationToken'] = continuation_token
            
            # List objects
            response = s3.list_objects_v2(**list_params)
            
            # Process objects
            if 'Contents' in response:
                for obj in response['Contents']:
                    # Skip "folder" objects (objects that end with '/' and have size 0)
                    if not (obj['Key'].endswith('/') and obj['Size'] == 0):
                        obj_info = {
                            'Key': obj['Key'],
                            'Size': obj['Size'],
                            'LastModified': obj['LastModified'].isoformat(),
                            'ETag': obj['ETag']
                        }
                        
                        # Only download content for files smaller than MAX_FILE_SIZE
                        if obj['Size'] <= MAX_FILE_SIZE:
                            try:
                                # Get file extension to determine if it's a text file
                                _, ext = os.path.splitext(obj['Key'])
                                ext = ext.lower() if ext else ''
                                
                                # List of text file extensions we want to process
                                text_extensions = ['.txt', '.json', '.yaml', '.yml', '.sql', '.py', '.js', '.java', 
                                                  '.c', '.cpp', '.h', '.cs', '.html', '.css', '.xml', '.md', '.sh', 
                                                  '.bat', '.ps1', '.tf', '.hcl', '.config', '.ini', '.properties']
                                
                                # Only download content for text files
                                if ext in text_extensions:
                                    logger.info(f"Downloading content for {obj['Key']}")
                                    response = s3.get_object(Bucket=bucket_name, Key=obj['Key'])
                                    content = response['Body'].read().decode('utf-8', errors='replace')
                                    obj_info['Content'] = content
                                else:
                                    obj_info['Content'] = f"[Binary file or unsupported format: {ext}]"
                            except Exception as e:
                                logger.error(f"Error downloading content for {obj['Key']}: {str(e)}")
                                obj_info['Content'] = f"[Error reading file: {str(e)}]"
                        else:
                            obj_info['Content'] = f"[File too large: {obj['Size']} bytes]"
                        
                        objects.append(obj_info)
            
            # Check if there are more objects to fetch
            if not response.get('IsTruncated'):
                break
            
            continuation_token = response.get('NextContinuationToken')
    
    except botocore.exceptions.ClientError as e:
        logger.error(f"Error scanning S3 folder {prefix}: {str(e)}")
        raise e
    
    logger.info(f"Found {len(objects)} objects in S3 folder")
    return objects

def format_s3_contents_for_prompt(bucket_name, s3_folder, objects):
    """
    Formats the S3 contents for the CloudFormation template generation prompt.
    
    Args:
        bucket_name (str): S3 bucket name
        s3_folder (str): S3 folder path
        objects (list): List of S3 objects
        
    Returns:
        dict: Formatted S3 contents for the prompt
    """
    logger.info("Formatting S3 contents for prompt")
    
    formatted_contents = {
        'bucket_name': bucket_name,
        's3_folder': s3_folder,
        'total_files': len(objects),
        'files_by_extension': defaultdict(list),
        'directories': defaultdict(list),
        'file_contents': {}
    }
    
    # Group files by extension and directory
    for obj in objects:
        key = obj['Key']
        
        # Group by file extension
        _, ext = os.path.splitext(key)
        if ext:
            ext = ext[1:]  # Remove the dot
        else:
            ext = 'unknown'
        formatted_contents['files_by_extension'][ext].append(key)
        
        # Group by directory structure
        dir_path = os.path.dirname(key)
        formatted_contents['directories'][dir_path].append(key)
        
        # Store file content if available
        if 'Content' in obj:
            formatted_contents['file_contents'][key] = obj['Content']
    
    # Convert defaultdicts to regular dicts for JSON serialization
    formatted_contents['files_by_extension'] = dict(formatted_contents['files_by_extension'])
    formatted_contents['directories'] = dict(formatted_contents['directories'])
    
    return formatted_contents

def verify_s3_objects_exist(bucket_name, s3_folder):
    """
    Verifies that the required S3 objects exist and recursively scans the folder.
    
    Args:
        bucket_name (str): S3 bucket name
        s3_folder (str): S3 folder path
        
    Returns:
        tuple: (bool, str, dict) - (exists, error_message, s3_contents)
    """
    logger.info(f"Verifying S3 objects exist in bucket: {bucket_name}, folder: {s3_folder}")
    s3 = boto3.client('s3')
    
    try:
        # Check if bucket exists
        s3.head_bucket(Bucket=bucket_name)
        
        # Scan the S3 folder recursively
        objects = scan_s3_folder_recursively(bucket_name, s3_folder)
        if not objects:
            return False, f"S3 folder is empty or not found: {s3_folder}", None
        
        # Format the S3 contents for the prompt
        s3_contents = format_s3_contents_for_prompt(bucket_name, s3_folder, objects)
        
        return True, "", s3_contents
        
    except botocore.exceptions.ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', '')
        
        if error_code == '404':
            return False, f"S3 object not found: {e.response['Error']['Message']}", None
        elif error_code == '403':
            return False, f"Access denied to S3: {e.response['Error']['Message']}", None
        else:
            return False, f"Error accessing S3: {str(e)}", None

def create_bedrock_client():
    """
    Creates and returns a Bedrock client with configurable timeout settings.
    
    Returns:
        boto3.client: Configured Bedrock client
    """
    # Get timeout values from environment variables or use defaults
    connect_timeout = int(os.environ.get('BEDROCK_CONNECT_TIMEOUT', 60))
    read_timeout = int(os.environ.get('BEDROCK_READ_TIMEOUT', 300))  # 5 minutes default
    
    # Create a custom configuration with increased timeouts
    config = botocore.config.Config(
        connect_timeout=connect_timeout,
        read_timeout=read_timeout,
        retries={'max_attempts': 3},
        region_name='us-east-1'  # Force us-east-1 region for Bedrock
    )
    
    return boto3.client('bedrock-runtime', config=config)

def call_llm_converse(prompt, wait=False):
    """
    Calls the Bedrock LLM directly using boto3 with the given prompt.

    Args:
        prompt (str): The prompt to send to the LLM.
        wait (bool): Whether to wait if throttling is needed.

    Returns:
        str: The response from the LLM.
    """
    # checks if its been more than 60 seconds since the last LLM call to avoid forced throttling
    global time_last

    if wait:
        if time.time() - time_last < 60:
            wait_time = 60 - (time.time() - time_last)
            logger.info(f"Sleeping for {wait_time:.2f} seconds to avoid forced throttling...")
            time.sleep(wait_time)
    
    try:
        # Create Bedrock client
        client = create_bedrock_client()
        model_id = os.environ.get('BEDROCK_MODEL_ID', 'us.anthropic.claude-3-7-sonnet-20250219-v1:0')
        logger.info(f"Using Bedrock model: {model_id}")
        
        # Prepare the request body
        request_body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 9162,
            "temperature": 0,
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        }
        
        # Invoke the model
        logger.info("Invoking Bedrock model")
        response = client.invoke_model(
            modelId=model_id,
            body=json.dumps(request_body)
        )
        
        # Parse the response
        response_body = json.loads(response['body'].read())
        content = response_body['content'][0]['text']
        logger.info("Successfully received response from Bedrock")
        
    except botocore.exceptions.ClientError as error:
        if error.response['Error']['Code'] == 'AccessDeniedException':
            error_message = f"\x1b[41m{error.response['Error']['Message']}\
                    \nTo troubeshoot this issue please refer to the following resources.\
                    \nhttps://docs.aws.amazon.com/IAM/latest/UserGuide/troubleshoot_access-denied.html\
                    \nhttps://docs.aws.amazon.com/bedrock/latest/userguide/security-iam.html\x1b[0m\n"
            logger.error(error_message)
        raise error
        
    finally:
        # Updates time_last to current time
        time_last = time.time()

    return content

def zip_and_archive_config_files(bucket_name, objects):
    """
    Zips the configuration files and moves them to an archive folder.
    
    Args:
        bucket_name (str): S3 bucket name
        objects (list): List of S3 objects
        
    Returns:
        str: S3 location of the zipped file
    """
    logger.info("Zipping and archiving configuration files")
    s3 = boto3.client('s3')
    
    # Create a zip file in memory
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'a', zipfile.ZIP_DEFLATED, False) as zip_file:
        # Add each config file to the zip file
        for obj in objects:
            key = obj['Key']
            try:
                # Get the file content from S3
                response = s3.get_object(
                    Bucket=bucket_name,
                    Key=key
                )
                content = response['Body'].read()
                
                # Add the file to the zip
                zip_file.writestr(key, content)
                logger.info(f"Added file to archive: {key}")
            except botocore.exceptions.ClientError as e:
                logger.error(f"Error getting file {key}: {str(e)}")
    
    # Set the buffer position to the beginning
    zip_buffer.seek(0)
    
    # Create archive folder if it doesn't exist
    archive_folder = os.environ.get('ARCHIVE_FOLDER', 'Archive')
    timestamp = int(time.time())
    zip_key = f"{archive_folder}/config_files_{timestamp}.zip"
    
    try:
        # Upload the zip file to S3
        s3.put_object(
            Bucket=bucket_name,
            Key=zip_key,
            Body=zip_buffer.getvalue()
        )
        
        return f"s3://{bucket_name}/{zip_key}"
    except botocore.exceptions.ClientError as e:
        logger.error(f"Error during zip archive creation: {str(e)}")
        raise e

def zip_and_archive_cfn_template(bucket_name, template_key, template_content):
    """
    Zips the CloudFormation template and moves it to an archive folder.
    Original file is preserved.
    
    Args:
        bucket_name (str): S3 bucket name
        template_key (str): Key of the CloudFormation template in S3
        template_content (str): Content of the CloudFormation template
        
    Returns:
        str: S3 location of the zipped file
    """
    logger.info("Zipping and archiving CloudFormation template")
    s3 = boto3.client('s3')
    
    # Create a zip file in memory
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'a', zipfile.ZIP_DEFLATED, False) as zip_file:
        # Add the CloudFormation template to the zip file
        file_name = os.path.basename(template_key)
        zip_file.writestr(file_name, template_content)
    
    # Set the buffer position to the beginning
    zip_buffer.seek(0)
    
    # Create archive folder if it doesn't exist
    archive_folder = os.environ.get('ARCHIVE_FOLDER', 'Archive')
    timestamp = int(time.time())
    zip_key = f"{archive_folder}/cfn_template_{timestamp}.zip"
    
    try:
        # Upload the zip file to S3
        s3.put_object(
            Bucket=bucket_name,
            Key=zip_key,
            Body=zip_buffer.getvalue()
        )
        
        # Note: We're NOT deleting the original file as requested
        logger.info(f"CloudFormation template archived at: s3://{bucket_name}/{zip_key}")
        
        return f"s3://{bucket_name}/{zip_key}"
    except botocore.exceptions.ClientError as e:
        logger.error(f"Error during zip archive creation: {str(e)}")
        raise e

def lambda_handler(event, context):
    """
    Lambda function handler that generates CloudFormation templates.
    
    Expected event structure:
    {
        "job_id": "12345678-abcd-1234-efgh-123456789012",
        "bucket_name": "my-resource-configs",
        "s3_folder": "resources/lambda"
    }
    """
    logger.info("Generator Lambda handler started")
    logger.info(f"Received event: {json.dumps(event)}")
    
    try:
        # Check required parameters
        required_params = ['job_id', 'bucket_name', 's3_folder']
        missing_params = [param for param in required_params if param not in event]
        if missing_params:
            error_message = f"Missing required parameters: {', '.join(missing_params)}"
            logger.error(error_message)
            return {
                'statusCode': 400,
                'body': json.dumps({'message': error_message})
            }
        
        # Extract parameters
        job_id = event['job_id']
        bucket_name = event['bucket_name']
        s3_folder = event['s3_folder'].rstrip('/')
        
        # Update job status to PROCESSING
        update_job_status(job_id, 'PROCESSING', 'Generating CloudFormation template')
        
        # Verify S3 objects exist and recursively scan folder
        logger.info(f"Verifying S3 objects in bucket: {bucket_name}, folder: {s3_folder}")
        objects_exist, error_message, s3_contents = verify_s3_objects_exist(bucket_name, s3_folder)
        if not objects_exist:
            logger.error(f"S3 object verification failed: {error_message}")
            update_job_status(job_id, 'ERROR', error_message)
            return {
                'statusCode': 404,
                'body': json.dumps({'message': error_message})
            }
        
        # Get the prompt template from Parameter Store
        prompt_template = get_prompt_from_parameter_store()
        
        # Format the CloudFormation template generation prompt
        logger.info("Formatting CloudFormation template generation prompt")
        s3_contents_json = json.dumps(s3_contents, indent=2)
        
        # Use a fallback template in case of formatting errors
        try:
            # Try to format the template with the parameters from the SSM parameter
            # The SSM parameter uses {bucket_name} instead of {s3_bucket}
            prompt = prompt_template.format(
                bucket_name=bucket_name,
                s3_folder=s3_folder,
                chunk_index=1,
                total_chunks=1,
                chunk_contents=s3_contents_json
            )
            logger.info("Successfully formatted prompt template")
        except KeyError as e:
            # If that fails, use a fallback template
            logger.warning(f"Template format error: {str(e)}. Using fallback template.")
            prompt = f"""
Generate a CloudFormation template for resources in bucket: {bucket_name}, folder: {s3_folder}.
Resource configurations:
{s3_contents_json}
"""
        
        # Call LLM for CloudFormation template generation
        logger.info("Calling LLM for CloudFormation template generation")
        cfn_template = call_llm_converse(prompt, wait=True)
        
        # Upload the CloudFormation template to S3
        logger.info("Uploading CloudFormation template to S3")
        iac_folder = os.environ.get('IAC_FOLDER', 'IaC')
        timestamp = int(time.time())
        output_key = f"{iac_folder.rstrip('/')}/cloudformation_template_{timestamp}.yaml"
        
        s3 = boto3.client('s3')
        s3.put_object(
            Bucket=bucket_name,
            Key=output_key,
            Body=cfn_template.encode('utf-8')
        )
        
        # Zip the CloudFormation template and move it to the archive folder
        logger.info("Zipping CloudFormation template and moving to archive folder")
        zip_location = zip_and_archive_cfn_template(bucket_name, output_key, cfn_template)
        
        # Get the S3 objects that were scanned during verification
        objects = scan_s3_folder_recursively(bucket_name, s3_folder)
        
        # Zip and archive config files (but don't delete them)
        logger.info("Zipping and archiving config files")
        config_zip_location = zip_and_archive_config_files(bucket_name, objects)
        
        # Prepare success response
        s3_location = f"s3://{bucket_name}/{output_key}"
        response_data = {
            'job_id': job_id,
            's3_location': s3_location,
            'zip_location': zip_location,
            'config_zip_location': config_zip_location
        }
        
        logger.info("CloudFormation template generation completed successfully")
        
        return response_data
            
    except Exception as e:
        logger.error(f"Error occurred: {str(e)}")
        logger.error(f"Error type: {type(e).__name__}")
        logger.error(f"Traceback:\n{traceback.format_exc()}")
        
        # Update job status to ERROR if job_id is available
        if 'job_id' in event:
            update_job_status(event['job_id'], 'ERROR', str(e))
        
        # Re-raise the exception to be handled by Step Functions
        raise e
