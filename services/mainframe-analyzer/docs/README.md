# Mainframe Modernization Project Documentation

## Overview

The Mainframe Modernization Project is a serverless application designed to analyze mainframe documentation and provide modernization recommendations. The system processes various document formats (PDF, DOCX, TXT), extracts text content, aggregates it, and uses Amazon Bedrock to analyze the content.

## Documentation Contents

- [Architecture](architecture.md): System architecture and components
- [Data Flow](data-flow.md): Data flow and processing stages
- [Deployment](deployment.md): Deployment and configuration instructions

## Quick Start

1. Clone the repository
2. Deploy the CloudFormation stack:
   ```bash
   cd mainframe-transform-project/scripts
   ./1.deploy.sh --region us-east-1 --env dev
   ```
3. Test the workflow:
   ```bash
   ./4.test-workflow.sh --bucket your-bucket --folder your-folder
   ```

## System Overview

The Mainframe Modernization Project consists of five Lambda functions orchestrated by AWS Step Functions:

1. **Initial Lambda**: Entry point for the workflow
2. **Process File Lambda**: Extracts text from individual files
3. **Aggregate Lambda**: Combines extracted text from all processed files
4. **Analysis Lambda**: Performs AI-powered analysis using Amazon Bedrock
5. **Status Lambda**: Provides job status information

## Key Features

- **Parallel Processing**: Files are processed in parallel for efficiency
- **Error Handling**: Robust error handling at each stage
- **Progress Tracking**: Job progress is tracked in DynamoDB
- **Adaptive Timeouts**: Timeout calculations based on input size
- **Service-Specific Output**: Analysis results are organized by AWS service type

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

For more detailed information, please refer to the specific documentation files linked above.
