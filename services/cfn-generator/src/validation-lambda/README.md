# CloudFormation Template Validation Lambda

This Lambda function validates CloudFormation templates and automatically attempts to fix validation errors using Amazon Bedrock LLM.

## Features

- **Syntax Validation**: Validates template syntax using CloudFormation's `validate_template` API
- **Deployment Validation**: Creates a CloudFormation change set to validate if the template can be deployed
- **Automatic Error Fixing**: Uses Amazon Bedrock LLM to fix validation errors
- **Retry Logic**: Attempts to fix templates up to a configurable number of times
- **Job Status Tracking**: Updates job status in DynamoDB throughout the validation process

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `JOBS_TABLE_NAME` | DynamoDB table for job tracking | `CFNGeneratorJobs` |
| `BEDROCK_MODEL_ID` | Amazon Bedrock model ID | `anthropic.claude-3-sonnet-20240229-v1:0` |
| `BEDROCK_CONNECT_TIMEOUT` | Connection timeout for Bedrock API calls | `60` (seconds) |
| `BEDROCK_READ_TIMEOUT` | Read timeout for Bedrock API calls | `300` (seconds) |

## Input Event Structure

```json
{
  "job_id": "12345678-abcd-1234-efgh-123456789012",
  "s3_location": "s3://bucket/path/to/template.yaml",
  "perform_changeset_validation": true,
  "max_fix_attempts": 5
}
```

| Parameter | Type | Description | Required | Default |
|-----------|------|-------------|----------|---------|
| `job_id` | String | Unique job identifier | Yes | - |
| `s3_location` | String | S3 location of the template | Yes | - |
| `perform_changeset_validation` | Boolean | Whether to perform change set validation | No | `true` |
| `max_fix_attempts` | Number | Maximum number of fix attempts | No | `5` |
| `fix_attempt` | Number | Current fix attempt (used internally) | No | `0` |

## Output Structure

```json
{
  "job_id": "12345678-abcd-1234-efgh-123456789012",
  "validation_status": "PASSED",
  "validation_message": "Template validation successful",
  "s3_location": "s3://bucket/path/to/template.yaml",
  "fix_attempts": 2
}
```

| Field | Type | Description |
|-------|------|-------------|
| `job_id` | String | Unique job identifier |
| `validation_status` | String | `PASSED` or `FAILED` |
| `validation_message` | String | Success message (if passed) |
| `validation_errors` | String | Error message (if failed) |
| `s3_location` | String | S3 location of the template |
| `fix_attempts` | Number | Number of fix attempts made |

## Job Status Values

| Status | Description |
|--------|-------------|
| `VALIDATING` | Template validation in progress |
| `FIXING` | Attempting to fix template errors |
| `VALIDATED` | Template validation successful |
| `VALIDATION_FAILED` | Template validation failed |

## Workflow

1. Receive validation request with job ID and S3 location
2. Update job status to `VALIDATING`
3. Retrieve template from S3
4. Perform syntax validation
5. If syntax validation fails:
   - Update job status to `FIXING`
   - Call Bedrock LLM to fix the template
   - Upload fixed template to S3
   - Retry validation (up to max attempts)
6. If syntax validation passes, perform change set validation
7. If change set validation fails:
   - Update job status to `FIXING`
   - Call Bedrock LLM to fix the template
   - Upload fixed template to S3
   - Retry validation (up to max attempts)
8. If all validations pass, update job status to `VALIDATED`
9. Return validation result

## Error Handling

- If validation fails after maximum fix attempts, job status is set to `VALIDATION_FAILED`
- If an unexpected error occurs, job status is set to `VALIDATION_FAILED` and the error is logged
- All errors are logged with detailed information for troubleshooting
