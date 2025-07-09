import json
import boto3
import botocore
import botocore.config
import os
import time
import traceback
import re
import sys
from typing import Dict, Any, List, Generator, Optional
from dataclasses import dataclass

# Add the shared directory to the path
sys.path.append('/opt/python')  # Lambda layer path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'shared'))

# Import the prompt manager
from shared.prompt_manager import get_prompt_manager

# Initialize clients
s3_client = boto3.client('s3')
dynamodb = boto3.resource('dynamodb')

# Initialize global variable for throttling
time_last = 0

# Initialize prompt manager
prompt_manager = get_prompt_manager()

@dataclass
class StreamingFile:
    filename: str
    content: str
    file_type: str
    section: str
    is_complete: bool = False

class StreamingFileExtractor:
    """
    Enhanced streaming analyzer that extracts individual files in real-time
    """
    
    def __init__(self, bucket_name: str, output_prefix: str):
        self.s3_client = boto3.client('s3')
        self.bedrock_client = boto3.client('bedrock-runtime')
        self.bucket_name = bucket_name
        self.output_prefix = output_prefix
        
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
            'csharp': r'^###\s*(.+\.cs)',  # .NET/C# files
            'java': r'^###\s*(.+\.java)',  # Java files
            'go': r'^###\s*(.+\.go)',      # Go files
            'javascript': r'^###\s*(.+\.js)', # JavaScript files
            'json': r'^###\s*(.+\.json)',
            'yaml': r'^###\s*(.+\.ya?ml)',
            'markdown': r'^###\s*(.+\.md)',
            'shell': r'^###\s*(.+\.sh)',
            'sql': r'^###\s*(.+\.sql)',
            'dockerfile': r'^###\s*(Dockerfile.*)',
            'terraform': r'^###\s*(.+\.tf)',
            'properties': r'^###\s*(.+\.properties)',
            'csproj': r'^###\s*(.+\.csproj)',  # .NET project files
            'xml': r'^###\s*(.+\.xml)'         # XML files
        }

    def stream_bedrock_response(self, prompt: str) -> Generator[str, None, None]:
        """Stream response from Bedrock with enhanced system prompt for mainframe modernization"""
        try:
            model_id = os.environ.get('BEDROCK_MODEL_ID', 'us.anthropic.claude-3-7-sonnet-20250219-v1:0')
            
            # Get system prompt from S3 with language support
            target_language = os.environ.get('TARGET_LANGUAGE', 'python')
            print(f"[LANGUAGE] Target language: {target_language}")
            base_prompt = prompt_manager.get_prompt('analysis-agent', target_language)
            
            if not base_prompt:
                print("Could not retrieve system prompt from S3, using minimal fallback")
                base_prompt = "You are an expert AWS architect specializing in mainframe modernization."
            else:
                print(f"[PROMPT] Retrieved {len(base_prompt)} character prompt for {target_language}")
            
            # Enhanced system prompt for streaming file extraction
            # Get file extension and language-specific instructions based on target language
            if target_language == 'dotnet':
                file_extension = '.cs'
                language_instruction = '.NET/C# code with proper namespaces, using statements, and error handling'
            elif target_language == 'java':
                file_extension = '.java'
                language_instruction = 'Java code with proper package declarations, imports, and exception handling'
            elif target_language == 'go':
                file_extension = '.go'
                language_instruction = 'Go code with proper package declarations, imports, and error handling'
            elif target_language == 'javascript':
                file_extension = '.js'
                language_instruction = 'JavaScript/Node.js code with proper module exports and error handling'
            else:  # python (default)
                file_extension = '.py'
                language_instruction = 'Python code with proper imports and error handling'
            
            print(f"[LANGUAGE] Using file extension: {file_extension} for {target_language}")
            
            enhanced_system_prompt = f"""{base_prompt}

CRITICAL INSTRUCTIONS FOR STRUCTURED OUTPUT:

You MUST organize your response using these exact section headers and follow the language-specific format:

## LAMBDA_FUNCTIONS
### function_name{file_extension}
[{language_instruction}]

CRITICAL FILENAME REQUIREMENTS:
- IGNORE any file extensions from the input documentation (.py, .cs, .js, etc.)
- ALWAYS use {file_extension} extension for ALL Lambda function files
- Generate meaningful function names but ALWAYS end with {file_extension}
- Example: AccountProcessor{file_extension}, ErrorHandler{file_extension}, FileValidator{file_extension}
- DO NOT copy .py, .cs, or other extensions from input - ONLY use {file_extension}
- Target language is {target_language} - generate {target_language} code with {file_extension} files

## IAM_ROLES  
### role_name.json
[IAM role definition in JSON]

## DYNAMODB
### table_name.json
[DynamoDB table definition]

## S3
### bucket_config.yaml
[S3 bucket configuration]

## STEP_FUNCTIONS
### workflow_name.json
[Step Functions definition]

## API_GATEWAY
### api_config.yaml
[API Gateway configuration]

## CLOUDFORMATION
### template_name.yaml
[CloudFormation template]

## README
### README.md
[Project documentation and setup instructions]

## ARCHITECTURE_DIAGRAM
### architecture.md
[Architecture overview and design decisions]

## REASONING
### analysis.md
[Technical reasoning and modernization rationale]

ABSOLUTE REQUIREMENTS: 
- Each section MUST start with ## followed by the section name
- Each file MUST start with ### followed by the filename
- MANDATORY: Use ONLY {file_extension} extension for ALL Lambda function files
- Target language: {target_language}
- Provide complete, production-ready {target_language} code for each file
- Follow {target_language} best practices and conventions
- Include proper error handling and best practices
- Focus on AWS serverless and managed services for mainframe modernization
- IGNORE input file extensions - generate appropriate {target_language} filenames with {file_extension}
"""

            # Prepare the request
            request_body = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 131000,  # Safe limit under Claude's 131,072 token maximum
                "system": enhanced_system_prompt,
                "messages": [
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "temperature": 0.1,
                "top_p": 0.9
            }
            
            print(f"[BEDROCK] Starting streaming request to {model_id}")
            
            # Make streaming request to Bedrock
            response = self.bedrock_client.invoke_model_with_response_stream(
                modelId=model_id,
                body=json.dumps(request_body)
            )
            
            # Process streaming response
            full_response = ""  # Track the complete response for debugging
            chunk_count = 0
            
            for event in response['body']:
                if 'chunk' in event:
                    chunk = event['chunk']
                    if 'bytes' in chunk:
                        chunk_data = json.loads(chunk['bytes'].decode())
                        if chunk_data['type'] == 'content_block_delta':
                            if 'delta' in chunk_data and 'text' in chunk_data['delta']:
                                text_chunk = chunk_data['delta']['text']
                                full_response += text_chunk
                                chunk_count += 1
                                
                                # Log every 50 chunks to avoid too much noise
                                if chunk_count % 50 == 0:
                                    print(f"[BEDROCK] Processed {chunk_count} chunks, total length: {len(full_response)}")
                                
                                yield text_chunk
            
            # Log the complete response for debugging (truncated if too long)
            print(f"[BEDROCK] Complete response received: {len(full_response)} characters, {chunk_count} chunks")
            if len(full_response) > 2000:
                print(f"[BEDROCK] Response preview (first 1000 chars): {full_response[:1000]}")
                print(f"[BEDROCK] Response preview (last 1000 chars): {full_response[-1000:]}")
            else:
                print(f"[BEDROCK] Full response: {full_response}")
                                
        except Exception as e:
            error_msg = f"Bedrock streaming error: {str(e)}"
            print(f"[ERROR] {error_msg}")
            yield f"Error: {error_msg}"

    def process_line(self, line: str):
        """Process a single line for section and file detection"""
        line_stripped = line.strip()
        
        # Skip empty lines
        if not line_stripped:
            self.current_content.append(line)
            return
        
        # Check for new section
        new_section = self.detect_section(line_stripped)
        if new_section:
            # Save current file if we have one
            if self.current_file and self.current_content:
                self.save_current_file()
            
            self.current_section = new_section
            self.current_file = None
            self.current_content = []
            
            print(f"[SECTION] Detected: {new_section}")
            
            # Auto-create files for documentation sections if no explicit file header follows
            if new_section in self.documentation_sections:
                # Set a default filename for documentation sections
                if new_section == 'README':
                    self.current_file = 'README.md'
                elif new_section == 'REASONING':
                    self.current_file = 'REASONING.md'
                elif new_section == 'ARCHITECTURE':
                    self.current_file = 'ARCHITECTURE.md'
                self.current_content = []
            return
        
        # Check for new file
        new_file = self.detect_file(line_stripped)
        if new_file and self.current_section:
            # Save previous file if we have one
            if self.current_file and self.current_content:
                self.save_current_file()
            
            self.current_file = new_file
            self.current_content = []
            print(f"[FILE] Detected: {new_file} in section {self.current_section}")
            return
        
        # Add content to current file
        if self.current_section:
            # Skip the section header line itself
            if not any(re.match(pattern, line_stripped, re.IGNORECASE) for pattern in self.section_patterns.values()):
                # Skip the file header line itself
                if not any(re.match(pattern, line_stripped) for pattern in self.file_patterns.values()):
                    self.current_content.append(line)
                    
                    # For documentation sections, save file when we detect it's complete
                    if self.current_section in self.documentation_sections:
                        # Save file when we detect it's complete
                        if self.is_file_complete(line_stripped):
                            self.save_current_file()

    def detect_section(self, line: str) -> Optional[str]:
        """Detect section headers"""
        for section, pattern in self.section_patterns.items():
            if re.match(pattern, line, re.IGNORECASE):
                return section
        return None

    def detect_file(self, line: str) -> Optional[str]:
        """Detect file headers"""
        for file_type, pattern in self.file_patterns.items():
            match = re.match(pattern, line)
            if match:
                filename = match.group(1)
                print(f"[FILE DETECTION] Detected {file_type} file: {filename} from line: {line[:100]}")
                return filename
        
        # Log lines that look like file headers but don't match our patterns
        if line.strip().startswith('###'):
            print(f"[FILE DETECTION] Unmatched file header: {line[:100]}")
        
        return None

    def is_file_complete(self, line: str) -> bool:
        """Check if current file is complete (simple heuristic)"""
        # For documentation sections, consider file complete when we see another section or file
        if self.current_section in self.documentation_sections:
            return (self.detect_section(line) is not None or 
                   self.detect_file(line) is not None)
        
        # For code files, use more sophisticated detection
        completion_indicators = [
            r'^\s*$',  # Empty line
            r'^\s*#.*END',  # Comment with END
            r'^\s*```\s*$',  # End of code block
        ]
        
        for indicator in completion_indicators:
            if re.match(indicator, line, re.IGNORECASE):
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
        
        # Determine file path
        # Map documentation sections to documentation folder
        if self.current_section in self.documentation_sections:
            section_folder = "documentation"
        else:
            section_folder = self.current_section.lower().replace('_', '-')
        file_path = f"{self.output_prefix}/{section_folder}/{self.current_file}"
        
        try:
            # Save to S3
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=file_path,
                Body=content.encode('utf-8'),
                ContentType=self.get_content_type(self.current_file)
            )
            
            file_info = {
                'filename': self.current_file,
                'section': self.current_section,
                'size': len(content),
                's3_path': f"s3://{self.bucket_name}/{file_path}",
                'content_type': self.get_content_type(self.current_file)
            }
            
            self.files_created.append(file_info)
            print(f"[SAVE] Saved {self.current_file} ({len(content)} chars) to {section_folder}/")
            
        except Exception as e:
            print(f"[ERROR] Failed to save {self.current_file}: {str(e)}")
        
        # Reset current file state
        self.current_file = None
        self.current_content = []

    def clean_file_content(self, content: str) -> str:
        """Clean and format file content"""
        lines = content.split('\n')
        cleaned_lines = []
        
        for line in lines:
            # Remove excessive whitespace but preserve indentation
            if line.strip():
                cleaned_lines.append(line.rstrip())
            else:
                cleaned_lines.append('')
        
        # Remove leading/trailing empty lines
        while cleaned_lines and not cleaned_lines[0].strip():
            cleaned_lines.pop(0)
        while cleaned_lines and not cleaned_lines[-1].strip():
            cleaned_lines.pop()
        
        return '\n'.join(cleaned_lines)

    def get_content_type(self, filename: str) -> str:
        """Get appropriate content type for file"""
        if filename.endswith('.py'):
            return 'text/x-python'
        elif filename.endswith('.cs'):
            return 'text/x-csharp'
        elif filename.endswith('.java'):
            return 'text/x-java'
        elif filename.endswith('.go'):
            return 'text/x-go'
        elif filename.endswith('.js'):
            return 'text/javascript'
        elif filename.endswith('.json'):
            return 'application/json'
        elif filename.endswith(('.yaml', '.yml')):
            return 'application/x-yaml'
        elif filename.endswith('.md'):
            return 'text/markdown'
        elif filename.endswith('.sh'):
            return 'text/x-shellscript'
        elif filename.endswith('.sql'):
            return 'text/x-sql'
        elif filename.startswith('Dockerfile'):
            return 'text/x-dockerfile'
        elif filename.endswith('.tf'):
            return 'text/x-terraform'
        elif filename.endswith('.csproj'):
            return 'application/xml'
        elif filename.endswith('.xml'):
            return 'application/xml'
        else:
            return 'text/plain'

    def process_streaming_response(self, prompt: str) -> Dict[str, Any]:
        """Process streaming response and extract files"""
        print(f"[STREAMING] Starting file extraction")
        
        try:
            total_chunks = 0
            total_lines = 0
            
            # Stream response and process line by line
            for chunk in self.stream_bedrock_response(prompt):
                self.buffer += chunk
                total_chunks += 1
                
                # Process complete lines
                while '\n' in self.buffer:
                    line, self.buffer = self.buffer.split('\n', 1)
                    total_lines += 1
                    
                    # Log every 100 lines to track progress
                    if total_lines % 100 == 0:
                        print(f"[STREAMING] Processed {total_lines} lines, {total_chunks} chunks")
                    
                    self.process_line(line)
            
            print(f"[STREAMING] Finished processing: {total_lines} lines, {total_chunks} chunks")
            print(f"[STREAMING] Buffer remaining: {len(self.buffer)} characters")
            
            # Process any remaining buffer
            if self.buffer.strip():
                print(f"[STREAMING] Processing remaining buffer: {len(self.buffer)} chars")
                self.process_line(self.buffer)
                if self.current_file and self.current_content:
                    self.save_current_file()
            
            # Save any remaining file
            if self.current_file and self.current_content:
                print(f"[STREAMING] Saving final file: {self.current_file}")
                self.save_current_file()
            
            # Process any remaining buffer
            if self.buffer.strip():
                self.process_line(self.buffer)
                if self.current_file and self.current_content:
                    self.save_current_file()
            
            print(f"[STREAMING] Total files created: {len(self.files_created)}")
            for file_info in self.files_created:
                print(f"[STREAMING] Created: {file_info['filename']} in {file_info['section']} ({file_info['size']} chars)")
            
            # Group files by section for summary
            files_by_section = {}
            for file_info in self.files_created:
                section = file_info['section']
                if section not in files_by_section:
                    files_by_section[section] = []
                files_by_section[section].append(file_info)
            
            return {
                'status': 'success',
                'total_files_created': len(self.files_created),
                'files_by_section': files_by_section,
                'all_files': self.files_created
            }
            
        except Exception as e:
            print(f"[STREAMING ERROR] {str(e)}")
            import traceback
            print(f"[STREAMING ERROR] Traceback: {traceback.format_exc()}")
            return {'status': 'error', 'error': str(e)}

class MainframeAnalyzer:
    """Main analyzer class that integrates with streaming file extraction"""
    
    def __init__(self):
        self.s3_client = boto3.client('s3')
        self.bedrock_client = boto3.client('bedrock-runtime')
        self.dynamodb = boto3.resource('dynamodb')
        
    def update_job_status(self, job_id: str, status: str, message: str = None):
        """Update job status in DynamoDB"""
        try:
            table_name = os.environ.get('JOBS_TABLE_NAME', 'MainframeAnalyzerJobs')
            table = self.dynamodb.Table(table_name)
            
            update_expression = 'SET #status = :status, updated_at = :updated_at'
            expression_attr_names = {'#status': 'status'}
            expression_attr_values = {
                ':status': status,
                ':updated_at': int(time.time())
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
            
            print(f"[STATUS] Updated job {job_id} to {status}")
            
        except Exception as e:
            print(f"[ERROR] Failed to update job status: {str(e)}")

    def get_aggregated_content(self, bucket_name: str, full_prompt_key: str) -> str:
        """Get aggregated content from S3 using the correct key parameter"""
        try:
            print(f"[S3] Getting aggregated content from s3://{bucket_name}/{full_prompt_key}")
            
            response = self.s3_client.get_object(Bucket=bucket_name, Key=full_prompt_key)
            content = response['Body'].read().decode('utf-8')
            
            print(f"[S3] Retrieved {len(content)} characters of aggregated content")
            return content
            
        except Exception as e:
            print(f"[ERROR] Failed to get aggregated content: {str(e)}")
            raise

    def lambda_handler(self, event, context):
        """Main Lambda handler for mainframe analysis with streaming file extraction"""
        try:
            print(f"[HANDLER] Received event: {json.dumps(event, default=str)}")
            
            # Extract parameters from the event
            bucket_name = event.get('bucket_name')
            full_prompt_key = event.get('full_prompt_key')  # Use the correct key from Step Functions
            job_id = event.get('job_id')
            output_path = event.get('output_path')
            
            if not bucket_name:
                raise ValueError("bucket_name is required")
            
            if not job_id:
                raise ValueError("job_id is required")
                
            if not full_prompt_key:
                raise ValueError("full_prompt_key is required")
            
            # Update job status to processing
            self.update_job_status(job_id, 'PROCESSING', 'Starting mainframe analysis with streaming file extraction')
            
            # Get aggregated content from S3 using the correct key
            aggregated_content = self.get_aggregated_content(bucket_name, full_prompt_key)
            
            if not aggregated_content:
                raise ValueError("No aggregated content found for analysis")
            
            # Create enhanced analysis prompt for streaming file extraction
            prompt = f"""
Please analyze the following mainframe documentation and provide comprehensive modernization recommendations with structured AWS implementations:

{aggregated_content}

Please provide a complete modernization solution organized by AWS service categories. For each service category, create specific implementation files:

1. **Lambda Functions**: Create Python Lambda functions for business logic migration
2. **IAM Roles**: Define security roles and policies for each service
3. **DynamoDB**: Design NoSQL table structures for data migration
4. **S3**: Configure storage buckets and lifecycle policies
5. **Step Functions**: Orchestrate complex workflows
6. **API Gateway**: Create REST/GraphQL APIs for external interfaces
7. **CloudFormation**: Infrastructure as Code templates
8. **Documentation**: README, architecture diagrams, and implementation reasoning

Focus on:
- Production-ready, secure implementations
- Best practices for each AWS service
- Proper error handling and monitoring
- Cost optimization strategies
- Migration-specific considerations for mainframe workloads

Provide complete, deployable code for each component.
"""
            
            # Create streaming file extractor
            output_prefix = f"{output_path}/aws-artifacts"
            extractor = StreamingFileExtractor(bucket_name, output_prefix)
            
            print(f"[ANALYSIS] Starting streaming analysis for job {job_id}")
            print(f"[OUTPUT] Files will be organized under: s3://{bucket_name}/{output_prefix}/")
            
            # Process streaming response and extract files
            streaming_result = extractor.process_streaming_response(prompt)
            
            if streaming_result['status'] == 'error':
                raise ValueError(f"Streaming analysis failed: {streaming_result['error']}")
            
            # Save analysis summary to results folder
            summary_key = f"{output_path}/aws-artifacts/results/analysis-summary.json"
            summary_content = {
                'job_id': job_id,
                'analysis_timestamp': int(time.time()),
                'total_files_created': streaming_result['total_files_created'],
                'files_by_section': streaming_result['files_by_section'],
                'output_location': f's3://{bucket_name}/{output_prefix}/',
                'status': 'COMPLETED'
            }
            
            self.s3_client.put_object(
                Bucket=bucket_name,
                Key=summary_key,
                Body=json.dumps(summary_content, indent=2).encode('utf-8'),
                ContentType='application/json'
            )
            
            # Create a comprehensive analysis report
            report_content = self.generate_analysis_report(streaming_result, job_id)
            report_key = f"{output_path}/aws-artifacts/results/analysis-report.md"
            
            self.s3_client.put_object(
                Bucket=bucket_name,
                Key=report_key,
                Body=report_content.encode('utf-8'),
                ContentType='text/markdown'
            )
            
            # Update job status to completed
            completion_message = f'Analysis completed successfully. {streaming_result["total_files_created"]} files created across {len(streaming_result["files_by_section"])} service categories. Results saved to s3://{bucket_name}/{output_prefix}/'
            
            self.update_job_status(
                job_id, 
                'COMPLETED', 
                completion_message
            )
            
            return {
                'job_id': job_id,
                'bucket_name': bucket_name,  # Add bucket_name for Step Functions
                'output_path': output_path,  # Add output_path for Step Functions
                'status': 'COMPLETED',
                'total_files_created': streaming_result['total_files_created'],
                'files_by_section': streaming_result['files_by_section'],
                'output_location': f's3://{bucket_name}/{output_prefix}/',
                'summary_location': f's3://{bucket_name}/{summary_key}',
                'report_location': f's3://{bucket_name}/{report_key}',
                'message': completion_message
            }
            
        except Exception as e:
            error_msg = f"Analysis failed: {str(e)}"
            print(f"[ERROR] {error_msg}")
            print(traceback.format_exc())
            
            # Update job status to failed if job_id is available
            if 'job_id' in locals():
                self.update_job_status(job_id, 'FAILED', error_msg)
            
            return {
                'job_id': job_id if 'job_id' in locals() else None,
                'bucket_name': bucket_name if 'bucket_name' in locals() else None,  # Add bucket_name for Step Functions
                'output_path': output_path if 'output_path' in locals() else None,  # Add output_path for Step Functions
                'status': 'FAILED',
                'error': error_msg
            }

    def generate_analysis_report(self, streaming_result: Dict[str, Any], job_id: str) -> str:
        """Generate a comprehensive analysis report"""
        report_lines = [
            "# Mainframe Modernization Analysis Report",
            f"",
            f"**Job ID:** {job_id}",
            f"**Analysis Date:** {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}",
            f"**Total Files Generated:** {streaming_result['total_files_created']}",
            f"",
            "## Generated AWS Components",
            f""
        ]
        
        # Add section summaries
        for section, files in streaming_result['files_by_section'].items():
            section_name = section.replace('_', ' ').title()
            report_lines.append(f"### {section_name}")
            report_lines.append(f"")
            
            for file_info in files:
                report_lines.append(f"- **{file_info['filename']}** ({file_info['size']} bytes)")
                report_lines.append(f"  - Location: `{file_info['s3_path']}`")
                report_lines.append(f"  - Type: {file_info['content_type']}")
            
            report_lines.append(f"")
        
        report_lines.extend([
            "## Implementation Guide",
            "",
            "1. **Review Generated Components**: Examine each AWS service implementation in its respective folder",
            "2. **Deploy Infrastructure**: Start with CloudFormation templates to provision AWS resources",
            "3. **Configure Security**: Apply IAM roles and policies for proper access control",
            "4. **Deploy Applications**: Upload Lambda functions and configure API Gateway endpoints",
            "5. **Data Migration**: Use DynamoDB configurations for data structure migration",
            "6. **Testing**: Validate each component before production deployment",
            "",
            "## Next Steps",
            "",
            "- Review the architecture documentation for system design overview",
            "- Examine the reasoning document for technical decisions and trade-offs",
            "- Follow the README for detailed setup and deployment instructions",
            "- Consider the migration roadmap for phased implementation approach",
            "",
            f"**Analysis completed successfully at {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}**"
        ])
        
        return '\n'.join(report_lines)

# Global instance for Lambda reuse
analyzer = MainframeAnalyzer()

def lambda_handler(event, context):
    """Lambda entry point"""
    return analyzer.lambda_handler(event, context)
