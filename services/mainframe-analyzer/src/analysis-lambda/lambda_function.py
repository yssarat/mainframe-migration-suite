import json
import boto3
import botocore
import botocore.config
import os
import time
import traceback
import re
from typing import Dict, Any, List, Generator, Optional
from dataclasses import dataclass

# Initialize clients
s3_client = boto3.client('s3')
dynamodb = boto3.resource('dynamodb')

# Initialize global variable for throttling
time_last = 0

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
        """Stream response from Bedrock with enhanced system prompt for mainframe modernization"""
        try:
            model_id = os.environ.get('BEDROCK_MODEL_ID', 'us.anthropic.claude-3-7-sonnet-20250219-v1:0')
            
            # Enhanced system prompt for mainframe modernization with structured output
            system_prompt = """You are an expert AWS architect specializing in mainframe modernization. 

CRITICAL: Generate complete, production-ready AWS artifacts in this EXACT structure:

## LAMBDA_FUNCTIONS
### function_name.py
```python
[Complete Python Lambda function with all imports, error handling, and logging]
```

## IAM_ROLES  
### role_name.json
```json
{
  "Version": "2012-10-17",
  "Statement": [complete IAM policy]
}
```

## STEP_FUNCTIONS
### workflow_name.json
```json
{
  "Comment": "Mainframe modernization workflow",
  "StartAt": "...",
  [complete state machine definition]
}
```

## DYNAMODB
### table_name.json
```json
{
  "TableName": "...",
  "AttributeDefinitions": [...],
  [complete table definition]
}
```

## CLOUDFORMATION
### template_name.yaml
```yaml
AWSTemplateFormatVersion: '2010-09-09'
Description: 'Mainframe modernization infrastructure'
Resources:
  [complete CloudFormation template]
```

## README
### README.md
```markdown
# Mainframe Modernization Project

## Overview
This project implements a comprehensive AWS serverless solution to modernize mainframe batch processing systems. The solution replaces traditional mainframe components with cloud-native AWS services, providing improved scalability, reliability, and cost efficiency while maintaining functional compatibility with existing business processes.

## Architecture Overview
The modernized architecture follows AWS Well-Architected Framework principles and implements an event-driven, serverless design. For detailed architecture diagrams and component relationships, see [architecture.md](architecture.md).

### Key Components:
- **S3 Input Bucket**: Receives mainframe data files with event triggers
- **Lambda Functions**: Process business logic with automatic scaling
- **Step Functions**: Orchestrate complex workflows with error handling
- **DynamoDB**: Store processed data with high performance
- **S3 Output Bucket**: Store generated reports and processed files
- **SNS/EventBridge**: Handle notifications and event routing
- **CloudWatch**: Monitor all components with comprehensive logging

## Data Flow
1. Mainframe data files uploaded to S3 Input Bucket
2. S3 event triggers Lambda function for initial processing
3. Step Functions orchestrates multi-step workflow
4. Lambda functions process data and store in DynamoDB
5. Output generation Lambda creates reports in S3 Output Bucket
6. SNS notifications sent for completion/errors
7. EventBridge routes events for downstream processing

## Deployment
### Prerequisites
- AWS CLI configured with appropriate permissions
- CloudFormation deployment capabilities
- S3 buckets for Lambda deployment packages

### Deployment Steps
1. Deploy infrastructure using CloudFormation template
2. Upload Lambda function packages to deployment bucket
3. Configure environment variables and parameters
4. Test workflow with sample data files
5. Configure monitoring and alerting

## Security Considerations
- All data encrypted at rest and in transit
- IAM roles follow principle of least privilege
- VPC endpoints for secure service communication
- KMS encryption for sensitive data
- CloudTrail logging for audit compliance

## Cost Optimization
- Serverless architecture eliminates idle resource costs
- DynamoDB on-demand pricing for variable workloads
- S3 lifecycle policies for automatic archiving
- Lambda memory optimization for cost efficiency
- CloudWatch log retention policies

## Monitoring and Logging
- CloudWatch dashboards for operational visibility
- Custom metrics for business KPIs
- Automated alerting for error conditions
- X-Ray tracing for performance analysis
- Structured logging across all components

## Error Handling
- Comprehensive retry mechanisms with exponential backoff
- Dead letter queues for failed message processing
- Circuit breaker patterns for external dependencies
- Graceful degradation for non-critical failures
- Automated recovery procedures where possible
```

## ARCHITECTURE
### architecture.md
```markdown
# Mainframe Modernization Architecture

## System Architecture Diagram

```
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
│  │ • File Upload   │    │ • Data Process  │    │ • Account Data  │             │
│  │ • Event Trigger │    │ • Validation    │    │ • Audit Logs    │             │
│  │ • Versioning    │    │ • Transform     │    │ • Job Status    │             │
│  └─────────────────┘    └─────────────────┘    └─────────────────┘             │
│           │                       │                       │                     │
│           │              ┌─────────────────┐              │                     │
│           │              │  STEP FUNCTIONS │              │                     │
│           └─────────────▶│   ORCHESTRATOR  │◀─────────────┘                     │
│                          │                 │                                    │
│                          │ • Workflow Mgmt │                                    │
│                          │ • Error Handling│                                    │
│                          │ • State Machine │                                    │
│                          └─────────────────┘                                    │
│                                   │                                             │
│                          ┌─────────────────┐                                    │
│                          │   S3 OUTPUT     │                                    │
│                          │    BUCKET       │                                    │
│                          │                 │                                    │
│                          │ • Reports       │                                    │
│                          │ • Processed Data│                                    │
│                          │ • Audit Files   │                                    │
│                          └─────────────────┘                                    │
│                                   │                                             │
│                          ┌─────────────────┐                                    │
│                          │ NOTIFICATIONS   │                                    │
│                          │                 │                                    │
│                          │ • SNS Topics    │                                    │
│                          │ • EventBridge   │                                    │
│                          │ • CloudWatch    │                                    │
│                          └─────────────────┘                                    │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

## Detailed Component Architecture

### Data Ingestion Layer
```
┌─────────────────────────────────────────────────────────────────┐
│                    DATA INGESTION LAYER                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Mainframe Files ──┐                                           │
│                    │                                           │
│  COBOL Programs ───┼──▶ S3 Input Bucket ──▶ Lambda Trigger    │
│                    │         │                     │           │
│  JCL Scripts ──────┘         │                     │           │
│                              │                     ▼           │
│                              │            ┌─────────────────┐  │
│                              │            │  File Processor │  │
│                              │            │     Lambda      │  │
│                              │            │                 │  │
│                              │            │ • Validation    │  │
│                              │            │ • Parsing       │  │
│                              │            │ • Metadata Ext │  │
│                              │            └─────────────────┘  │
│                              │                     │           │
│                              ▼                     ▼           │
│                    ┌─────────────────┐   ┌─────────────────┐  │
│                    │   CloudWatch    │   │  Step Functions │  │
│                    │     Logs        │   │   Workflow      │  │
│                    └─────────────────┘   └─────────────────┘  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Processing Layer
```
┌─────────────────────────────────────────────────────────────────┐
│                     PROCESSING LAYER                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────┐ │
│  │  ACCOUNT DATA   │    │   VALIDATION    │    │   BUSINESS  │ │
│  │   PROCESSOR     │    │    LAMBDA       │    │    LOGIC    │ │
│  │                 │    │                 │    │   LAMBDA    │ │
│  │ • Parse Records │    │ • Data Quality  │    │ • Transform │ │
│  │ • Extract Fields│    │ • Schema Valid  │    │ • Calculate │ │
│  │ • Format Data   │    │ • Error Check   │    │ • Aggregate │ │
│  └─────────────────┘    └─────────────────┘    └─────────────┘ │
│           │                       │                       │     │
│           └───────────────────────┼───────────────────────┘     │
│                                   │                             │
│                          ┌─────────────────┐                    │
│                          │  STEP FUNCTIONS │                    │
│                          │   COORDINATOR   │                    │
│                          │                 │                    │
│                          │ • Parallel Exec │                    │
│                          │ • Error Retry   │                    │
│                          │ • State Mgmt    │                    │
│                          │ • Flow Control  │                    │
│                          └─────────────────┘                    │
│                                   │                             │
│                          ┌─────────────────┐                    │
│                          │    DYNAMODB     │                    │
│                          │   DATA STORE    │                    │
│                          │                 │                    │
│                          │ • Account Table │                    │
│                          │ • Audit Table   │                    │
│                          │ • Job Status    │                    │
│                          └─────────────────┘                    │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Output and Notification Layer
```
┌─────────────────────────────────────────────────────────────────┐
│                OUTPUT & NOTIFICATION LAYER                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────┐ │
│  │   REPORT GEN    │    │   FILE OUTPUT   │    │   ARCHIVE   │ │
│  │    LAMBDA       │    │     LAMBDA      │    │   LAMBDA    │ │
│  │                 │    │                 │    │             │ │
│  │ • Format Report │    │ • Generate CSV  │    │ • Compress  │ │
│  │ • Create Summary│    │ • Create JSON   │    │ • Store     │ │
│  │ • Add Metadata  │    │ • Format Output │    │ • Lifecycle │ │
│  └─────────────────┘    └─────────────────┘    └─────────────┘ │
│           │                       │                       │     │
│           └───────────────────────┼───────────────────────┘     │
│                                   │                             │
│                          ┌─────────────────┐                    │
│                          │   S3 OUTPUT     │                    │
│                          │    BUCKETS      │                    │
│                          │                 │                    │
│                          │ • Reports/      │                    │
│                          │ • Processed/    │                    │
│                          │ • Archive/      │                    │
│                          │ • Audit/        │                    │
│                          └─────────────────┘                    │
│                                   │                             │
│                          ┌─────────────────┐                    │
│                          │  NOTIFICATIONS  │                    │
│                          │                 │                    │
│                          │ ┌─────────────┐ │                    │
│                          │ │     SNS     │ │                    │
│                          │ │   Topics    │ │                    │
│                          │ └─────────────┘ │                    │
│                          │ ┌─────────────┐ │                    │
│                          │ │ EventBridge │ │                    │
│                          │ │    Rules    │ │                    │
│                          │ └─────────────┘ │                    │
│                          │ ┌─────────────┐ │                    │
│                          │ │ CloudWatch  │ │                    │
│                          │ │   Alarms    │ │                    │
│                          │ └─────────────┘ │                    │
│                          └─────────────────┘                    │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Service Integration Flow

### Data Processing Workflow
1. **File Upload**: Mainframe files uploaded to S3 Input Bucket
2. **Event Trigger**: S3 event triggers File Processor Lambda
3. **Validation**: Lambda validates file format and structure
4. **Workflow Start**: Step Functions workflow initiated
5. **Parallel Processing**: Multiple Lambda functions process data in parallel
6. **Data Storage**: Processed data stored in DynamoDB
7. **Report Generation**: Output Lambda generates reports
8. **File Output**: Reports saved to S3 Output Bucket
9. **Notifications**: SNS/EventBridge send completion notifications

### Error Handling Flow
1. **Error Detection**: Lambda functions detect processing errors
2. **Retry Logic**: Step Functions implements exponential backoff retry
3. **Dead Letter Queue**: Failed messages sent to DLQ for analysis
4. **Alert Generation**: CloudWatch alarms trigger notifications
5. **Manual Intervention**: Operations team notified for manual resolution

## Security Architecture

### Data Protection
- **Encryption at Rest**: All S3 buckets and DynamoDB tables encrypted with KMS
- **Encryption in Transit**: All API calls use TLS 1.2+
- **Access Control**: IAM roles with least privilege principles
- **Network Security**: VPC endpoints for service communication

### Monitoring and Compliance
- **CloudTrail**: All API calls logged for audit
- **CloudWatch**: Comprehensive monitoring and alerting
- **X-Ray**: Distributed tracing for performance analysis
- **Config**: Resource configuration compliance monitoring
```

## REASONING
### reasoning.md
```markdown
# Detailed Service Selection Reasoning for Mainframe Modernization

## AWS Service Selection Methodology

This document provides comprehensive reasoning for each AWS service selection in the mainframe modernization project, including alternatives considered, trade-offs made, and consistency explanations for similar components.

## Core Processing Services

### AWS Lambda for Business Logic Processing

**Selection Reasoning**: AWS Lambda was chosen as the primary compute service because:

1. **Stateless Processing**: The original mainframe program performs discrete data processing operations that map perfectly to Lambda's stateless execution model
2. **Event-Driven Architecture**: Lambda integrates seamlessly with S3 events, allowing automatic triggering when new data files are uploaded
3. **Cost Efficiency**: Pay-per-use pricing model is ideal for batch processing workloads that may run infrequently
4. **Scalability**: Automatic scaling handles varying volumes of data without manual intervention
5. **Language Support**: Allows reimplementation of legacy COBOL logic in modern languages like Python

**Alternatives Considered**:
- **EC2 Instances**: Rejected due to higher operational overhead and continuous running costs even during idle periods
- **AWS Batch**: Considered but deemed unnecessary for this processing complexity level
- **AWS Fargate**: Rejected as containerization adds complexity without significant benefits for this workload

**Trade-offs**:
- Lambda has 15-minute execution time limit, but this is sufficient for expected data volumes
- Cold start latency may impact initial processing time, but acceptable for batch operations
- Memory limitations require careful optimization for large data processing

### AWS Step Functions for Workflow Orchestration

**Selection Reasoning**: Step Functions was selected for workflow orchestration because:

1. **Visual Workflow**: Provides clear visual representation of processing steps, improving maintainability
2. **Error Handling**: Built-in retry mechanisms and error handling improve system reliability
3. **State Management**: Maintains workflow state across multiple Lambda invocations
4. **Integration**: Native integration with Lambda, DynamoDB, and other AWS services
5. **Monitoring**: Detailed execution history and CloudWatch integration for operational visibility

**Alternatives Considered**:
- **SQS/SNS Chains**: More complex to manage and monitor without visual workflow benefits
- **Custom Orchestration Logic**: Would require additional development and maintenance effort
- **AWS Batch**: Lacks the fine-grained control and visual workflow representation

**Trade-offs**:
- Step Functions adds a small cost overhead, but operational benefits outweigh this concern
- Introduces another service to learn and manage, but simplifies overall architecture complexity

## Data Storage Services

### Amazon DynamoDB for Structured Data

**Selection Reasoning**: DynamoDB was chosen for processed account data because:

1. **Schema Flexibility**: Accommodates various account record structures without rigid schema constraints
2. **Performance**: Single-digit millisecond response times support rapid data retrieval
3. **Scalability**: Automatic scaling handles varying data volumes without manual intervention
4. **Integration**: Seamless integration with Lambda and other AWS services
5. **Managed Service**: No operational overhead for database management, patching, or backups

**Alternatives Considered**:
- **Amazon RDS**: Rejected as the relational model adds unnecessary complexity for this data structure
- **Amazon DocumentDB**: Overkill for the relatively simple document structure of account records
- **Amazon Neptune**: The data doesn't have complex relationships requiring a graph database

**Trade-offs**:
- DynamoDB pricing can be higher for large data volumes, but expected volume is manageable
- Query flexibility is more limited compared to SQL databases, but access patterns are simple and well-defined
- Eventually consistent reads may require careful application design

### Amazon S3 for File Storage

**Selection Reasoning**: S3 was selected to replace traditional file systems because:

1. **Durability**: 99.999999999% durability far exceeds traditional file systems
2. **Scalability**: Virtually unlimited storage capacity eliminates capacity planning concerns
3. **Event Notifications**: S3 can trigger Lambda functions when new files are uploaded
4. **Versioning**: Provides audit trail and recovery options not available in original system
5. **Cost Efficiency**: Tiered storage classes allow cost optimization based on access patterns

**Alternatives Considered**:
- **EFS/FSx**: Rejected as they introduce unnecessary complexity for simple file operations
- **Amazon Glacier**: Too slow for operational data that needs regular access
- **Database BLOBs**: Would complicate the architecture without adding significant value

**Trade-offs**:
- S3 doesn't support traditional file locking mechanisms, but not required for read-only processing
- Eventual consistency for overwrite operations, but doesn't impact our create-new-object workflow

## Integration and Communication Services

### Amazon SNS for Notifications

**Selection Reasoning**: SNS was chosen for system notifications because:

1. **Pub/Sub Model**: Decouples notification producers from consumers
2. **Multiple Protocols**: Supports email, SMS, HTTP, and other delivery methods
3. **Reliability**: Built-in retry mechanisms and dead letter queues
4. **Integration**: Native integration with other AWS services
5. **Scalability**: Handles high-volume notification scenarios

**Alternatives Considered**:
- **Amazon SES**: Limited to email notifications only
- **Custom Notification System**: Would require additional development and maintenance
- **Third-party Services**: Adds external dependencies and potential security concerns

### Amazon EventBridge for Event Routing

**Selection Reasoning**: EventBridge was selected for event-driven communication because:

1. **Event Routing**: Sophisticated routing based on event content and patterns
2. **Schema Registry**: Manages event schemas for consistency across services
3. **Integration**: Connects with numerous AWS and third-party services
4. **Filtering**: Advanced filtering capabilities reduce unnecessary processing
5. **Replay**: Event replay capabilities for debugging and recovery scenarios

**Alternatives Considered**:
- **Amazon SQS**: Limited routing capabilities and requires more complex architecture
- **Amazon SNS**: Less sophisticated filtering and routing capabilities
- **Custom Event System**: Would require significant development effort and maintenance

## Monitoring and Observability

### Amazon CloudWatch for Monitoring

**Selection Reasoning**: CloudWatch was selected because:

1. **Integrated Monitoring**: Native integration with all AWS services used in the solution
2. **Custom Metrics**: Ability to track business-specific metrics and KPIs
3. **Alerting**: Configurable alarms for operational anomalies and threshold breaches
4. **Log Aggregation**: Centralized logging from all components with structured search
5. **Log Insights**: Powerful query capabilities for log analysis and troubleshooting

**Alternatives Considered**:
- **Third-party Monitoring Tools**: Would add unnecessary complexity, cost, and external dependencies
- **Custom Logging Solutions**: Would require additional development and maintenance overhead

## Performance Considerations

### Lambda Optimization Strategy
- Function memory allocation tuned based on processing requirements and cost optimization
- Code optimization to minimize execution time and reduce costs
- Connection pooling and reuse for database connections
- Warm start strategies implemented for critical functions

### DynamoDB Performance Tuning
- Appropriate provisioning of read/write capacity based on usage patterns
- Effective partition key design for even data distribution
- Global Secondary Indexes (GSI) for alternative access patterns
- DynamoDB Accelerator (DAX) consideration for high-read scenarios

### S3 Transfer Optimization
- Multipart uploads for large files to improve reliability and performance
- S3 Transfer Acceleration for remote uploads when needed
- Appropriate storage class selection based on access patterns
- CloudFront integration for frequently accessed content

## Scalability Analysis

### Horizontal Scalability
- Lambda automatically scales to handle increased processing load up to account limits
- DynamoDB scales horizontally with auto-scaling policies and on-demand pricing
- S3 provides virtually unlimited storage capacity with automatic scaling
- Step Functions can handle increased workflow complexity and volume

### Vertical Scalability
- Lambda memory allocation can be increased for more CPU power (up to 10GB)
- DynamoDB can be provisioned for higher throughput when needed
- Multi-region deployment for geographic scaling and disaster recovery

### Scaling Limitations
- Lambda concurrent execution limits (default 1000, can be increased)
- API rate limits for service interactions may require throttling
- DynamoDB partition throughput limitations require careful key design
- Step Functions execution history retention limits

## Operational Complexity Assessment

### Deployment Complexity
- Infrastructure as Code (CloudFormation) reduces deployment complexity and errors
- CI/CD pipelines automate deployment processes and reduce manual intervention
- Blue/green deployment strategy minimizes risk and downtime
- Automated testing ensures reliable updates and reduces regression risk

### Monitoring Complexity
- Centralized CloudWatch dashboards provide comprehensive operational visibility
- Automated alerts reduce manual monitoring overhead and improve response time
- Log insights and X-Ray tracing simplify troubleshooting and root cause analysis
- Standardized logging format across all components improves consistency

### Maintenance Overhead
- Serverless architecture minimizes infrastructure maintenance requirements
- Managed services reduce operational burden for database management, patching
- Automated testing and deployment reduce manual maintenance tasks
- Self-healing capabilities reduce manual intervention requirements

## Consistency Explanations

### Similar Component Mapping
- All file processing operations use Lambda for consistency in execution model
- All structured data storage uses DynamoDB for uniform access patterns and performance
- All workflow orchestration uses Step Functions for consistent management and monitoring
- All notifications use SNS for uniform delivery mechanisms

### Naming Conventions
- Consistent resource naming patterns across all AWS services
- Standardized environment variable naming for configuration management
- Uniform tagging strategy for all resources to support cost allocation and management
- Consistent IAM role and policy naming for security management

### Security Controls
- Consistent IAM role patterns across all services with least privilege principles
- Uniform encryption standards for all data storage (KMS encryption)
- Standardized VPC and security group configurations where applicable
- Consistent logging and monitoring patterns for security audit compliance

## Cost Optimization Strategies

### Service Selection for Cost
- Serverless services chosen to eliminate idle resource costs
- Pay-per-use pricing models align costs with actual business usage
- Managed services reduce operational overhead costs and staffing requirements
- Auto-scaling capabilities prevent over-provisioning and reduce waste

### Storage Optimization
- S3 lifecycle policies automatically transition data to cheaper storage classes
- DynamoDB on-demand pricing for variable workloads eliminates capacity planning
- CloudWatch log retention policies manage storage costs for operational logs
- Data compression and efficient serialization formats reduce storage costs

### Compute Optimization
- Lambda memory optimization balances performance and cost
- Step Functions reduce overall execution time through parallel processing
- Efficient algorithms and data structures minimize processing time and costs

## Risk Assessment and Mitigation

### Technical Risks
- **Lambda timeout limitations**: Mitigated through workflow design and data chunking
- **DynamoDB throttling**: Addressed through proper capacity planning and auto-scaling
- **S3 eventual consistency**: Handled through application design and retry logic
- **Service limits**: Monitored proactively with automated limit increase requests

### Operational Risks
- **Service outages**: Multi-region deployment and disaster recovery procedures
- **Data loss**: Comprehensive backup strategies and point-in-time recovery
- **Security breaches**: Defense-in-depth security model with multiple layers
- **Cost overruns**: Automated cost monitoring and alerting with budget controls

### Business Risks
- **Performance degradation**: Comprehensive monitoring and automated scaling
- **Data accuracy**: Validation and reconciliation processes at multiple points
- **Compliance violations**: Automated compliance checking and audit trails

## Future Extensibility

### Architecture Flexibility
- Microservices design enables independent scaling and deployment of components
- Event-driven architecture supports easy integration of new services and capabilities
- API-first approach facilitates future enhancements and third-party integrations
- Modular design allows for incremental improvements and feature additions

### Technology Evolution
- Serverless architecture adapts automatically to new AWS service capabilities
- Container support available through Lambda container images for complex dependencies
- Machine learning integration possible through AWS AI/ML services (SageMaker, Comprehend)
- Real-time processing capabilities through Kinesis and Lambda integration

### Business Growth
- Architecture scales automatically with business growth and increased data volumes
- Multi-tenant design supports expansion to multiple business units or customers
- International expansion supported through multi-region deployment capabilities
- Integration capabilities support merger and acquisition scenarios
```

Continue this pattern for ALL AWS services. Each file must be:
- Complete and deployable
- Include proper error handling
- Follow AWS best practices
- Include monitoring and logging
- Be production-ready

Focus on mainframe modernization patterns like:
- Batch processing with Step Functions
- Data transformation with Glue
- Legacy system integration
- Event-driven architectures
- Microservices decomposition"""
            
            request_body = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 131000,
                "temperature": 0.1,
                "top_p": 0.9,
                "system": system_prompt,
                "messages": [{"role": "user", "content": prompt}]
            }
            
            print(f"[BEDROCK] Starting streaming response for mainframe modernization analysis")
            
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
                                
                                if total_chars % 10000 == 0:
                                    print(f"[BEDROCK] Streamed {total_chars:,} characters, created {len(self.files_created)} files")
                                
                                yield text_chunk
                                
            print(f"[BEDROCK] Completed streaming {total_chars:,} total characters")
                                
        except Exception as e:
            print(f"[BEDROCK ERROR] {str(e)}")
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
            print(f"[SECTION] Started section: {new_section}")
            
            # Auto-create files for documentation sections if no explicit file header follows
            if new_section in self.documentation_sections:
                # Set a default filename for documentation sections
                if new_section == 'README':
                    self.current_file = 'README.md'
                elif new_section == 'REASONING':
                    self.current_file = 'reasoning.md'  # Use consistent naming
                elif new_section == 'ARCHITECTURE':
                    self.current_file = 'architecture.md'
                
                if self.current_file:
                    print(f"[FILE] Auto-created file: {self.current_file} for section {new_section}")
            
            return
        
        # Check for file headers
        new_file = self.detect_file(line_stripped)
        if new_file and self.current_section:
            # Save previous file if we have one
            if self.current_file and self.current_content:
                self.save_current_file()
            
            self.current_file = new_file
            self.current_content = []
            print(f"[FILE] Started file: {new_file} in section {self.current_section}")
            return
        
        # Add content to current file or section
        if self.current_section:
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
        
        # For documentation sections, only save when we hit another section
        if self.current_section in self.documentation_sections:
            # Only save when we detect a new section starting (not the current section)
            new_section = self.detect_section(line)
            if new_section and new_section != self.current_section:
                return True
            # Don't save documentation files based on length - accumulate all content
            return False
        
        # Check for code block endings for technical files
        if line == '```' and len(self.current_content) > 10:
            return True
        
        # Check for next file/section starting for technical files
        if (self.detect_file(line) or self.detect_section(line)) and len(self.current_content) > 5:
            return True
        
        # For very large technical files, save periodically to avoid memory issues
        if len(self.current_content) > 1000:
            return True
        
        return False

    def save_current_file(self):
        """Save the current file to S3"""
        if not self.current_file or not self.current_content:
            return
        
        # Clean and prepare content
        content = self.clean_file_content('\n'.join(self.current_content))
        
        if len(content.strip()) < 50:  # Skip tiny files
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
            print(f"[SAVE ERROR] Failed to save {self.current_file}: {str(e)}")
        
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
                "maxTokens": 131000,
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

def process_with_streaming_extraction(prompt: str, bucket_name: str, output_path: str) -> Dict[str, Any]:
    """
    Process the prompt using streaming file extraction
    """
    print("[STREAMING] Starting streaming file extraction analysis")
    
    # Create the streaming extractor
    extractor = StreamingFileExtractor(bucket_name, f"{output_path}/aws_artifacts")
    
    try:
        # Stream the response and process in real-time
        for chunk in extractor.stream_bedrock_response(prompt):
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
            'total_files_created': len(extractor.files_created),
            'files_by_section': files_by_section,
            'all_files': extractor.files_created
        }
        
    except Exception as e:
        return {'status': 'error', 'error': str(e)}

def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Enhanced Lambda function handler with streaming file extraction capabilities."""
    print("=== ENHANCED ANALYSIS LAMBDA HANDLER STARTED ===")
    
    try:
        # Extract parameters from the event
        job_id = event.get('job_id')
        bucket_name = event.get('bucket_name')
        full_prompt_key = event.get('full_prompt_key')
        output_path = event.get('output_path', f"mainframe-analysis/{job_id}")
        use_streaming = event.get('use_streaming', True)  # Default to streaming
        
        print(f"[JOB] ID: {job_id}, Bucket: {bucket_name}, Path: {output_path}")
        print(f"[CONFIG] Streaming extraction enabled: {use_streaming}")
        
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
        update_job_status(job_id, 'ANALYZING', "Starting enhanced analysis with streaming extraction")
        
        if use_streaming:
            # Use streaming file extraction
            print("[PROCESSING] Using streaming file extraction approach")
            update_job_status(job_id, 'STREAMING', "Processing with real-time file extraction")
            
            streaming_result = process_with_streaming_extraction(full_prompt, bucket_name, output_path)
            
            if streaming_result['status'] == 'error':
                update_job_status(job_id, 'ERROR', streaming_result['error'])
                return streaming_result
            
            # Create summary of extracted files
            uploaded_files = []
            for file_info in streaming_result['all_files']:
                uploaded_files.append({
                    "service_type": file_info['section'],
                    "filename": file_info['filename'],
                    "s3_location": file_info['s3_path'],
                    "size_bytes": file_info['size'],
                    "content_type": file_info['content_type']
                })
            
            # Update job status
            status_message = f"Successfully extracted {streaming_result['total_files_created']} individual files using streaming"
            update_job_status(job_id, 'COMPLETED', status_message)
            
            return {
                'status': 'success',
                'job_id': job_id,
                'bucket_name': bucket_name,
                'output_path': output_path,
                'files': uploaded_files,
                'streaming_extraction': True,
                'files_by_section': streaming_result['files_by_section'],
                'total_files_created': streaming_result['total_files_created']
            }
        
        else:
            # Fall back to original chunking approach
            print("[PROCESSING] Using traditional chunking approach")
            
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
                'streaming_extraction': False,
                'chunked_processing': use_chunking
            }
        
    except Exception as e:
        error_message = f"Error during enhanced analysis: {str(e)}"
        print(f"[ERROR] {error_message}")
        print(f"[ERROR] Traceback:\n{traceback.format_exc()}")
        
        if 'job_id' in event:
            update_job_status(event['job_id'], 'ERROR', error_message)
        
        return {'status': 'error', 'error': str(e)}
