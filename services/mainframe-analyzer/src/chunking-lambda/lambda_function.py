import json
import boto3
import os
import re
import time
import logging
from typing import Dict, Any, Tuple, List

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize clients
s3_client = boto3.client('s3')
dynamodb = boto3.resource('dynamodb')

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
    """Estimates the token count for a given text."""
    char_count = len(text)
    token_count = char_count // 4
    
    print(f"[TOKEN ESTIMATION] Character count: {char_count:,}")
    print(f"[TOKEN ESTIMATION] Estimated token count: {token_count:,}")
    
    return token_count

def create_chunks(full_text: str, max_tokens_per_chunk: int = None) -> List[str]:
    """Divides the full text into processable chunks with strict size limits."""
    # Get max tokens per chunk from environment variable or use default
    if max_tokens_per_chunk is None:
        max_tokens_per_chunk = int(os.environ.get('MAX_TOKENS_PER_CHUNK', 15000))
    
    print(f"[CHUNKING] Creating chunks with max {max_tokens_per_chunk} tokens per chunk")
    chunks = []
    
    # Find the documentation section
    split_point = full_text.find("DOCUMENTATION:")
    if split_point != -1:
        prompt_part = full_text[:split_point + len("DOCUMENTATION:")]
        documentation = full_text[split_point + len("DOCUMENTATION:"):]
    else:
        prompt_part = "You are an expert mainframe documentation analyzer. Please analyze the following documentation:\n\nDOCUMENTATION:"
        documentation = full_text
    
    # Calculate tokens for the prompt template
    prompt_tokens = estimate_token_count(prompt_part)
    print(f"[CHUNKING] Prompt template uses {prompt_tokens} tokens")
    
    # Adjust max tokens per chunk to account for the prompt template
    available_tokens = max_tokens_per_chunk - prompt_tokens - 500  # Add buffer
    
    # Split by document boundaries
    documents = re.split(r'(--- FILE: .*? ---\n\n)', documentation)
    
    current_chunk = ""
    current_chunk_tokens = 0
    
    # Process each document or separator
    for doc in documents:
        if not doc.strip():
            continue
            
        doc_tokens = estimate_token_count(doc)
        
        # If this document is too large for a single chunk, split it further
        if doc_tokens > available_tokens:
            print(f"[CHUNKING] Large document found: {doc_tokens} tokens, splitting further")
            
            # If we have content in the current chunk, finalize it first
            if current_chunk:
                chunks.append(prompt_part + "\n\n" + current_chunk)
                current_chunk = ""
                current_chunk_tokens = 0
            
            # Split the large document into paragraphs
            paragraphs = re.split(r'\n\n+', doc)
            
            for para in paragraphs:
                para_tokens = estimate_token_count(para)
                
                # If even a single paragraph is too large, split it into sentences
                if para_tokens > available_tokens:
                    sentences = re.split(r'(?<=[.!?])\s+', para)
                    
                    for sentence in sentences:
                        sentence_tokens = estimate_token_count(sentence)
                        
                        # If adding this sentence would exceed the chunk size and we already have content
                        if current_chunk_tokens + sentence_tokens > available_tokens and current_chunk:
                            # Save the current chunk and start a new one
                            chunks.append(prompt_part + "\n\n" + current_chunk)
                            current_chunk = sentence
                            current_chunk_tokens = sentence_tokens
                        else:
                            # Add to the current chunk
                            if current_chunk:
                                current_chunk += " " + sentence
                            else:
                                current_chunk = sentence
                            current_chunk_tokens += sentence_tokens
                else:
                    # If adding this paragraph would exceed the chunk size and we already have content
                    if current_chunk_tokens + para_tokens > available_tokens and current_chunk:
                        # Save the current chunk and start a new one
                        chunks.append(prompt_part + "\n\n" + current_chunk)
                        current_chunk = para
                        current_chunk_tokens = para_tokens
                    else:
                        # Add to the current chunk
                        if current_chunk:
                            current_chunk += "\n\n" + para
                        else:
                            current_chunk = para
                        current_chunk_tokens += para_tokens
        else:
            # If adding this document would exceed the chunk size and we already have content
            if current_chunk_tokens + doc_tokens > available_tokens and current_chunk:
                # Save the current chunk and start a new one
                chunks.append(prompt_part + "\n\n" + current_chunk)
                current_chunk = doc
                current_chunk_tokens = doc_tokens
            else:
                # Add to the current chunk
                if current_chunk:
                    current_chunk += doc
                else:
                    current_chunk = doc
                current_chunk_tokens += doc_tokens
    
    # Add the final chunk if it has content
    if current_chunk:
        chunks.append(prompt_part + "\n\n" + current_chunk)
    
    print(f"[CHUNKING] Created {len(chunks)} chunks")
    for i, chunk in enumerate(chunks):
        chunk_tokens = estimate_token_count(chunk)
        print(f"[CHUNKING] Chunk {i+1}: {chunk_tokens} tokens")
    
    return chunks

def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Evaluates input size and creates chunks if necessary
    """
    print("=== CHUNKING LAMBDA HANDLER STARTED ===")
    
    try:
        # Extract parameters from the event
        job_id = event.get('job_id')
        bucket_name = event.get('bucket_name')
        full_prompt_key = event.get('full_prompt_key')
        output_path = event.get('output_path')
        
        print(f"[JOB] ID: {job_id}, Bucket: {bucket_name}, Path: {output_path}")
        
        # Validate required parameters
        if not all([job_id, bucket_name, full_prompt_key]):
            error_message = "Missing required parameters"
            update_job_status(job_id, 'ERROR', error_message)
            return {'status': 'error', 'error': error_message}
        
        # Get the full prompt from S3
        response = s3_client.get_object(Bucket=bucket_name, Key=full_prompt_key)
        full_prompt = response['Body'].read().decode('utf-8')
        
        # Estimate tokens
        estimated_tokens = estimate_token_count(full_prompt)
        
        # Get chunking threshold from environment variable or use default
        chunking_threshold = int(os.environ.get('CHUNKING_THRESHOLD', 15000))
        
        # Check if chunking is needed
        requires_chunking = estimated_tokens > chunking_threshold
        
        if requires_chunking:
            # Update job status
            update_job_status(job_id, 'CHUNKING', f"Breaking content into chunks ({estimated_tokens:,} tokens)")
            
            # Get max tokens per chunk from environment variable
            max_tokens_per_chunk = int(os.environ.get('MAX_TOKENS_PER_CHUNK', 15000))
            
            # Create chunks
            chunks = create_chunks(full_prompt, max_tokens_per_chunk)
            chunk_metadata = []
            
            # Save chunks to S3
            for i, chunk in enumerate(chunks):
                chunk_key = f"{output_path}/chunks/chunk_{i+1}_of_{len(chunks)}.txt"
                s3_client.put_object(
                    Bucket=bucket_name,
                    Key=chunk_key,
                    Body=chunk.encode('utf-8')
                )
                
                chunk_metadata.append({
                    "index": i+1,
                    "total": len(chunks),
                    "chunk_key": chunk_key,
                    "estimated_tokens": estimate_token_count(chunk)
                })
            
            return {
                "job_id": job_id,
                "bucket_name": bucket_name,
                "output_path": output_path,
                "requires_chunking": True,
                "chunks": chunk_metadata,
                "total_chunks": len(chunks)
            }
        else:
            # No chunking needed
            return {
                "job_id": job_id,
                "bucket_name": bucket_name,
                "full_prompt_key": full_prompt_key,
                "output_path": output_path,
                "requires_chunking": False
            }
            
    except Exception as e:
        error_message = f"Error during chunking: {str(e)}"
        print(f"[ERROR] {error_message}")
        
        if 'job_id' in event:
            update_job_status(event['job_id'], 'ERROR', error_message)
        
        return {'status': 'error', 'error': str(e)}
