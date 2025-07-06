import json
import boto3
import botocore
import botocore.config
import os
import time
import traceback
import re
from typing import Dict, Any, Generator, Optional, List
from dataclasses import dataclass

# Initialize clients
s3_client = boto3.client('s3')
dynamodb = boto3.resource('dynamodb')
ssm_client = boto3.client('ssm')

# Initialize global variable for throttling
time_last = 0

@dataclass
class ChunkStreamingFile:
    filename: str
    content: str
    file_type: str
    section: str
    chunk_index: int
    is_complete: bool = False

class ChunkStreamingExtractor:
    """
    Streaming extractor for chunk processing with individual file extraction
    """
    
    def __init__(self, bucket_name: str, output_prefix: str, chunk_index: int):
        self.s3_client = boto3.client('s3')
        self.bedrock_client = boto3.client('bedrock-runtime')
        self.bucket_name = bucket_name
        self.output_prefix = output_prefix
        self.chunk_index = chunk_index
        
        # Streaming state
        self.buffer = ""
        self.current_section = None
        self.current_file = None
        self.current_content = []
        self.files_created = []
        
        # Enhanced section and file patterns for mainframe modernization
        self.section_patterns = {
            'LAMBDA_FUNCTIONS': r'^##\s*LAMBDA[_\s]*FUNCTIONS?',
            'IAM_ROLES': r'^##\s*IAM[_\s]*ROLES?',
            'DYNAMODB': r'^##\s*DYNAMO[_\s]*DB',
            'S3': r'^##\s*S3',
            'SQS_SNS_EVENTBRIDGE': r'^##\s*(?:SQS[_\s]*SNS[_\s]*EVENTBRIDGE|MESSAGING)',
            'STEP_FUNCTIONS': r'^##\s*STEP[_\s]*FUNCTIONS?',
            'AWS_GLUE': r'^##\s*(?:AWS[_\s]*GLUE|GLUE)',
            'API_GATEWAY': r'^##\s*API[_\s]*GATEWAY',
            'ECS_FARGATE': r'^##\s*(?:ECS|FARGATE|CONTAINERS)',
            'RDS': r'^##\s*RDS',
            'CLOUDFORMATION': r'^##\s*(?:CLOUDFORMATION|CFN)',
            'OTHER_SERVICES': r'^##\s*OTHER[_\s]*SERVICES',
            'README': r'^##\s*README',
            'REASONING': r'^##\s*REASONING',
            'ARCHITECTURE': r'^##\s*ARCHITECTURE'
        }
        
        # Special documentation sections that should go to documentation folder
        self.documentation_sections = {'README', 'REASONING', 'ARCHITECTURE'}
        
        self.file_patterns = {
            'python': r'^###\s*(.+\.py)',
            'json': r'^###\s*(.+\.json)',
            'yaml': r'^###\s*(.+\.ya?ml)',
            'markdown': r'^###\s*(.+\.md)',
            'shell': r'^###\s*(.+\.sh)',
            'sql': r'^###\s*(.+\.sql)',
            'dockerfile': r'^###\s*(Dockerfile.*)',
            'terraform': r'^###\s*(.+\.tf)',
            'properties': r'^###\s*(.+\.properties)'
        }

    def stream_bedrock_response(self, prompt: str) -> Generator[str, None, None]:
        """Stream response from Bedrock for chunk processing"""
        try:
            model_id = os.environ.get('BEDROCK_MODEL_ID', 'us.anthropic.claude-3-7-sonnet-20250219-v1:0')
            
            # Enhanced system prompt for chunk processing
            system_prompt = f"""You are an expert AWS architect specializing in mainframe modernization. 

This is chunk {self.chunk_index} of a larger mainframe modernization analysis.

CRITICAL: Generate complete, production-ready AWS artifacts in this EXACT structure:

## LAMBDA_FUNCTIONS
### function_name_chunk{self.chunk_index}.py
```python
[Complete Python Lambda function with all imports, error handling, and logging]
```

## IAM_ROLES  
### role_name_chunk{self.chunk_index}.json
```json
{{
  "Version": "2012-10-17",
  "Statement": [complete IAM policy for this chunk's functionality]
}}
```

## STEP_FUNCTIONS
### workflow_name_chunk{self.chunk_index}.json
```json
{{
  "Comment": "Mainframe modernization workflow for chunk {self.chunk_index}",
  "StartAt": "...",
  [complete state machine definition]
}}
```

## README
### README_chunk{self.chunk_index}.md
```markdown
# Mainframe Modernization - Chunk {self.chunk_index}

## Overview
[Documentation specific to this chunk's functionality]

## Components
[Description of AWS services and components in this chunk]
```

## REASONING
### analysis_chunk{self.chunk_index}.md
```markdown
# Analysis and Reasoning - Chunk {self.chunk_index}

## Chunk Analysis
[Analysis specific to this chunk of the mainframe system]

## AWS Service Selection
[Reasoning for chosen AWS services for this chunk]
```

Continue this pattern for ALL AWS services relevant to this chunk. Each file must be:
- Complete and deployable
- Include proper error handling
- Follow AWS best practices
- Be production-ready
- Include chunk-specific naming to avoid conflicts

Focus on mainframe modernization patterns relevant to this chunk."""
            
            request_body = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 131000,
                "temperature": 0.1,
                "top_p": 0.9,
                "system": system_prompt,
                "messages": [{"role": "user", "content": prompt}]
            }
            
            print(f"[BEDROCK] Starting streaming response for chunk {self.chunk_index}")
            
            response = self.bedrock_client.invoke_model_with_response_stream(
                modelId=model_id,
                body=json.dumps(request_body)
            )
            
            total_chars = 0
            for event in response['body']:
                if 'chunk' in event:
                    chunk = event['chunk']
                    if 'bytes' in chunk:
                        chunk_data = json.loads(chunk['bytes'].decode())
                        if chunk_data['type'] == 'content_block_delta':
                            if 'delta' in chunk_data and 'text' in chunk_data['delta']:
                                text_chunk = chunk_data['delta']['text']
                                total_chars += len(text_chunk)
                                
                                if total_chars % 5000 == 0:
                                    print(f"[BEDROCK] Chunk {self.chunk_index}: Streamed {total_chars:,} characters, created {len(self.files_created)} files")
                                
                                yield text_chunk
                                
            print(f"[BEDROCK] Chunk {self.chunk_index}: Completed streaming {total_chars:,} total characters")
                                
        except Exception as e:
            print(f"[BEDROCK ERROR] Chunk {self.chunk_index}: {str(e)}")
            yield f"Error: {str(e)}"

    def process_streaming_chunk(self, chunk: str):
        """Process each streaming chunk and extract files in real-time"""
        self.buffer += chunk
        
        # Process complete lines
        while '\n' in self.buffer:
            line, self.buffer = self.buffer.split('\n', 1)
            self.process_line(line)

    def process_line(self, line: str):
        """Process a single line and manage sections/files"""
        line_stripped = line.strip()
        
        # Check for section headers
        new_section = self.detect_section(line_stripped)
        if new_section:
            # Save current file if we have one
            if self.current_file and self.current_content:
                self.save_current_file()
            
            self.current_section = new_section
            self.current_file = None
            self.current_content = []
            print(f"[SECTION] Chunk {self.chunk_index}: Started section: {new_section}")
            
            # Auto-create files for documentation sections if no explicit file header follows
            if new_section in self.documentation_sections:
                # Set a default filename for documentation sections with chunk identifier
                if new_section == 'README':
                    self.current_file = f'README_chunk{self.chunk_index}.md'
                elif new_section == 'REASONING':
                    self.current_file = f'analysis_chunk{self.chunk_index}.md'
                elif new_section == 'ARCHITECTURE':
                    self.current_file = f'architecture_chunk{self.chunk_index}.md'
                
                if self.current_file:
                    print(f"[FILE] Chunk {self.chunk_index}: Auto-created file: {self.current_file} for section {new_section}")
            
            return
        
        # Check for file headers
        new_file = self.detect_file(line_stripped)
        if new_file and self.current_section:
            # Save previous file if we have one
            if self.current_file and self.current_content:
                self.save_current_file()
            
            self.current_file = new_file
            self.current_content = []
            print(f"[FILE] Chunk {self.chunk_index}: Started file: {new_file} in section {self.current_section}")
            return
        
        # Add content to current file or section
        if self.current_section:
            # For documentation sections without explicit file headers, start collecting content
            if self.current_section in self.documentation_sections and not self.current_file:
                # Auto-create file if we haven't already
                if self.current_section == 'README':
                    self.current_file = f'README_chunk{self.chunk_index}.md'
                elif self.current_section == 'REASONING':
                    self.current_file = f'analysis_chunk{self.chunk_index}.md'
                elif self.current_section == 'ARCHITECTURE':
                    self.current_file = f'architecture_chunk{self.chunk_index}.md'
                
                if self.current_file:
                    print(f"[FILE] Chunk {self.chunk_index}: Auto-created file: {self.current_file} for content in section {self.current_section}")
            
            # Add content if we have a current file
            if self.current_file:
                self.current_content.append(line)
                
                # Save file when we detect it's complete
                if self.is_file_complete(line_stripped):
                    self.save_current_file()

    def detect_section(self, line: str) -> Optional[str]:
        """Detect section headers"""
        for section_name, pattern in self.section_patterns.items():
            if re.match(pattern, line, re.IGNORECASE):
                return section_name
        return None

    def detect_file(self, line: str) -> Optional[str]:
        """Detect file headers"""
        for file_type, pattern in self.file_patterns.items():
            match = re.match(pattern, line, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        return None

    def is_file_complete(self, line: str) -> bool:
        """Check if current file is complete"""
        if not self.current_content:
            return False
        
        # For documentation sections, save when we hit another section or significant content
        if self.current_section in self.documentation_sections:
            # Save when we detect a new section starting
            if self.detect_section(line):
                return True
            
            # Save documentation files when they have substantial content (more than 15 lines for chunks)
            if len(self.current_content) > 15:
                # Look for natural break points in documentation
                if line.strip() == '' and len(self.current_content) > 30:
                    return True
        
        # Check for code block endings
        if line == '```' and len(self.current_content) > 10:
            return True
        
        # Check for next file/section starting
        if (self.detect_file(line) or self.detect_section(line)) and len(self.current_content) > 5:
            return True
        
        # For large files, save periodically (smaller threshold for chunks)
        if len(self.current_content) > 300:
            return True
        
        return False

    def save_current_file(self):
        """Save the current file to S3"""
        if not self.current_file or not self.current_content:
            return
        
        # Clean and prepare content
        content = self.clean_file_content('\n'.join(self.current_content))
        
        if len(content.strip()) < 30:  # Skip tiny files
            return
        
        # Determine file path with chunk identifier
        # Map documentation sections to documentation folder
        if self.current_section in self.documentation_sections:
            section_folder = "documentation"
        else:
            section_folder = self.current_section.lower().replace('_', '-')
        
        # Add chunk identifier to filename to avoid conflicts
        filename_parts = self.current_file.rsplit('.', 1)
        if len(filename_parts) == 2:
            base_name, extension = filename_parts
            chunk_filename = f"{base_name}_chunk{self.chunk_index}.{extension}"
        else:
            chunk_filename = f"{self.current_file}_chunk{self.chunk_index}"
        
        file_path = f"{self.output_prefix}/{section_folder}/{chunk_filename}"
        
        try:
            # Save to S3
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=file_path,
                Body=content.encode('utf-8'),
                ContentType=self.get_content_type(self.current_file)
            )
            
            file_info = {
                'filename': chunk_filename,
                'original_filename': self.current_file,
                'section': self.current_section,
                'chunk_index': self.chunk_index,
                'size': len(content),
                's3_path': f"s3://{self.bucket_name}/{file_path}",
                'content_type': self.get_content_type(self.current_file)
            }
            
            self.files_created.append(file_info)
            print(f"[SAVE] Chunk {self.chunk_index}: Saved {chunk_filename} ({len(content)} chars) to {section_folder}/")
            
        except Exception as e:
            print(f"[SAVE ERROR] Chunk {self.chunk_index}: Failed to save {self.current_file}: {str(e)}")
        
        # Reset current file
        self.current_file = None
        self.current_content = []

    def clean_file_content(self, content: str) -> str:
        """Clean and format file content"""
        lines = content.split('\n')
        cleaned_lines = []
        in_code_block = False
        
        for line in lines:
            # Handle code blocks
            if line.strip().startswith('```'):
                if line.strip() == '```':
                    in_code_block = False
                    continue
                else:
                    in_code_block = True
                    continue
            
            # Skip empty lines at start
            if not cleaned_lines and not line.strip():
                continue
            
            cleaned_lines.append(line)
        
        # Remove trailing empty lines
        while cleaned_lines and not cleaned_lines[-1].strip():
            cleaned_lines.pop()
        
        return '\n'.join(cleaned_lines)

    def get_content_type(self, filename: str) -> str:
        """Get content type based on file extension"""
        if filename.endswith('.py'):
            return 'text/x-python'
        elif filename.endswith('.json'):
            return 'application/json'
        elif filename.endswith('.md'):
            return 'text/markdown'
        elif filename.endswith('.yaml') or filename.endswith('.yml'):
            return 'application/x-yaml'
        elif filename.endswith('.sh'):
            return 'application/x-sh'
        elif filename.endswith('.sql'):
            return 'application/sql'
        elif filename.endswith('.tf'):
            return 'text/x-terraform'
        else:
            return 'text/plain'

    def finalize_processing(self):
        """Finalize processing and save any remaining content"""
        # Save any remaining file
        if self.current_file and self.current_content:
            self.save_current_file()
        
        # Process any remaining buffer
        if self.buffer.strip():
            self.process_line(self.buffer)
            if self.current_file and self.current_content:
                self.save_current_file()

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

def process_chunk_with_streaming(chunk_content: str, bucket_name: str, output_path: str, chunk_index: int) -> Dict[str, Any]:
    """
    Process a chunk using streaming file extraction
    """
    print(f"[STREAMING] Starting streaming file extraction for chunk {chunk_index}")
    
    # Create the streaming extractor for this chunk
    extractor = ChunkStreamingExtractor(bucket_name, f"{output_path}/chunk_{chunk_index}_files", chunk_index)
    
    try:
        # Stream the response and process in real-time
        for chunk in extractor.stream_bedrock_response(chunk_content):
            if chunk.startswith("Error:"):
                return {'status': 'error', 'error': chunk}
            
            extractor.process_streaming_chunk(chunk)
        
        # Finalize processing
        extractor.finalize_processing()
        
        # Group files by section
        files_by_section = {}
        for file_info in extractor.files_created:
            section = file_info['section']
            if section not in files_by_section:
                files_by_section[section] = []
            files_by_section[section].append(file_info)
        
        return {
            'status': 'success',
            'chunk_index': chunk_index,
            'total_files_created': len(extractor.files_created),
            'files_by_section': files_by_section,
            'all_files': extractor.files_created
        }
        
    except Exception as e:
        return {'status': 'error', 'error': str(e)}

def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Enhanced chunk processor with streaming file extraction capabilities.
    """
    print("=== ENHANCED CHUNK PROCESSOR LAMBDA HANDLER STARTED ===")
    
    try:
        # Extract parameters from the event
        job_id = event.get('job_id')
        bucket_name = event.get('bucket_name')
        chunk_key = event.get('chunk_key')
        chunk_index = event.get('chunk_index')
        total_chunks = event.get('total_chunks')
        output_path = event.get('output_path')
        use_streaming = event.get('use_streaming', True)  # Default to streaming
        
        print(f"[JOB] ID: {job_id}, Chunk: {chunk_index}/{total_chunks}")
        print(f"[CONFIG] Streaming extraction enabled: {use_streaming}")
        
        # Validate required parameters
        if not all([job_id, bucket_name, chunk_key, chunk_index, total_chunks]):
            error_message = "Missing required parameters"
            return {'status': 'error', 'error': error_message}
        
        # Update job status
        update_job_status(job_id, 'PROCESSING', f"Processing chunk {chunk_index} of {total_chunks} with streaming extraction")
        
        # Get the chunk content from S3
        response = s3_client.get_object(Bucket=bucket_name, Key=chunk_key)
        chunk_content = response['Body'].read().decode('utf-8')
        
        if use_streaming:
            # Use streaming file extraction for this chunk
            print(f"[PROCESSING] Using streaming file extraction for chunk {chunk_index}")
            
            streaming_result = process_chunk_with_streaming(chunk_content, bucket_name, output_path, chunk_index)
            
            if streaming_result['status'] == 'error':
                error_message = f"Error in streaming analysis for chunk {chunk_index}: {streaming_result['error']}"
                print(f"[ERROR] {error_message}")
                return {'status': 'error', 'error': error_message}
            
            # Save chunk results summary
            result_key = f"{output_path}/results/chunk_{chunk_index}_streaming_results.json"
            s3_client.put_object(
                Bucket=bucket_name,
                Key=result_key,
                Body=json.dumps(streaming_result, indent=2).encode('utf-8')
            )
            
            return {
                'status': 'success',
                'job_id': job_id,
                'chunk_index': chunk_index,
                'total_chunks': total_chunks,
                'result_key': result_key,
                'streaming_extraction': True,
                'total_files_created': streaming_result['total_files_created'],
                'files_by_section': streaming_result['files_by_section'],
                'all_files': streaming_result['all_files']
            }
        
        else:
            # Fall back to traditional processing
            print(f"[PROCESSING] Using traditional processing for chunk {chunk_index}")
            
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
                'streaming_extraction': False,
                'service_contents': service_contents
            }
        
    except Exception as e:
        error_message = f"Error processing chunk: {str(e)}"
        print(f"[ERROR] {error_message}")
        print(traceback.format_exc())
        
        return {'status': 'error', 'error': str(e)}
