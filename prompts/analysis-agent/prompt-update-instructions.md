# Prompt Update Instructions

## Required Updates for All Language Prompts

To ensure all prompts generate the required architecture.md and readme.md files, please update each language prompt (python-prompt.txt, java-prompt.txt, dotnet-prompt.txt, go-prompt.txt, javascript-prompt.txt, and default-prompt.txt) with the following additions:

### 1. Add ARCHITECTURE_DIAGRAM Section

Add this new section after the DYNAMODB section and before the README section:

```
## ARCHITECTURE_DIAGRAM
### architecture.md
```ascii
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           MAINFRAME MODERNIZATION PLATFORM                      │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐             │
│  │   MAINFRAME     │    │      AWS        │    │    BUSINESS     │             │
│  │   DATA FILES    │───▶│   PROCESSING    │───▶│   APPLICATIONS  │             │
│  │                 │    │    LAYER        │    │                 │             │
│  └─────────────────┘    └─────────────────┘    └─────────────────┘             │
│           │                       │                       │                     │
│           │                       │                       │                     │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐             │
│  │   S3 INPUT      │    │     LAMBDA      │    │    DYNAMODB     │             │
│  │   BUCKET        │───▶│   FUNCTIONS     │───▶│    TABLES       │             │
│  │                 │    │                 │    │                 │             │
│  │ • VSAM Files    │    │ • Converter     │    │ • Account Data  │             │
│  │ • Event Trigger │    │ • Processor     │    │ • Job Status    │             │
│  │ • Versioning    │    │ • Generator     │    │                 │             │
│  └─────────────────┘    └─────────────────┘    └─────────────────┘             │
│           │                       │                       │                     │
│           │              ┌─────────────────┐              │                     │
│           │              │  STEP FUNCTIONS │              │                     │
│           └─────────────▶│   WORKFLOWS     │◀─────────────┘                     │
│                          │                 │                                    │
│                          │ • VSAM Conv.    │                                    │
│                          │ • Account Proc. │                                    │
│                          └─────────────────┘                                    │
│                                   │                                             │
│                          ┌─────────────────┐                                    │
│                          │   S3 OUTPUT     │                                    │
│                          │    BUCKET       │                                    │
│                          │                 │                                    │
│                          │ • Standard      │                                    │
│                          │ • Array         │                                    │
│                          │ • Variable      │                                    │
│                          └─────────────────┘                                    │
│                                   │                                             │
│                          ┌─────────────────┐                                    │
│                          │ NOTIFICATIONS   │                                    │
│                          │                 │                                    │
│                          │ • SNS Topics    │                                    │
│                          │ • CloudWatch    │                                    │
│                          │                 │                                    │
│                          └─────────────────┘                                    │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 2. Update README Section

Replace the existing README.md content with this format:

```
## README
### readme.md
```markdown
## Executive Summary of the Modernization Approach

This document outlines the modernization approach for migrating the CBACT01C mainframe batch program to AWS. The program reads account records from an indexed file, processes the data, and writes the processed information into multiple output files with different formats. The modernization strategy focuses on creating a serverless, event-driven architecture that maintains the core business logic while leveraging AWS services for improved scalability, reliability, and cost efficiency.


### Implementation Roadmap and Dependencies

1. **Infrastructure Setup (Week 1)**
   - Create S3 buckets for input and output files
   - Configure IAM roles and policies
   - Set up CloudWatch logging and monitoring

2. **Core Processing Implementation (Week 2)**
   - Develop Lambda function for account data processing
   - Implement data transformation logic
   - Create output file generation modules

3. **Integration and Event Configuration (Week 3)**
   - Configure S3 event notifications
   - Set up error handling and retry mechanisms
   - Implement monitoring and alerting

4. **Testing and Validation (Week 4)**
   - Perform unit and integration testing
   - Validate data transformation accuracy
   - Test error handling and recovery

5. **Deployment and Cutover (Week 5)**
   - Deploy to production environment
   - Perform parallel runs with mainframe system
   - Monitor performance and make adjustments

### Data Flow Descriptions

1. **Input Processing**
   - Account data files are uploaded to the input S3 bucket
   - S3 event notification triggers the Lambda function
   - Lambda function reads and validates the input data

2. **Data Transformation**
   - Lambda function processes account records according to business rules
   - Performs data transformations and calculations
   - Handles special cases (e.g., default values for zero amounts)

3. **Output Generation**
   - Creates three different output formats:
     - Fixed-length records (equivalent to OUT-FILE)
     - Array-structured records (equivalent to ARRY-FILE)
     - Variable-length records (equivalent to VBRC-FILE)
   - Writes output files to the designated S3 bucket

### Security Considerations

- **Data Protection**
  - S3 buckets configured with server-side encryption
  - Data in transit protected with TLS
  - Bucket policies to restrict access

- **Access Control**
  - IAM roles with least privilege permissions
  - Resource-based policies for S3 buckets
  - Secure Lambda execution environment

- **Monitoring and Auditing**
  - CloudTrail for API activity logging
  - CloudWatch for operational monitoring
  - S3 access logging enabled

### Cost Optimization Strategies

- **Serverless Architecture**
  - Pay-only-for-what-you-use Lambda execution
  - No idle infrastructure costs

- **Storage Optimization**
  - S3 lifecycle policies for output file management
  - S3 storage class selection based on access patterns

- **Operational Efficiency**
  - Automated error handling reduces manual intervention
  - Event-driven architecture eliminates polling costs

### Monitoring and Logging Approach

- **Lambda Function Monitoring**
  - CloudWatch metrics for invocation count, duration, and errors
  - Custom metrics for business-specific KPIs

- **Comprehensive Logging**
  - Structured logging with consistent format
  - Log levels for different severity of events
  - Log retention policies aligned with business requirements

- **Alerting**
  - CloudWatch alarms for error thresholds
  - SNS notifications for critical failures
  - Dashboard for operational visibility

### Error Handling Strategies

- **Input Validation**
  - Validate file format and content before processing
  - Reject and notify on invalid input

- **Processing Errors**
  - Graceful handling of business rule exceptions
  - Detailed error messages with context

- **System Failures**
  - Automatic retries for transient failures
  - Dead-letter queue for persistent failures
  - Comprehensive error reporting

### Deployment Instructions

1. **Prerequisites**
   - AWS CLI configured with appropriate permissions
   - AWS SAM CLI installed for serverless deployment
   - [LANGUAGE-SPECIFIC TOOLS] for Lambda development

2. **Deployment Steps**
   - Clone the repository
   - Run `sam build` to build the application
   - Run `sam deploy --guided` for interactive deployment
   - Follow prompts to configure deployment parameters

3. **Verification**
   - Upload a test file to the input S3 bucket
   - Verify Lambda execution in CloudWatch Logs
   - Check output files in the output S3 bucket
```

### 3. Update the CRITICAL Instruction

Update the initial CRITICAL instruction at the top of each prompt to include these new files:

```
CRITICAL: Generate complete, production-ready AWS artifacts for [LANGUAGE]-based solutions in this EXACT structure:
```

Change to:

```
CRITICAL: Generate complete, production-ready AWS artifacts for [LANGUAGE]-based solutions in this EXACT structure, including architecture.md and readme.md files:
```

## Implementation Steps

1. Edit each language prompt file:
   - python-prompt.txt
   - java-prompt.txt
   - dotnet-prompt.txt
   - go-prompt.txt
   - javascript-prompt.txt
   - default-prompt.txt

2. For each file:
   - Update the CRITICAL instruction
   - Add the ARCHITECTURE_DIAGRAM section
   - Update the README section

3. After updating all prompts, upload them to S3 using the upload-prompts.sh script

## Language-Specific Adjustments

For each language prompt, make sure to adjust the [LANGUAGE-SPECIFIC TOOLS] section in the readme.md template to match the language:

- **Python**: "Python 3.9+ for Lambda development"
- **Java**: "Java 11+ JDK and Maven for Lambda development"
- **Go**: "Go 1.21+ for Lambda development"
- **.NET**: ".NET 6+ SDK for Lambda development"
- **JavaScript**: "Node.js 18+ for Lambda development"
- **Default**: "Appropriate runtime for Lambda development"
