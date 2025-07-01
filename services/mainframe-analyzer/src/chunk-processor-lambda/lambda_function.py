import json
import boto3
import botocore
import botocore.config
import os
import time
import traceback
from typing import Dict, Any

# Initialize clients
s3_client = boto3.client('s3')
dynamodb = boto3.resource('dynamodb')
ssm_client = boto3.client('ssm')

# Initialize global variable for throttling
time_last = 0

def update_job_status(job_id: str, status: str, message: str = None) -> None:
    """Updates the job status in DynamoDB."""
    table_name = os.environ.get('JOBS_TABLE_NAME', 'MainframeAnalyzerJobs')
    
    try:
        table = dynamodb.Table(table_name)
        update_expression = 'SET #status = :status, updated_at = :time'
        expression_attr_names = {'#status': 'status'}
        expression_attr_values = {
            ':status': status,
            ':time': int(time.time())
        }
        
        if message:
            update_expression += ', status_message = :message'
            expression_attr_values[':message'] = message
        
        table.update_item(
            Key={'job_id': job_id},
            UpdateExpression=update_expression,
            ExpressionAttributeNames=expression_attr_names,
            ExpressionAttributeValues=expression_attr_values
        )
    except Exception as e:
        print(f"Error updating job status: {str(e)}")

def get_prompt_template(template_path: str) -> str:
    """Retrieves the prompt template from Parameter Store."""
    try:
        response = ssm_client.get_parameter(
            Name=template_path,
            WithDecryption=True
        )
        return response['Parameter']['Value']
    except Exception as e:
        print(f"Error retrieving prompt template: {str(e)}")
        # Return a default template if the parameter doesn't exist
        return """
        You are an expert in AWS architecture and mainframe modernization. Analyze the following mainframe code and generate detailed AWS artifacts that would be needed to implement this functionality in AWS.

        For each AWS service type, provide complete, implementation-ready code and configurations, not just summaries.

        {content}

        Organize your response by AWS service type, using the following format:
        
        ## LAMBDA_FUNCTIONS
        [Provide complete Lambda function code]
        
        ## IAM_ROLES
        [Provide complete IAM role definitions in JSON]
        
        ## DYNAMODB
        [Provide complete DynamoDB table definitions in JSON]
        
        ## S3
        [Provide S3 bucket configurations and policies]
        
        ## SQS_SNS_EVENTBRIDGE
        [Provide queue, topic, and rule definitions]
        
        ## STEP_FUNCTIONS
        [Provide complete state machine definitions]
        
        ## AWS_GLUE
        [Provide Glue job and crawler definitions]
        
        ## OTHER_SERVICES
        [Any other relevant AWS services]
        
        Be thorough and provide actual implementations, not just descriptions.
        """

def estimate_token_count(text: str) -> int:
    """Estimates the token count for a given text."""
    char_count = len(text)
    token_count = char_count // 4
    
    print(f"[TOKEN ESTIMATION] Character count: {char_count:,}")
    print(f"[TOKEN ESTIMATION] Estimated token count: {token_count:,}")
    
    return token_count

def calculate_adaptive_timeout(prompt_length: int, base_timeout: int = 120) -> int:
    """Calculates an adaptive timeout based on input length."""
    timeout = base_timeout
    estimated_tokens = prompt_length // 4
    
    if estimated_tokens < 5000:
        timeout += (prompt_length // 10000) * 30
        scaling_type = "Small input scaling"
    elif estimated_tokens < 20000:
        timeout += (prompt_length // 10000) * 45
        scaling_type = "Medium input scaling"
    else:
        timeout += (prompt_length // 10000) * 60
        scaling_type = "Large input scaling"
    
    print(f"[TIMEOUT] {scaling_type}: {timeout}s for ~{estimated_tokens:,} tokens")
    
    return min(timeout, 600)

def create_bedrock_client():
    """Creates and returns a Bedrock client."""
    return boto3.client('bedrock-runtime')

def call_llm_converse(prompt: str, wait: bool = False, timeout_seconds: int = None, max_retries: int = 1) -> str:
    """Calls the Bedrock LLM with the given prompt."""
    global time_last

    print(f"[BEDROCK] Starting call with prompt of {len(prompt):,} characters")

    if wait and time.time() - time_last < 60:
        wait_time = 60 - (time.time() - time_last)
        print(f"[BEDROCK] Waiting {wait_time:.2f}s to avoid throttling")
        time.sleep(wait_time)
    
    prompt_length = len(prompt)
    estimated_tokens = estimate_token_count(prompt)
    
    # Get max tokens threshold from environment variable or use default
    max_tokens_threshold = int(os.environ.get('MAX_TOKENS_THRESHOLD', 20000))
    
    if estimated_tokens > max_tokens_threshold:
        return "Error: Input is too large for processing."
    
    if timeout_seconds is None:
        timeout_seconds = calculate_adaptive_timeout(prompt_length)
    
    try:
        client = create_bedrock_client()
        model_id = os.environ.get('BEDROCK_MODEL_ID', 'us.anthropic.claude-3-7-sonnet-20250219-v1:0')
        
        # For Claude models, use the correct format with system as a top-level parameter
        request_body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 15000,
            "temperature": 0,
            "top_p": 0.9,
            "system": "You are an expert in AWS architecture and mainframe modernization.",
            "messages": [
                {"role": "user", "content": prompt}
            ]
        }
        
        config = botocore.config.Config(
            read_timeout=timeout_seconds,
            connect_timeout=timeout_seconds,
            retries={'max_attempts': 2}
        )
        
        client_with_timeout = boto3.client('bedrock-runtime', config=config)
        
        print(f"[BEDROCK] Invoking model with {timeout_seconds}s timeout")
        start_time = time.time()
        response = client_with_timeout.invoke_model(
            modelId=model_id,
            body=json.dumps(request_body)
        )
        duration = time.time() - start_time
        
        response_body = json.loads(response['body'].read())
        content = response_body['content'][0]['text']
        
        print(f"[BEDROCK] Call completed in {duration:.2f}s")
        
        return content
            
    except Exception as e:
        print(f"[BEDROCK ERROR] {str(e)}")
        return f"Error: {str(e)}"
    finally:
        time_last = time.time()

def parse_llm_response_by_service(llm_response: str) -> Dict[str, str]:
    """Parses the LLM response to extract content for different AWS service types."""
    print(f"[PARSING] Starting to parse response of {len(llm_response):,} characters")
    
    service_markers = [
        "LAMBDA_FUNCTIONS", "IAM_ROLES", "CLOUDFORMATION", "DYNAMODB",
        "RDS", "API_GATEWAY", "AWS_GLUE", "S3", "SQS_SNS_EVENTBRIDGE",
        "STEP_FUNCTIONS", "OTHER_SERVICES"
    ]
    
    service_contents = {}
    
    # Find all sections in the response
    for i, marker in enumerate(service_markers):
        section_start = llm_response.find(f"## {marker}")
        
        if section_start == -1:
            continue
            
        # Find the end of this section (start of next section or end of text)
        section_end = len(llm_response)
        for next_marker in service_markers:
            next_start = llm_response.find(f"## {next_marker}", section_start + len(marker) + 3)
            if next_start != -1 and next_start < section_end:
                section_end = next_start
        
        # Extract the section content
        section_content = llm_response[section_start:section_end].strip()
        service_contents[marker] = section_content
    
    # If no sections were found, return the entire response under OTHER_SERVICES
    if not service_contents:
        service_contents["OTHER_SERVICES"] = f"## OTHER_SERVICES\n\n{llm_response}"
    
    return service_contents

def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Processes a chunk of the mainframe documentation and analyzes it.
    """
    print("=== CHUNK PROCESSOR LAMBDA HANDLER STARTED ===")
    
    try:
        # Extract parameters from the event
        job_id = event.get('job_id')
        bucket_name = event.get('bucket_name')
        chunk_key = event.get('chunk_key')
        chunk_index = event.get('chunk_index')
        total_chunks = event.get('total_chunks')
        output_path = event.get('output_path')
        
        print(f"[JOB] ID: {job_id}, Chunk: {chunk_index}/{total_chunks}")
        
        # Validate required parameters
        if not all([job_id, bucket_name, chunk_key, chunk_index, total_chunks]):
            error_message = "Missing required parameters"
            return {'status': 'error', 'error': error_message}
        
        # Update job status
        update_job_status(job_id, 'PROCESSING', f"Processing chunk {chunk_index} of {total_chunks}")
        
        # Get the chunk content from S3
        response = s3_client.get_object(Bucket=bucket_name, Key=chunk_key)
        chunk_content = response['Body'].read().decode('utf-8')
        
        # Get prompt template from Parameter Store
        prompt_template_path = os.environ.get('PROMPT_TEMPLATE_PATH', '/mainframe-modernization/documentation-agent/updated-prompt')
        prompt_template = get_prompt_template(prompt_template_path)
        
        # Apply template to chunk content
        formatted_prompt = prompt_template.replace("{content}", chunk_content)
        
        # Call Bedrock to analyze the chunk with the formatted prompt
        print(f"[PROCESSING] Analyzing chunk {chunk_index} of {total_chunks}")
        analysis_result = call_llm_converse(formatted_prompt, wait=(chunk_index > 1))
        
        # Check if the analysis was successful
        if analysis_result.startswith("Error:"):
            error_message = f"Error analyzing chunk {chunk_index}: {analysis_result}"
            print(f"[ERROR] {error_message}")
            return {'status': 'error', 'error': error_message}
        
        # Parse the result by service
        service_contents = parse_llm_response_by_service(analysis_result)
        
        # Save the results to S3
        result_key = f"{output_path}/results/chunk_{chunk_index}_results.json"
        s3_client.put_object(
            Bucket=bucket_name,
            Key=result_key,
            Body=json.dumps(service_contents, indent=2).encode('utf-8')
        )
        
        return {
            'status': 'success',
            'job_id': job_id,
            'chunk_index': chunk_index,
            'total_chunks': total_chunks,
            'result_key': result_key,
            'service_contents': service_contents
        }
        
    except Exception as e:
        error_message = f"Error processing chunk: {str(e)}"
        print(f"[ERROR] {error_message}")
        print(traceback.format_exc())
        
        return {'status': 'error', 'error': str(e)}
