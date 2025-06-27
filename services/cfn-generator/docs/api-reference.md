# API Reference

This document provides detailed information about the APIs and interfaces available in the Asynchronous CloudFormation Generator.

## Lambda Functions

### Initial Lambda

The Initial Lambda function initiates the CloudFormation template generation process.

**Function Name**: `CFNGenerator-Initial-<env>`

**Input Parameters**:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| bucket_name | string | Yes | S3 bucket containing resource configurations |
| s3_folder | string | Yes | Folder path within the S3 bucket |

**Response**:

| Field | Type | Description |
|-------|------|-------------|
| job_id | string | Unique identifier for the generation job |
| status | string | Initial status of the job (PENDING) |
| message | string | Description of the job status |
| files_found | number | Number of files found in the S3 folder |

**Example Request**:
```json
{
  "bucket_name": "my-resource-configs",
  "s3_folder": "resources/lambda"
}
```

**Example Response**:
```json
{
  "job_id": "12345678-abcd-1234-efgh-123456789012",
  "status": "PENDING",
  "message": "CloudFormation template generation started. Use the job_id to check status.",
  "files_found": 10
}
```

### Status Lambda

The Status Lambda function retrieves the status of a template generation job.

**Function Name**: `CFNGenerator-Status-<env>`

**Input Parameters**:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| job_id | string | Yes | Unique identifier for the generation job |

**Response**:

| Field | Type | Description |
|-------|------|-------------|
| job_id | string | Unique identifier for the generation job |
| status | string | Current status of the job (PENDING, PROCESSING, COMPLETED, ERROR) |
| message | string | Description of the job status |
| created_at | number | Unix timestamp when the job was created |
| updated_at | number | Unix timestamp when the job was last updated |
| s3_location | string | S3 location of the generated template (if completed) |
| zip_location | string | S3 location of the zipped template (if completed) |
| config_zip_location | string | S3 location of the zipped configuration files (if completed) |
| error | string | Error message (if status is ERROR) |

**Example Request**:
```json
{
  "job_id": "12345678-abcd-1234-efgh-123456789012"
}
```

**Example Response**:
```json
{
  "job_id": "12345678-abcd-1234-efgh-123456789012",
  "status": "COMPLETED",
  "message": "CloudFormation template generation completed successfully",
  "created_at": 1621234567,
  "updated_at": 1621234789,
  "s3_location": "s3://my-bucket/IaC/cloudformation_template_1621234789.yaml",
  "zip_location": "s3://my-bucket/Archive/cfn_template_1621234789.zip",
  "config_zip_location": "s3://my-bucket/Archive/config_files_1621234789.zip"
}
```

### Generator Lambda

The Generator Lambda function processes resource configurations and generates CloudFormation templates.

**Function Name**: `CFNGenerator-Generator-<env>`

**Input Parameters**:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| job_id | string | Yes | Unique identifier for the generation job |
| bucket_name | string | Yes | S3 bucket containing resource configurations |
| s3_folder | string | Yes | Folder path within the S3 bucket |

**Response**:

| Field | Type | Description |
|-------|------|-------------|
| job_id | string | Unique identifier for the generation job |
| s3_location | string | S3 location of the generated template |
| zip_location | string | S3 location of the zipped template |
| config_zip_location | string | S3 location of the zipped configuration files |

**Example Request**:
```json
{
  "job_id": "12345678-abcd-1234-efgh-123456789012",
  "bucket_name": "my-resource-configs",
  "s3_folder": "resources/lambda"
}
```

**Example Response**:
```json
{
  "job_id": "12345678-abcd-1234-efgh-123456789012",
  "s3_location": "s3://my-bucket/IaC/cloudformation_template_1621234789.yaml",
  "zip_location": "s3://my-bucket/Archive/cfn_template_1621234789.zip",
  "config_zip_location": "s3://my-bucket/Archive/config_files_1621234789.zip"
}
```

### Completion Lambda

The Completion Lambda function finalizes the template generation process and updates the job status.

**Function Name**: `CFNGenerator-Completion-<env>`

**Input Parameters**:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| job_id | string | Yes | Unique identifier for the generation job |
| s3_location | string | Yes | S3 location of the generated template |
| zip_location | string | Yes | S3 location of the zipped template |
| config_zip_location | string | Yes | S3 location of the zipped configuration files |

**Response**:

| Field | Type | Description |
|-------|------|-------------|
| job_id | string | Unique identifier for the generation job |
| status | string | Final status of the job (COMPLETED) |
| message | string | Description of the job status |
| s3_location | string | S3 location of the generated template |
| zip_location | string | S3 location of the zipped template |
| config_zip_location | string | S3 location of the zipped configuration files |

**Example Request**:
```json
{
  "job_id": "12345678-abcd-1234-efgh-123456789012",
  "s3_location": "s3://my-bucket/IaC/cloudformation_template_1621234789.yaml",
  "zip_location": "s3://my-bucket/Archive/cfn_template_1621234789.zip",
  "config_zip_location": "s3://my-bucket/Archive/config_files_1621234789.zip"
}
```

**Example Response**:
```json
{
  "job_id": "12345678-abcd-1234-efgh-123456789012",
  "status": "COMPLETED",
  "message": "CloudFormation template generation completed successfully",
  "s3_location": "s3://my-bucket/IaC/cloudformation_template_1621234789.yaml",
  "zip_location": "s3://my-bucket/Archive/cfn_template_1621234789.zip",
  "config_zip_location": "s3://my-bucket/Archive/config_files_1621234789.zip"
}
```

## Bedrock Agent Action Groups

### GenerateTemplate Action Group

The GenerateTemplate action group initiates the CloudFormation template generation process.

**Action Group Name**: `GenerateTemplate`

**API Path**: `/generate-template`

**HTTP Method**: `POST`

**Request Body**:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| bucket_name | string | Yes | S3 bucket containing resource configurations |
| s3_folder | string | Yes | Folder path within the S3 bucket |

**Response Body**:

| Field | Type | Description |
|-------|------|-------------|
| job_id | string | Unique identifier for the generation job |
| status | string | Initial status of the job (PENDING) |
| message | string | Description of the job status |
| files_found | number | Number of files found in the S3 folder |

### CheckStatus Action Group

The CheckStatus action group retrieves the status of a template generation job.

**Action Group Name**: `CheckStatus`

**API Path**: `/check-status`

**HTTP Method**: `POST`

**Request Body**:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| job_id | string | Yes | Unique identifier for the generation job |

**Response Body**:

| Field | Type | Description |
|-------|------|-------------|
| job_id | string | Unique identifier for the generation job |
| status | string | Current status of the job (PENDING, PROCESSING, COMPLETED, ERROR) |
| message | string | Description of the job status |
| created_at | number | Unix timestamp when the job was created |
| updated_at | number | Unix timestamp when the job was last updated |
| s3_location | string | S3 location of the generated template (if completed) |
| zip_location | string | S3 location of the zipped template (if completed) |
| config_zip_location | string | S3 location of the zipped configuration files (if completed) |
| error | string | Error message (if status is ERROR) |

## DynamoDB Schema

### JobsTable

The JobsTable stores information about template generation jobs.

**Table Name**: `CFNGeneratorJobs-<env>`

**Primary Key**: `job_id` (string)

**Attributes**:

| Attribute | Type | Description |
|-----------|------|-------------|
| job_id | string | Unique identifier for the generation job (Primary Key) |
| bucket_name | string | S3 bucket containing resource configurations |
| s3_folder | string | Folder path within the S3 bucket |
| status | string | Current status of the job (PENDING, PROCESSING, COMPLETED, ERROR) |
| message | string | Description of the job status |
| created_at | number | Unix timestamp when the job was created |
| updated_at | number | Unix timestamp when the job was last updated |
| s3_location | string | S3 location of the generated template (if completed) |
| zip_location | string | S3 location of the zipped template (if completed) |
| config_zip_location | string | S3 location of the zipped configuration files (if completed) |
| error | string | Error message (if status is ERROR) |
| ttl | number | Time-to-live for the record (30 days from creation) |

## S3 Bucket Structure

The S3 bucket stores resource configurations, generated templates, and archives.

**Bucket Name**: `cfn-generator-<env>-<account-id>-<region>`

**Folder Structure**:

- `/lambda/` - Lambda function deployment packages
- `/IaC/` - Generated CloudFormation templates
- `/Archive/` - Archived templates and configuration files
  - `cfn_template_<timestamp>.zip` - Zipped CloudFormation templates
  - `config_files_<timestamp>.zip` - Zipped configuration files
