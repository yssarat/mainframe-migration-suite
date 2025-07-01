import json
import boto3
import botocore
import botocore.config
import os
import time
import traceback
import re
from typing import Dict, Any, List

# Initialize clients
s3_client = boto3.client('s3')
dynamodb = boto3.resource('dynamodb')

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

def estimate_token_count(text: str) -> int:
    """
    Estimates the token count for a given text.
    This is a rough approximation - actual token count depends on the tokenizer used.
    
    Args:
        text (str): The text to estimate tokens for
        
    Returns:
        int: Estimated token count
    """
    # A very rough approximation: 1 token ≈ 4 characters for English text
    char_count = len(text)
    token_count = char_count // 4
    
    # Add detailed logging about token estimation
    print(f"[TOKEN ESTIMATION] Character count: {char_count:,}")
    print(f"[TOKEN ESTIMATION] Estimated token count: {token_count:,}")
    print(f"[TOKEN ESTIMATION] Estimation ratio: 1 token per 4 characters")
    
    return token_count

def calculate_adaptive_timeout(text_length: int) -> int:
    """Calculate timeout based on text length."""
    base_timeout = 60
    additional_timeout = (text_length // 10000) * 30
    max_timeout = 900  # 15 minutes
    
    timeout = min(base_timeout + additional_timeout, max_timeout)
    print(f"[TIMEOUT] Calculated timeout: {timeout}s for text length: {text_length:,}")
    
    return timeout

def create_bedrock_client():
    """Create a Bedrock client with retry configuration."""
    config = botocore.config.Config(
        retries={
            'max_attempts': 10,
            'mode': 'adaptive'
        },
        read_timeout=900,
        connect_timeout=60
    )
    
    return boto3.client('bedrock-runtime', config=config)

def call_llm_converse(prompt: str, wait: bool = True, timeout_seconds: int = 300) -> str:
    """Call Bedrock LLM with conversation API and proper throttling."""
    global time_last
    
    if wait and time_last > 0:
        elapsed = time.time() - time_last
        if elapsed < 2:
            sleep_time = 2 - elapsed
            print(f"[THROTTLING] Sleeping for {sleep_time:.2f} seconds")
            time.sleep(sleep_time)
    
    try:
        client = create_bedrock_client()
        
        # Get model ID from environment or use default
        model_id = os.environ.get('BEDROCK_MODEL_ID', 'us.anthropic.claude-3-7-sonnet-20250219-v1:0')
        print(f"[BEDROCK] Using model: {model_id}")
        
        # Prepare the conversation
        messages = [
            {
                "role": "user",
                "content": [{"text": prompt}]
            }
        ]
        
        # Call the converse API
        response = client.converse(
            modelId=model_id,
            messages=messages,
            inferenceConfig={
                "maxTokens": 200000,
                "temperature": 0.1,
                "topP": 0.9
            }
        )
        
        time_last = time.time()
        
        # Extract the response text
        if 'output' in response and 'message' in response['output']:
            content = response['output']['message']['content']
            if content and len(content) > 0 and 'text' in content[0]:
                result = content[0]['text']
                print(f"[BEDROCK] Successfully received response ({len(result)} characters)")
                return result
        
        return "Error: No valid response from Bedrock"
        
    except Exception as e:
        error_msg = f"Error calling Bedrock: {str(e)}"
        print(f"[BEDROCK ERROR] {error_msg}")
        print(f"[BEDROCK ERROR] Traceback:\n{traceback.format_exc()}")
        return f"Error: {error_msg}"

def parse_llm_response_by_service(response: str) -> Dict[str, str]:
    """Parse the LLM response and organize by service type."""
    print("[PARSING] Organizing response by service type")
    
    service_contents = {}
    
    # Define service patterns to look for
    service_patterns = {
        'LAMBDA': r'(?:### LAMBDA|## AWS Lambda|# Lambda)',
        'API_GATEWAY': r'(?:### API GATEWAY|## API Gateway|# API Gateway)',
        'DYNAMODB': r'(?:### DYNAMODB|## DynamoDB|# DynamoDB)',
        'S3': r'(?:### S3|## S3|# S3)',
        'IAM_ROLES': r'(?:### IAM|## IAM|# IAM)',
        'CLOUDFORMATION': r'(?:### CLOUDFORMATION|## CloudFormation|# CloudFormation)',
        'ECS': r'(?:### ECS|## ECS|# ECS)',
        'RDS': r'(?:### RDS|## RDS|# RDS)',
        'SQS': r'(?:### SQS|## SQS|# SQS)',
        'SNS': r'(?:### SNS|## SNS|# SNS)',
        'STEP_FUNCTIONS': r'(?:### STEP FUNCTIONS|## Step Functions|# Step Functions)',
        'README': r'(?:### README|## README|# README)'
    }
    
    # Split response into sections
    lines = response.split('\n')
    current_service = None
    current_content = []
    
    for line in lines:
        # Check if this line starts a new service section
        found_service = None
        for service, pattern in service_patterns.items():
            if re.search(pattern, line, re.IGNORECASE):
                found_service = service
                break
        
        if found_service:
            # Save previous service content if any
            if current_service and current_content:
                service_contents[current_service] = '\n'.join(current_content).strip()
            
            # Start new service
            current_service = found_service
            current_content = [line]
            print(f"[PARSING] Found section: {current_service}")
        elif current_service:
            # Add to current service content
            current_content.append(line)
    
    # Don't forget the last service
    if current_service and current_content:
        service_contents[current_service] = '\n'.join(current_content).strip()
    
    # If no services were found, put everything in a general section
    if not service_contents:
        service_contents['GENERAL'] = response
        print("[PARSING] No specific services found, using general section")
    
    print(f"[PARSING] Found {len(service_contents)} service sections: {list(service_contents.keys())}")
    return service_contents

def create_chunks(text: str, max_chunk_size: int = 100000) -> List[str]:
    """
    Split text into chunks for processing.
    
    Args:
        text (str): The text to split
        max_chunk_size (int): Maximum size per chunk in characters
        
    Returns:
        List[str]: List of text chunks
    """
    print(f"[CHUNKING] Creating chunks from text of {len(text):,} characters")
    
    if len(text) <= max_chunk_size:
        print("[CHUNKING] Text fits in single chunk")
        return [text]
    
    chunks = []
    current_pos = 0
    
    while current_pos < len(text):
        # Calculate chunk end position
        chunk_end = min(current_pos + max_chunk_size, len(text))
        
        # If not at the end, try to break at a natural boundary
        if chunk_end < len(text):
            # Look for paragraph breaks, sentence endings, or word boundaries
            for boundary in ['\n\n', '. ', '\n', ' ']:
                last_boundary = text.rfind(boundary, current_pos, chunk_end)
                if last_boundary > current_pos:
                    chunk_end = last_boundary + len(boundary)
                    break
        
        # Extract the chunk
        chunk = text[current_pos:chunk_end].strip()
        if chunk:
            chunks.append(chunk)
            print(f"[CHUNKING] Created chunk {len(chunks)} ({len(chunk):,} characters)")
        
        current_pos = chunk_end
    
    print(f"[CHUNKING] Created {len(chunks)} total chunks")
    return chunks

def process_chunks(chunks: List[str]) -> Dict[str, str]:
    """
    Process multiple chunks and aggregate their results.
    
    Args:
        chunks (list): List of text chunks to process
        
    Returns:
        dict: Aggregated results by service type
    """
    print(f"[CHUNKING] Processing {len(chunks)} chunks")
    
    # Process each chunk
    chunk_results = []
    for i, chunk in enumerate(chunks):
        print(f"[CHUNKING] Processing chunk {i+1} of {len(chunks)}")
        
        # Process this chunk with Bedrock
        result = call_llm_converse(chunk, wait=(i > 0))  # Wait except for first chunk
        
        # Check if the analysis was successful
        if result.startswith("Error:"):
            print(f"[CHUNKING] Error processing chunk {i+1}: {result}")
            chunk_results.append({
                'status': 'error',
                'error': result
            })
        else:
            # Parse the result by service
            service_contents = parse_llm_response_by_service(result)
            chunk_results.append({
                'status': 'success',
                'service_contents': service_contents
            })
    
    # Aggregate the results
    return aggregate_chunk_results(chunk_results)

def aggregate_chunk_results(chunk_results: List[Dict]) -> Dict[str, str]:
    """
    Combines the results from multiple chunk analyses into a cohesive output.
    
    Args:
        chunk_results (list): List of analysis results from different chunks
        
    Returns:
        dict: Aggregated analysis by service type
    """
    print(f"[CHUNKING] Aggregating results from {len(chunk_results)} chunks")
    
    # Initialize the aggregated results
    aggregated = {}
    
    # Process each chunk result
    for i, result in enumerate(chunk_results):
        # Skip failed analyses
        if result.get('status') == 'error':
            print(f"[CHUNKING] Skipping failed chunk {i+1}")
            continue
            
        # Get the service contents from this chunk
        service_contents = result.get('service_contents', {})
        
        # Merge into the aggregated results
        for service_type, content in service_contents.items():
            if service_type not in aggregated:
                aggregated[service_type] = content
                print(f"[CHUNKING] Added new service type: {service_type}")
            else:
                # Append new content, avoiding duplication
                aggregated[service_type] += f"\n\n### Additional Analysis from Chunk {i+1}\n\n{content}"
                print(f"[CHUNKING] Appended content to existing service type: {service_type}")
    
    return aggregated

def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Lambda function handler that analyzes text using Bedrock with chunking support."""
    print("=== ANALYSIS LAMBDA HANDLER STARTED ===")
    
    try:
        # Extract parameters from the event
        job_id = event.get('job_id')
        bucket_name = event.get('bucket_name')
        full_prompt_key = event.get('full_prompt_key')
        output_path = event.get('output_path', f"mainframe-analysis/{job_id}")
        
        print(f"[JOB] ID: {job_id}, Bucket: {bucket_name}, Path: {output_path}")
        
        # Validate required parameters
        if not all([job_id, bucket_name, full_prompt_key]):
            error_message = "Missing required parameters"
            update_job_status(job_id, 'ERROR', error_message)
            return {'status': 'error', 'error': error_message}
        
        # Get the full prompt from S3
        response = s3_client.get_object(Bucket=bucket_name, Key=full_prompt_key)
        full_prompt = response['Body'].read().decode('utf-8')
        
        # Log prompt details
        prompt_length = len(full_prompt)
        estimated_tokens = estimate_token_count(full_prompt)
        
        # Update job status
        update_job_status(job_id, 'ANALYZING', "Starting analysis")
        
        # Determine if we need chunking
        use_chunking = estimated_tokens > 150000
        
        if use_chunking:
            print(f"[CHUNKING] Input size ({estimated_tokens:,} tokens) exceeds limit. Using chunking.")
            update_job_status(job_id, 'CHUNKING', f"Breaking content into chunks ({estimated_tokens:,} tokens)")
            
            # Create chunks
            chunks = create_chunks(full_prompt)
            
            if not chunks:
                error_message = "Failed to create chunks for processing"
                update_job_status(job_id, 'ERROR', error_message)
                return {'status': 'error', 'error': error_message}
            
            # Process chunks
            update_job_status(job_id, 'PROCESSING_CHUNKS', f"Processing {len(chunks)} chunks")
            service_contents = process_chunks(chunks)
            
            if not service_contents:
                error_message = "Failed to get results from any chunks"
                update_job_status(job_id, 'ERROR', error_message)
                return {'status': 'error', 'error': error_message}
                
            analysis_result = "Chunked processing completed successfully"
        else:
            # Standard processing for smaller inputs
            timeout_seconds = calculate_adaptive_timeout(prompt_length)
            
            print(f"[BEDROCK] Analyzing documentation with {timeout_seconds}s timeout")
            analysis_result = call_llm_converse(full_prompt, wait=True, timeout_seconds=timeout_seconds)
            
            if analysis_result.startswith("Error:"):
                update_job_status(job_id, 'ERROR', analysis_result)
                return {'status': 'error', 'error': analysis_result}
            
            service_contents = parse_llm_response_by_service(analysis_result)
        
        # Save raw result for non-chunked processing
        if not use_chunking:
            raw_result_key = f"{output_path}/raw_analysis_result.txt"
            s3_client.put_object(
                Bucket=bucket_name,
                Key=raw_result_key,
                Body=analysis_result.encode('utf-8')
            )
        
        # Create aws_artifacts subfolder
        aws_artifacts_path = f"{output_path}/aws_artifacts"
        
        # Save each service content to a separate file
        uploaded_files = []
        
        for service_type, content in service_contents.items():
            if not content.strip():
                continue
                
            # Determine file extension
            if service_type == "CLOUDFORMATION":
                file_extension = ".yaml"
            elif service_type in ["IAM_ROLES", "DYNAMODB"]:
                file_extension = ".json"
            elif service_type == "README":
                file_extension = ".md"
            else:
                file_extension = ".txt"
                
            service_filename = f"{service_type.lower()}{file_extension}"
            service_key = f"{aws_artifacts_path}/{service_filename}"
            
            s3_client.put_object(
                Bucket=bucket_name,
                Key=service_key,
                Body=content.encode('utf-8')
            )
            
            uploaded_files.append({
                "service_type": service_type,
                "s3_location": f"s3://{bucket_name}/{service_key}",
                "size_bytes": len(content.encode('utf-8'))
            })
        
        # Update job status
        status_message = f"Successfully analyzed and created {len(uploaded_files)} files"
        if use_chunking:
            status_message = f"Successfully analyzed using chunking and created {len(uploaded_files)} files"
            
        update_job_status(job_id, 'COMPLETED', status_message)
        
        return {
            'status': 'success',
            'job_id': job_id,
            'bucket_name': bucket_name,
            'output_path': output_path,
            'files': uploaded_files,
            'chunked_processing': use_chunking
        }
        
    except Exception as e:
        error_message = f"Error during analysis: {str(e)}"
        print(f"[ERROR] {error_message}")
        print(f"[ERROR] Traceback:\n{traceback.format_exc()}")
        
        if 'job_id' in event:
            update_job_status(event['job_id'], 'ERROR', error_message)
        
        return {'status': 'error', 'error': str(e)}
