# Mainframe Modernization Project Architecture Analysis

## Overview

This project implements a serverless architecture for analyzing mainframe documentation to assist with modernization efforts. The system processes various document formats (PDF, DOCX, TXT), extracts text content, aggregates it, and uses Amazon Bedrock to analyze the content and provide modernization recommendations.

## Architecture Components

The architecture consists of several Lambda functions orchestrated by AWS Step Functions:

1. **Initial Lambda (`initial_lambda.py`)**
   - Entry point for the workflow
   - Validates input parameters (S3 bucket and folder path)
   - Lists files in the specified S3 location
   - Creates a job record in DynamoDB
   - Starts the Step Functions workflow

2. **Process File Lambda (`process_file_lambda.py`)**
   - Extracts text from individual files (PDF, DOCX, TXT)
   - Uploads extracted text to S3
   - Updates job progress in DynamoDB

3. **Aggregate Lambda (`aggregate_lambda.py`)**
   - Combines extracted text from all processed files
   - Prepares the full prompt for analysis
   - Updates job status in DynamoDB

4. **Analysis Lambda (`analysis_lambda.py`)**
   - Sends the aggregated content to Amazon Bedrock for analysis
   - Parses the response by AWS service type
   - Saves results to S3
   - Updates job status to completed

5. **Status Lambda (`status_lambda.py`)**
   - Provides job status information
   - Retrieves execution details from Step Functions
   - Lists output files from S3

## Data Flow

1. User submits a job with S3 bucket and folder path
2. System lists files and creates a job record
3. Each file is processed in parallel to extract text
4. Extracted text is aggregated into a single document
5. Aggregated content is sent to Bedrock for analysis
6. Analysis results are saved to S3
7. User can check job status and retrieve results

## Key Features

- **Parallel Processing**: Files are processed in parallel for efficiency
- **Error Handling**: Robust error handling at each stage
- **Progress Tracking**: Job progress is tracked in DynamoDB
- **Adaptive Timeouts**: Timeout calculations based on input size
- **Service-Specific Output**: Analysis results are organized by AWS service type

## AWS Services Used

- **Lambda**: For serverless compute
- **Step Functions**: For workflow orchestration
- **DynamoDB**: For job tracking and status
- **S3**: For storage of input files and results
- **Bedrock**: For AI-powered analysis
- **IAM**: For security and access control

## Implementation Details

### Job Processing

The system uses a Step Functions workflow to coordinate the processing of files:

1. The initial Lambda creates a job record and starts the workflow
2. Files are processed in parallel using a Map state
3. Results are aggregated and sent for analysis
4. Final results are stored in S3

### Error Handling

Each Lambda function includes comprehensive error handling:

- Input validation
- S3 access verification
- Exception handling with detailed logging
- Status updates to DynamoDB on failures

### Adaptive Processing

The system adapts to different input sizes:

- Timeout calculations based on input length
- Automatic retry with reduced input on timeouts
- Maximum file limits to prevent overloading

## Conclusion

This architecture provides a scalable, serverless solution for analyzing mainframe documentation to assist with modernization efforts. The modular design allows for easy maintenance and extension of functionality.
