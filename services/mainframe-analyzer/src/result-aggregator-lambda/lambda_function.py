import json
import boto3
import os
import time
import traceback
from typing import Dict, Any, List

# Initialize clients
s3_client = boto3.client('s3')
dynamodb = boto3.resource('dynamodb')

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

def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Aggregates results from all chunks and generates individual AWS artifacts
    """
    print("=== RESULT AGGREGATOR LAMBDA HANDLER STARTED ===")
    
    try:
        # Extract parameters from the event
        job_id = event.get('job_id')
        bucket_name = event.get('bucket_name')
        output_path = event.get('output_path')
        chunk_results = event.get('chunk_results', [])
        
        print(f"[JOB] ID: {job_id}, Bucket: {bucket_name}, Path: {output_path}")
        print(f"[AGGREGATION] Processing {len(chunk_results)} chunk results")
        
        # Validate required parameters
        if not all([job_id, bucket_name, output_path]):
            error_message = "Missing required parameters"
            update_job_status(job_id, 'ERROR', error_message)
            return {'status': 'error', 'error': error_message}
        
        # Update job status
        update_job_status(job_id, 'AGGREGATING', f"Combining results from {len(chunk_results)} chunks")
        
        # Initialize aggregated results
        aggregated = {}
        
        # Process each chunk result
        for result in chunk_results:
            if result.get('status') == 'error':
                print(f"[AGGREGATION] Skipping failed chunk {result.get('chunk_index')}")
                continue
                
            # Get the result from S3
            result_key = result.get('result_key')
            if not result_key:
                print(f"[AGGREGATION] Missing result_key in chunk result: {result}")
                continue
                
            try:
                response = s3_client.get_object(Bucket=bucket_name, Key=result_key)
                chunk_data = json.loads(response['Body'].read().decode('utf-8'))
                
                chunk_index = result.get('chunk_index')
                service_contents = chunk_data
                
                if isinstance(service_contents, dict):
                    print(f"[AGGREGATION] Processing chunk {chunk_index} with {len(service_contents)} service types")
                    
                    # Merge into aggregated results
                    for service_type, content in service_contents.items():
                        if service_type not in aggregated:
                            aggregated[service_type] = content
                            print(f"[AGGREGATION] Added new service type: {service_type}")
                        else:
                            aggregated[service_type] += f"\n\n### Additional Analysis from Chunk {chunk_index}\n\n{content}"
                            print(f"[AGGREGATION] Appended content to existing service type: {service_type}")
                else:
                    print(f"[AGGREGATION] Unexpected format for chunk data: {type(service_contents)}")
            except Exception as e:
                print(f"[ERROR] Failed to process chunk result {result_key}: {str(e)}")
                continue
        
        # Create aws_artifacts subfolder
        aws_artifacts_path = f"{output_path}/aws_artifacts"
        
        # Save each service content to a separate file
        uploaded_files = []
        
        for service_type, content in aggregated.items():
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
            
            print(f"[S3] Uploading {service_type} content ({len(content):,} chars) to {service_key}")
            
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
        
        # Save consolidated analysis
        consolidated_key = f"{output_path}/analysis/consolidated-analysis.json"
        s3_client.put_object(
            Bucket=bucket_name,
            Key=consolidated_key,
            Body=json.dumps(aggregated, indent=2)
        )
        
        # Update job status
        update_job_status(job_id, 'COMPLETED', f"Successfully analyzed using chunking and created {len(uploaded_files)} service-specific files")
        
        return {
            'status': 'success',
            'job_id': job_id,
            'bucket_name': bucket_name,
            'output_path': output_path,
            'files': uploaded_files,
            'chunked_processing': True
        }
        
    except Exception as e:
        error_message = f"Error aggregating results: {str(e)}"
        print(f"[ERROR] {error_message}")
        print(traceback.format_exc())
        
        if 'job_id' in event:
            update_job_status(event['job_id'], 'ERROR', error_message)
        
        return {'status': 'error', 'error': str(e)}
