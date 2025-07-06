# Streaming File Extraction Enhancements

## Overview

Both the Analysis Lambda and Chunk Processor Lambda functions have been enhanced with real-time streaming file extraction capabilities. This enhancement allows the system to extract individual AWS artifact files (Python, JSON, YAML, etc.) in real-time as the AI generates responses, rather than waiting for the complete response and then parsing it.

## Key Features Added

### 1. Real-Time Streaming File Extraction
- **StreamingFileExtractor Class**: Processes AI responses in real-time as they stream from Bedrock
- **Individual File Creation**: Creates separate, deployable files for each AWS service component
- **Immediate S3 Storage**: Files are saved to S3 as soon as they're complete, not at the end of processing

### 2. Enhanced File Organization
- **Service-Based Folders**: Files are organized by AWS service type (lambda-functions, iam-roles, etc.)
- **Multiple File Types**: Supports Python (.py), JSON (.json), YAML (.yml), Markdown (.md), Shell (.sh), SQL (.sql), Terraform (.tf), and more
- **Proper Content Types**: Each file is saved with the correct MIME type for better handling

### 3. Mainframe Modernization Focus
- **Specialized Patterns**: Enhanced detection patterns for mainframe modernization artifacts
- **Production-Ready Code**: Generated files include proper error handling, logging, and AWS best practices
- **Complete Implementations**: Each file contains complete, deployable code rather than just snippets

### 4. Chunk-Aware Processing
- **Chunk Identification**: Files from different chunks are uniquely named to avoid conflicts
- **Parallel Processing**: Multiple chunks can be processed simultaneously without file naming conflicts
- **Aggregated Results**: Results from all chunks are properly aggregated and organized

## Technical Implementation

### Analysis Lambda Enhancements

The analysis lambda (`analysis-lambda/lambda_function.py`) now includes:

```python
class StreamingFileExtractor:
    """Enhanced streaming analyzer that extracts individual files in real-time"""
    
    def __init__(self, bucket_name: str, output_prefix: str):
        # Initialize streaming state and patterns
        
    def stream_bedrock_response(self, prompt: str) -> Generator[str, None, None]:
        # Stream response from Bedrock with enhanced system prompt
        
    def process_streaming_chunk(self, chunk: str):
        # Process each streaming chunk and extract files in real-time
        
    def save_current_file(self):
        # Save individual files to S3 as they're completed
```

**Key Features:**
- Configurable streaming extraction (enabled by default)
- Fallback to traditional chunking approach
- Enhanced system prompts for mainframe modernization
- Real-time file extraction and S3 storage

### Chunk Processor Lambda Enhancements

The chunk processor lambda (`chunk-processor-lambda/lambda_function.py`) now includes:

```python
class ChunkStreamingExtractor:
    """Streaming extractor for chunk processing with individual file extraction"""
    
    def __init__(self, bucket_name: str, output_prefix: str, chunk_index: int):
        # Initialize with chunk-specific naming
        
    def save_current_file(self):
        # Add chunk identifier to filename to avoid conflicts
        chunk_filename = f"{base_name}_chunk{self.chunk_index}.{extension}"
```

**Key Features:**
- Chunk-specific file naming to prevent conflicts
- Individual file extraction per chunk
- Parallel processing support
- Enhanced error handling and logging

## File Organization Structure

The enhanced system creates the following S3 structure:

```
s3://bucket/output-path/
├── individual_files/                    # For analysis lambda
│   ├── lambda-functions/
│   │   ├── function1.py
│   │   ├── function2.py
│   │   └── ...
│   ├── iam-roles/
│   │   ├── role1.json
│   │   ├── role2.json
│   │   └── ...
│   ├── step-functions/
│   │   ├── workflow1.json
│   │   └── ...
│   └── cloudformation/
│       ├── template1.yaml
│       └── ...
├── chunk_1_files/                       # For chunk processor
│   ├── lambda-functions/
│   │   ├── function1_chunk1.py
│   │   └── ...
│   └── ...
├── chunk_2_files/
│   └── ...
└── results/
    ├── chunk_1_streaming_results.json
    └── ...
```

## Configuration Options

### Environment Variables

Both lambda functions support these new environment variables:

- `USE_STREAMING_EXTRACTION`: Enable/disable streaming extraction (default: true)
- `STREAMING_CHUNK_SIZE`: Size of streaming chunks for processing (default: 10000)
- `MAX_FILES_PER_SECTION`: Maximum files to create per service section (default: 50)

### Event Parameters

Both functions accept a new parameter in their event payload:

```json
{
  "job_id": "...",
  "bucket_name": "...",
  "use_streaming": true,  // Enable streaming extraction
  "..."
}
```

## Benefits

### 1. Faster Time to Value
- Files are available as soon as they're generated, not after complete processing
- Users can start working with generated artifacts immediately
- Reduced waiting time for large document processing

### 2. Better Resource Utilization
- Memory usage is more consistent as files are saved immediately
- Reduced risk of lambda timeouts due to large response processing
- More efficient S3 storage patterns

### 3. Enhanced Reliability
- Individual file failures don't affect other files
- Better error isolation and recovery
- More granular progress tracking

### 4. Improved User Experience
- Real-time progress feedback through file creation
- Individual file access for targeted development
- Better organization for large modernization projects

## Usage Examples

### Analysis Lambda with Streaming

```python
# Event payload
event = {
    "job_id": "analysis-123",
    "bucket_name": "mainframe-transform-dev",
    "full_prompt_key": "prompts/mainframe-analysis.txt",
    "use_streaming": True  # Enable streaming extraction
}

# Response includes individual files
response = {
    "status": "success",
    "streaming_extraction": True,
    "total_files_created": 25,
    "files_by_section": {
        "LAMBDA_FUNCTIONS": [
            {
                "filename": "batch_processor.py",
                "s3_path": "s3://bucket/path/lambda-functions/batch_processor.py",
                "size": 2048,
                "content_type": "text/x-python"
            }
        ]
    }
}
```

### Chunk Processor with Streaming

```python
# Event payload
event = {
    "job_id": "chunk-analysis-456",
    "chunk_index": 1,
    "total_chunks": 5,
    "use_streaming": True
}

# Response includes chunk-specific files
response = {
    "status": "success",
    "streaming_extraction": True,
    "chunk_index": 1,
    "total_files_created": 8,
    "all_files": [
        {
            "filename": "data_processor_chunk1.py",
            "original_filename": "data_processor.py",
            "chunk_index": 1,
            "section": "LAMBDA_FUNCTIONS"
        }
    ]
}
```

## Migration Guide

### Existing Deployments

1. **Backup Current Functions**: The enhanced functions maintain backward compatibility
2. **Update Environment Variables**: Add new streaming configuration variables
3. **Test with Streaming Disabled**: Set `use_streaming: false` to use original behavior
4. **Gradual Rollout**: Enable streaming for new jobs while keeping existing jobs unchanged

### Monitoring and Observability

The enhanced functions provide additional logging:

```
[STREAMING] Starting streaming file extraction analysis
[SECTION] Started section: LAMBDA_FUNCTIONS
[FILE] Started file: batch_processor.py in section LAMBDA_FUNCTIONS
[SAVE] Saved batch_processor.py (2048 chars) to lambda-functions/
[BEDROCK] Streamed 50,000 characters, created 12 files
```

## Future Enhancements

### Planned Features

1. **File Validation**: Automatic syntax validation for generated files
2. **Dependency Analysis**: Automatic detection of dependencies between generated files
3. **Template Generation**: Creation of deployment templates for generated artifacts
4. **Cost Estimation**: Automatic cost estimation for generated AWS resources

### Performance Optimizations

1. **Parallel File Processing**: Process multiple files simultaneously
2. **Intelligent Chunking**: Dynamic chunk sizing based on content complexity
3. **Caching**: Cache frequently used patterns and templates
4. **Compression**: Automatic compression for large files

## Troubleshooting

### Common Issues

1. **Files Not Being Created**
   - Check `use_streaming` parameter is set to `true`
   - Verify S3 permissions for the lambda execution role
   - Check CloudWatch logs for parsing errors

2. **Incomplete Files**
   - Review file completion detection logic
   - Check for streaming interruptions in logs
   - Verify Bedrock response format

3. **Naming Conflicts**
   - Ensure chunk processors use unique chunk identifiers
   - Check file naming patterns in logs
   - Verify S3 key generation logic

### Debug Mode

Enable detailed logging by setting environment variable:
```
DEBUG_STREAMING=true
```

This provides additional logging for:
- Buffer processing details
- File detection patterns
- S3 upload operations
- Error stack traces

## Conclusion

The streaming file extraction enhancements significantly improve the mainframe modernization platform's capability to generate individual, deployable AWS artifacts in real-time. This provides faster time to value, better resource utilization, and an enhanced user experience for large-scale modernization projects.

The implementation maintains backward compatibility while providing powerful new capabilities for modern cloud-native development workflows.
