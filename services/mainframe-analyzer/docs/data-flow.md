# Data Flow and Processing

## Data Flow

1. **Input**: User submits a job with S3 bucket and folder path containing mainframe documentation
2. **Document Discovery**: Initial Lambda lists files and creates a job record
3. **Text Extraction**: Process File Lambda extracts text from each document in parallel
4. **Aggregation**: Aggregate Lambda combines all extracted text into a single document
5. **Analysis**: Analysis Lambda sends the aggregated content to Bedrock for AI-powered analysis
6. **Results**: Analysis results are saved to S3, organized by AWS service type
7. **Status Tracking**: Status Lambda provides job status and progress information throughout the process

## Key Features

- **Parallel Processing**: Files are processed in parallel for efficiency
- **Error Handling**: Robust error handling at each stage
- **Progress Tracking**: Job progress is tracked in DynamoDB
- **Adaptive Timeouts**: Timeout calculations based on input size
- **Service-Specific Output**: Analysis results are organized by AWS service type

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

## Processing Stages

### 1. Initial Processing

- User submits job with S3 bucket and folder path
- Initial Lambda validates input parameters
- Lists files in the specified S3 location
- Creates a job record in DynamoDB
- Starts the Step Functions workflow

### 2. File Processing

- Step Functions Map state processes files in parallel
- Process File Lambda extracts text from each file
- Supports PDF, DOCX, and TXT formats
- Extracted text is stored in S3
- Job progress is updated in DynamoDB

### 3. Content Aggregation

- Aggregate Lambda combines extracted text from all files
- Applies size limits to prevent timeouts
- Prepares the full prompt for analysis
- Updates job status in DynamoDB

### 4. AI Analysis

- Analysis Lambda sends the aggregated content to Amazon Bedrock
- Uses adaptive timeouts based on input size
- Implements automatic retry with reduced input on timeouts
- Parses the response by AWS service type
- Saves results to S3
- Updates job status to completed

### 5. Status Reporting

- Status Lambda provides job status information
- Calculates progress percentage
- Retrieves execution details from Step Functions
- Lists output files from S3
- Provides estimated completion time for in-progress jobs
