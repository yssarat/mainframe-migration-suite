import json
import boto3
import botocore
import os
import time
import logging
import traceback
import re
from decimal import Decimal

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Get environment variables
JOBS_TABLE_NAME = os.environ.get('JOBS_TABLE_NAME')
BEDROCK_MODEL_ID = os.environ.get('BEDROCK_MODEL_ID')
PROMPT_PARAMETER_NAME = os.environ.get('PROMPT_PARAMETER_NAME')
ARCHIVE_FOLDER = os.environ.get('ARCHIVE_FOLDER', 'Archive')
IAC_FOLDER = os.environ.get('IAC_FOLDER', 'IaC')

# Get AWS region and account ID
region = os.environ.get('AWS_REGION', 'us-east-1')
sts_client = boto3.client('sts')
account_id = sts_client.get_caller_identity()['Account']

# Initialize global variable for throttling
time_last = 0

# Custom JSON encoder to handle Decimal objects
class CustomJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        # Also handle datetime objects from DynamoDB
        if hasattr(obj, 'isoformat'):
            return obj.isoformat()
        return super(CustomJSONEncoder, self).default(obj)

def create_bedrock_client():
    """
    Creates and returns a Bedrock client with configurable timeout settings.
    
    Returns:
        boto3.client: Configured Bedrock client
    """
    # Get timeout values from environment variables or use defaults
    connect_timeout = int(os.environ.get('BEDROCK_CONNECT_TIMEOUT', 60))
    read_timeout = int(os.environ.get('BEDROCK_READ_TIMEOUT', 600))  # 10 minutes default
    
    # Create a custom configuration with increased timeouts
    config = botocore.config.Config(
        connect_timeout=connect_timeout,
        read_timeout=read_timeout,
        retries={'max_attempts': 5},
        region_name='us-east-1'  # Force us-east-1 region for Bedrock
    )
    
    return boto3.client('bedrock-runtime', config=config)

def call_llm_for_template_fix(template_content, error_message, attempt_number):
    """
    Calls the Bedrock LLM to fix a CloudFormation template based on validation errors.
    Implements exponential backoff with jitter for throttling exceptions.
    
    Args:
        template_content (str): The CloudFormation template content with errors
        error_message (str): The validation error message
        attempt_number (int): The current attempt number
        
    Returns:
        str: The fixed CloudFormation template content
    """
    global time_last
    
    # Calculate base wait time with exponential backoff based on attempt number
    # Start with 60 seconds for first attempt, then increase exponentially
    base_wait_time = 60 * (2 ** (attempt_number - 1))
    
    # Add jitter (random value between 0 and 30% of base wait time)
    import random
    jitter = random.uniform(0, 0.3 * base_wait_time)
    wait_time = base_wait_time + jitter
    
    # Cap the maximum wait time at 5 minutes
    wait_time = min(wait_time, 300)
    
    # Check if we need to wait based on the last API call
    if time.time() - time_last < wait_time:
        actual_wait = wait_time - (time.time() - time_last)
        logger.info(f"Implementing backoff strategy: Sleeping for {actual_wait:.2f} seconds (attempt {attempt_number})")
        time.sleep(actual_wait)
    
    # Maximum number of retries for throttling exceptions
    max_retries = 5
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            # Create Bedrock client
            client = create_bedrock_client()
            model_id = BEDROCK_MODEL_ID or f'arn:aws:bedrock:{region}:{account_id}:inference-profile/us.anthropic.claude-3-7-sonnet-20250219-v1:0'
            logger.info(f"Using Bedrock model: {model_id} for template fix attempt {attempt_number} (retry {retry_count})")
            
            # Prepare the prompt for the LLM
            prompt = f"""
You are an AWS CloudFormation expert. I have a CloudFormation template that failed validation with the following error:

ERROR MESSAGE:
{error_message}

Please fix the template to resolve this error. Return ONLY the fixed template with no additional explanations.

Here is the current template:

{template_content}
"""
            
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
            logger.info(f"Invoking Bedrock model for template fix (attempt {attempt_number}, retry {retry_count})")
            response = client.invoke_model(
                modelId=model_id,
                body=json.dumps(request_body)
            )
            
            # Parse the response
            response_body = json.loads(response['body'].read())
            fixed_template = response_body['content'][0]['text']
            logger.info(f"Successfully received fixed template from Bedrock (attempt {attempt_number})")
            
            # Clean up the response to ensure it's just the template
            # Sometimes the model might include markdown code block markers
            fixed_template = re.sub(r'^```ya?ml\s*', '', fixed_template, flags=re.MULTILINE)
            fixed_template = re.sub(r'^```\s*$', '', fixed_template, flags=re.MULTILINE)
            
            # Update the last API call time
            time_last = time.time()
            return fixed_template
            
        except botocore.exceptions.ClientError as error:
            retry_count += 1
            error_code = error.response.get('Error', {}).get('Code', '')
            
            if error_code == 'ThrottlingException' and retry_count < max_retries:
                # Calculate exponential backoff time for this retry
                retry_wait = (2 ** retry_count) + random.uniform(0, 10)
                logger.warning(f"Throttling exception encountered. Retrying in {retry_wait:.2f} seconds (retry {retry_count}/{max_retries})")
                time.sleep(retry_wait)
                continue
            elif error_code == 'AccessDeniedException':
                error_message = f"Access denied to Bedrock: {error.response['Error']['Message']}"
                logger.error(error_message)
                raise error
            else:
                # If we've exhausted retries or it's another type of error, raise it
                logger.error(f"Error invoking Bedrock model after {retry_count} retries: {str(error)}")
                raise error
        except Exception as e:
            logger.error(f"Unexpected error in call_llm_for_template_fix: {str(e)}")
            raise e
        finally:
            # Always update the last API call time
            time_last = time.time()

def upload_template_to_s3(template_content, s3_location):
    """
    Uploads a CloudFormation template to S3.
    
    Args:
        template_content (str): The CloudFormation template content
        s3_location (str): S3 location where to upload the template (s3://bucket/key)
        
    Returns:
        str: The S3 location of the uploaded template
    """
    logger.info(f"Uploading template to S3: {s3_location}")
    
    # Parse S3 location
    if s3_location.startswith('s3://'):
        s3_location = s3_location[5:]  # Remove 's3://' prefix
    
    parts = s3_location.split('/', 1)
    if len(parts) != 2:
        raise ValueError(f"Invalid S3 location format: {s3_location}")
    
    bucket_name = parts[0]
    object_key = parts[1]
    
    # Upload to S3
    s3 = boto3.client('s3')
    try:
        s3.put_object(
            Bucket=bucket_name,
            Key=object_key,
            Body=template_content.encode('utf-8')
        )
        return f"s3://{bucket_name}/{object_key}"
    except Exception as e:
        logger.error(f"Error uploading template to S3: {str(e)}")
        raise e

def update_job_status(job_id, status, message=None, additional_data=None):
    """
    Updates the status of a job in DynamoDB.
    
    Args:
        job_id (str): Unique job identifier
        status (str): New job status
        message (str): Optional status message
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
    
    # Add message if provided
    if message:
        update_expression += ", message = :message"
        expression_attribute_values[":message"] = message
    
    # Add additional data if provided
    if additional_data and isinstance(additional_data, dict):
        for key, value in additional_data.items():
            if key not in ['job_id', 'status', 'updated_at', 'message']:
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

def get_template_from_s3(s3_location):
    """
    Retrieves a CloudFormation template from S3.
    
    Args:
        s3_location (str): S3 location of the template (s3://bucket/key)
        
    Returns:
        str: Template content
    """
    logger.info(f"Getting template from S3: {s3_location}")
    
    # Parse S3 location
    if s3_location.startswith('s3://'):
        s3_location = s3_location[5:]  # Remove 's3://' prefix
    
    parts = s3_location.split('/', 1)
    if len(parts) != 2:
        raise ValueError(f"Invalid S3 location format: {s3_location}")
    
    bucket_name = parts[0]
    object_key = parts[1]
    
    # Get object from S3
    s3 = boto3.client('s3')
    try:
        response = s3.get_object(
            Bucket=bucket_name,
            Key=object_key
        )
        template_content = response['Body'].read().decode('utf-8')
        return template_content
    except Exception as e:
        logger.error(f"Error getting template from S3: {str(e)}")
        raise e

def extract_parameters_from_template(template_content):
    """
    Extracts parameters and their default values from a CloudFormation template.
    
    Args:
        template_content (str): CloudFormation template content
        
    Returns:
        dict: Dictionary of parameter names and their default values
    """
    logger.info("Extracting parameters from template")
    
    try:
        # Parse template
        if template_content.strip().startswith('{'):
            # JSON template
            template = json.loads(template_content)
        else:
            # YAML template
            import yaml
            template = yaml.safe_load(template_content)
        
        parameters = {}
        
        # Extract parameters and their default values
        if 'Parameters' in template:
            for param_name, param_config in template['Parameters'].items():
                if 'Default' in param_config:
                    parameters[param_name] = param_config['Default']
                else:
                    # For parameters without default values, try to provide sensible defaults
                    param_type = param_config.get('Type', '')
                    
                    if param_type == 'String':
                        parameters[param_name] = 'dummy-value'
                    elif param_type == 'Number':
                        parameters[param_name] = '0'
                    elif param_type == 'AWS::EC2::KeyPair::KeyName':
                        # Skip key pair parameters as they're often optional
                        continue
                    elif param_type == 'AWS::EC2::VPC::Id':
                        # Try to get default VPC
                        try:
                            ec2 = boto3.client('ec2')
                            vpcs = ec2.describe_vpcs(Filters=[{'Name': 'isDefault', 'Values': ['true']}])
                            if vpcs['Vpcs']:
                                parameters[param_name] = vpcs['Vpcs'][0]['VpcId']
                        except Exception:
                            # Skip if we can't get a default VPC
                            continue
                    elif param_type == 'AWS::EC2::Subnet::Id':
                        # Try to get a subnet in the default VPC
                        try:
                            ec2 = boto3.client('ec2')
                            vpcs = ec2.describe_vpcs(Filters=[{'Name': 'isDefault', 'Values': ['true']}])
                            if vpcs['Vpcs']:
                                default_vpc_id = vpcs['Vpcs'][0]['VpcId']
                                subnets = ec2.describe_subnets(
                                    Filters=[{'Name': 'vpc-id', 'Values': [default_vpc_id]}]
                                )
                                if subnets['Subnets']:
                                    parameters[param_name] = subnets['Subnets'][0]['SubnetId']
                        except Exception:
                            # Skip if we can't get a subnet
                            continue
                    elif param_type == 'AWS::EC2::SecurityGroup::Id':
                        # Skip security group parameters as they're often specific
                        continue
                    elif param_type == 'CommaDelimitedList':
                        parameters[param_name] = 'value1,value2,value3'
                    elif param_type.startswith('List<'):
                        parameters[param_name] = 'value1,value2,value3'
                    else:
                        # For other parameter types, use a generic string
                        parameters[param_name] = 'dummy-value'
        
        logger.info(f"Extracted parameters: {json.dumps(parameters)}")
        return parameters
    
    except Exception as e:
        logger.error(f"Error extracting parameters from template: {str(e)}")
        logger.error(traceback.format_exc())
        return {}

def validate_template_syntax(template_content):
    """
    Validates template syntax using CloudFormation ValidateTemplate API.
    
    Args:
        template_content (str): CloudFormation template content
        
    Returns:
        tuple: (is_valid, error_message)
    """
    logger.info("Validating template syntax")
    
    try:
        cfn = boto3.client('cloudformation')
        cfn.validate_template(TemplateBody=template_content)
        logger.info("Template syntax validation successful")
        return True, None
    except botocore.exceptions.ClientError as e:
        error_message = e.response['Error']['Message']
        logger.error(f"Template syntax validation failed: {error_message}")
        return False, error_message

def validate_with_changeset(template_content, job_id, parameters=None):
    """
    Validates a CloudFormation template by creating a change set without executing it.
    
    Args:
        template_content (str): CloudFormation template content
        job_id (str): Unique job identifier
        parameters (dict, optional): Dictionary of parameter key-value pairs
        
    Returns:
        tuple: (is_valid, validation_details)
    """
    logger.info("Validating template with change set")
    
    cfn = boto3.client('cloudformation')
    timestamp = int(time.time())
    stack_name = f"validation-{job_id[:8]}-{timestamp}"
    change_set_name = f"validation-{job_id[:8]}-{timestamp}"
    
    # Prepare parameters if provided
    cfn_parameters = []
    if parameters:
        for key, value in parameters.items():
            cfn_parameters.append({
                'ParameterKey': key,
                'ParameterValue': str(value)
            })
    
    try:
        # Create the change set
        response = cfn.create_change_set(
            StackName=stack_name,
            TemplateBody=template_content,
            ChangeSetName=change_set_name,
            ChangeSetType="CREATE",
            Description="Validation change set",
            Parameters=cfn_parameters,
            Capabilities=[
                'CAPABILITY_IAM',
                'CAPABILITY_NAMED_IAM',
                'CAPABILITY_AUTO_EXPAND'
            ]
        )
        
        change_set_id = response['Id']
        
        # Wait for change set creation to complete
        waiter = cfn.get_waiter('change_set_create_complete')
        try:
            waiter.wait(
                ChangeSetName=change_set_id,
                WaiterConfig={
                    'Delay': 5,
                    'MaxAttempts': 20
                }
            )
            
            # Get the change set details
            change_set = cfn.describe_change_set(ChangeSetName=change_set_id)
            
            # Template is valid if the change set was created successfully
            validation_details = {
                'status': 'VALID',
                'changes_count': len(change_set.get('Changes', [])),
                'capabilities': change_set.get('Capabilities', []),
                'description': "Template validation successful"
            }
            
            logger.info("Change set validation successful")
            return True, validation_details
            
        except botocore.exceptions.WaiterError:
            # The change set creation failed, get the reason
            change_set = cfn.describe_change_set(ChangeSetName=change_set_id)
            
            # Special case: No changes is actually valid for our validation purpose
            if change_set['Status'] == 'FAILED' and "didn't contain changes" in change_set.get('StatusReason', ''):
                validation_details = {
                    'status': 'VALID',
                    'description': "Template is valid but would create no changes"
                }
                logger.info("Template is valid but would create no changes")
                return True, validation_details
            
            # Otherwise, it's an actual validation failure
            validation_details = {
                'status': 'INVALID',
                'reason': change_set.get('StatusReason', 'Unknown validation error'),
                'description': "Template validation failed"
            }
            logger.error(f"Change set validation failed: {change_set.get('StatusReason', 'Unknown validation error')}")
            return False, validation_details
            
    except botocore.exceptions.ClientError as e:
        # Handle client errors (permissions, invalid template, etc.)
        error_message = e.response['Error']['Message']
        validation_details = {
            'status': 'INVALID',
            'reason': error_message,
            'description': "Template validation failed"
        }
        logger.error(f"Change set validation failed with client error: {error_message}")
        return False, validation_details
        
    finally:
        # Clean up: Delete the change set and the stack if it was created
        try:
            if 'change_set_id' in locals():
                logger.info(f"Cleaning up change set: {change_set_id}")
                cfn.delete_change_set(ChangeSetName=change_set_id)
                
            # Check if the stack exists and delete it if it does
            try:
                cfn.describe_stacks(StackName=stack_name)
                logger.info(f"Cleaning up stack: {stack_name}")
                cfn.delete_stack(StackName=stack_name)
            except botocore.exceptions.ClientError:
                # Stack doesn't exist, which is fine
                pass
                
        except Exception as cleanup_error:
            # Log cleanup errors but don't fail the validation
            logger.warning(f"Cleanup error: {str(cleanup_error)}")

def lambda_handler(event, context):
    """
    Lambda function handler that validates CloudFormation templates.
    If validation fails, it attempts to fix the template using Bedrock LLM.
    
    Expected event structure:
    {
        "job_id": "12345678-abcd-1234-efgh-123456789012",
        "s3_location": "s3://bucket/path/to/template.yaml",
        "perform_changeset_validation": true,
        "max_fix_attempts": 5
    }
    """
    logger.info("Validation Lambda handler started")
    logger.info(f"Received event: {json.dumps(event)}")
    
    try:
        # Check required parameters
        required_params = ['job_id', 's3_location']
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
        s3_location = event['s3_location']
        perform_changeset_validation = event.get('perform_changeset_validation', True)
        max_fix_attempts = event.get('max_fix_attempts', 5)
        fix_attempt = event.get('fix_attempt', 0)
        
        # Update job status to VALIDATING
        update_job_status(job_id, 'VALIDATING', f"Validating CloudFormation template (attempt {fix_attempt + 1})")
        
        # Get the template from S3
        template_content = get_template_from_s3(s3_location)
        
        # First-level validation (syntax)
        syntax_valid, syntax_errors = validate_template_syntax(template_content)
        if not syntax_valid:
            # Check if we should attempt to fix the template
            if fix_attempt < max_fix_attempts:
                logger.info(f"Template syntax validation failed. Attempting to fix (attempt {fix_attempt + 1})")
                update_job_status(job_id, 'FIXING', f"Attempting to fix template syntax errors (attempt {fix_attempt + 1})")
                
                # Call LLM to fix the template
                fixed_template = call_llm_for_template_fix(template_content, syntax_errors, fix_attempt + 1)
                
                # Upload the fixed template to S3
                upload_template_to_s3(fixed_template, s3_location)
                
                # Recursively call the validation function with the fixed template
                event['fix_attempt'] = fix_attempt + 1
                return lambda_handler(event, context)
            else:
                # Max attempts reached, return failure
                logger.error(f"Max fix attempts reached ({max_fix_attempts}). Template validation failed.")
                update_job_status(job_id, 'VALIDATION_FAILED', 
                                 f"Template syntax validation failed after {max_fix_attempts} fix attempts: {syntax_errors}")
                return {
                    'job_id': job_id,
                    'validation_status': 'FAILED',
                    'validation_errors': syntax_errors,
                    's3_location': s3_location,
                    'fix_attempts': fix_attempt
                }
        
        # Second-level validation (change set)
        if perform_changeset_validation:
            # Extract parameters from the template
            parameters = extract_parameters_from_template(template_content)
            
            # Validate with change set
            changeset_valid, validation_details = validate_with_changeset(template_content, job_id, parameters)
            if not changeset_valid:
                # Check if we should attempt to fix the template
                if fix_attempt < max_fix_attempts:
                    logger.info(f"Template deployment validation failed. Attempting to fix (attempt {fix_attempt + 1})")
                    update_job_status(job_id, 'FIXING', 
                                     f"Attempting to fix template deployment errors (attempt {fix_attempt + 1})")
                    
                    # Call LLM to fix the template
                    error_message = validation_details.get('reason', 'Unknown error')
                    fixed_template = call_llm_for_template_fix(template_content, error_message, fix_attempt + 1)
                    
                    # Upload the fixed template to S3
                    upload_template_to_s3(fixed_template, s3_location)
                    
                    # Recursively call the validation function with the fixed template
                    event['fix_attempt'] = fix_attempt + 1
                    return lambda_handler(event, context)
                else:
                    # Max attempts reached, return failure
                    logger.error(f"Max fix attempts reached ({max_fix_attempts}). Template validation failed.")
                    update_job_status(
                        job_id, 
                        'VALIDATION_FAILED', 
                        f"Template deployment validation failed after {max_fix_attempts} fix attempts: {validation_details.get('reason', 'Unknown error')}"
                    )
                    return {
                        'job_id': job_id,
                        'validation_status': 'FAILED',
                        'validation_errors': validation_details.get('reason', 'Unknown error'),
                        's3_location': s3_location,
                        'fix_attempts': fix_attempt
                    }
        
        # All validations passed
        update_job_status(job_id, 'VALIDATED', 'Template validation successful', 
                         {'fix_attempts': fix_attempt})
        return {
            'job_id': job_id,
            'validation_status': 'PASSED',
            'validation_message': 'Template validation successful',
            's3_location': s3_location,
            'fix_attempts': fix_attempt
        }
            
    except Exception as e:
        logger.error(f"Error occurred: {str(e)}")
        logger.error(f"Error type: {type(e).__name__}")
        logger.error(f"Traceback:\n{traceback.format_exc()}")
        
        # Update job status to ERROR if job_id is available
        if 'job_id' in event:
            update_job_status(event['job_id'], 'VALIDATION_FAILED', str(e))
        
        # Re-raise the exception to be handled by Step Functions
        raise e
