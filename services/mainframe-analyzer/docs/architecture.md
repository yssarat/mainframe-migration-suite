# Mainframe Modernization Project Architecture

## Architecture Diagram

```
┌─────────────┐     ┌───────────────┐     ┌───────────────────┐
│             │     │               │     │                   │
│  S3 Bucket  │────▶│  Initial      │────▶│  Step Functions   │
│  (Input)    │     │  Lambda       │     │  State Machine    │
│             │     │               │     │                   │
└─────────────┘     └───────────────┘     └─────────┬─────────┘
                                                    │
                                                    ▼
┌─────────────┐     ┌───────────────┐     ┌───────────────────┐
│             │     │               │     │                   │
│  DynamoDB   │◀───▶│  Status       │◀────│  Map State        │
│  Table      │     │  Lambda       │     │  (Parallel        │
│             │     │               │     │   Processing)     │
└─────────────┘     └───────────────┘     └─────────┬─────────┘
                                                    │
                                                    ▼
┌─────────────┐     ┌───────────────┐     ┌───────────────────┐
│             │     │               │     │                   │
│  S3 Bucket  │◀───▶│  Process File │◀────│  Process File     │
│  (Extracted │     │  Lambda       │     │  Lambda (Multiple │
│   Text)     │     │               │     │  Parallel Invoc.) │
└─────────────┘     └───────────────┘     └─────────┬─────────┘
                                                    │
                                                    ▼
┌─────────────┐     ┌───────────────┐     ┌───────────────────┐
│             │     │               │     │                   │
│  S3 Bucket  │◀───▶│  Aggregate    │◀────│  Aggregate State  │
│  (Combined  │     │  Lambda       │     │                   │
│   Content)  │     │               │     │                   │
└─────────────┘     └───────────────┘     └─────────┬─────────┘
                                                    │
                                                    ▼
┌─────────────┐     ┌───────────────┐     ┌───────────────────┐
│             │     │               │     │                   │
│  Amazon     │◀───▶│  Analysis     │◀────│  Analysis State   │
│  Bedrock    │     │  Lambda       │     │                   │
│             │     │               │     │                   │
└─────────────┘     └───────────────┘     └───────────────────┘
                            │
                            ▼
                    ┌───────────────┐
                    │               │
                    │  S3 Bucket    │
                    │  (Results)    │
                    │               │
                    └───────────────┘
```

## System Components

### AWS Services Used

1. **AWS Lambda**: Serverless compute for processing documents and orchestrating the workflow
2. **Amazon S3**: Storage for input documents, extracted text, and analysis results
3. **Amazon DynamoDB**: NoSQL database for job tracking and status management
4. **AWS Step Functions**: Workflow orchestration for coordinating the processing steps
5. **Amazon Bedrock**: AI service for analyzing mainframe documentation
6. **AWS IAM**: Identity and access management for secure service interactions
7. **AWS CloudFormation**: Infrastructure as code for deploying the application

### Lambda Functions

1. **Initial Lambda (`initial-lambda`)**: 
   - Entry point for the workflow
   - Validates input parameters (S3 bucket and folder path)
   - Lists files in the specified S3 location
   - Creates a job record in DynamoDB
   - Starts the Step Functions workflow

2. **Process File Lambda (`process-file-lambda`)**: 
   - Extracts text from individual files (PDF, DOCX, TXT)
   - Uploads extracted text to S3
   - Updates job progress in DynamoDB

3. **Aggregate Lambda (`aggregate-lambda`)**: 
   - Combines extracted text from all processed files
   - Prepares the full prompt for analysis
   - Updates job status in DynamoDB

4. **Analysis Lambda (`analysis-lambda`)**: 
   - Sends the aggregated content to Amazon Bedrock for analysis
   - Parses the response by AWS service type
   - Saves results to S3
   - Updates job status to completed

5. **Status Lambda (`status-lambda`)**: 
   - Provides job status information
   - Retrieves execution details from Step Functions
   - Lists output files from S3
