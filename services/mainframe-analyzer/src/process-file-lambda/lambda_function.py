import json
import boto3
import os
import time
import io
import traceback
from typing import Dict, Any

# Initialize clients
s3_client = boto3.client('s3')
dynamodb = boto3.resource('dynamodb')

def extract_text_from_pdf(file_obj: io.BytesIO) -> str:
    """
    Extracts text from a PDF file.
    
    Args:
        file_obj (io.BytesIO): File object containing the PDF data
        
    Returns:
        str: Extracted text from the PDF
    """
    try:
        import PyPDF2
        pdf_reader = PyPDF2.PdfReader(file_obj)
        text = ""
        
        for page_num in range(len(pdf_reader.pages)):
            page = pdf_reader.pages[page_num]
            text += page.extract_text() + "\n\n"
            
        return text
    except Exception as e:
        print(f"Error extracting text from PDF: {str(e)}")
        return f"Error extracting text from PDF: {str(e)}"

def extract_text_from_docx(file_obj: io.BytesIO) -> str:
    """
    Extracts text from a DOCX file.
    
    Args:
        file_obj (io.BytesIO): File object containing the DOCX data
        
    Returns:
        str: Extracted text from the DOCX
    """
    try:
        import docx
        doc = docx.Document(file_obj)
        text = ""
        
        for paragraph in doc.paragraphs:
            text += paragraph.text + "\n"
            
        return text
    except Exception as e:
        print(f"Error extracting text from DOCX: {str(e)}")
        return f"Error extracting text from DOCX: {str(e)}"

def extract_text_from_txt(file_obj: io.BytesIO) -> str:
    """
    Extracts text from a TXT file.
    
    Args:
        file_obj (io.BytesIO): File object containing the TXT data
        
    Returns:
        str: Extracted text from the TXT file
    """
    try:
        return file_obj.read().decode('utf-8')
    except UnicodeDecodeError:
        try:
            # Try with a different encoding if utf-8 fails
            file_obj.seek(0)
            return file_obj.read().decode('latin-1')
        except Exception as e:
            print(f"Error extracting text from TXT: {str(e)}")
            return f"Error extracting text from TXT: {str(e)}"

def extract_text_from_file(bucket_name: str, file_key: str) -> str:
    """
    Extracts text from a file in S3 based on its extension.
    
    Args:
        bucket_name (str): S3 bucket name
        file_key (str): Key of the file in S3
        
    Returns:
        str: Extracted text from the file
    """
    try:
        # Get the file from S3
        response = s3_client.get_object(Bucket=bucket_name, Key=file_key)
        file_content = response['Body'].read()
        file_obj = io.BytesIO(file_content)
        
        # Extract text based on file extension
        file_extension = os.path.splitext(file_key)[1].lower()
        
        if file_extension == '.pdf':
            return extract_text_from_pdf(file_obj)
        elif file_extension == '.docx':
            return extract_text_from_docx(file_obj)
        elif file_extension == '.txt':
            return extract_text_from_txt(file_obj)
        else:
            return f"Unsupported file extension: {file_extension}"
    
    except Exception as e:
        print(f"Error extracting text from file {file_key}: {str(e)}")
        return f"Error extracting text from file: {str(e)}"

def update_job_progress(job_id: str, increment: int = 1) -> None:
    """
    Updates the job progress in DynamoDB.
    
    Args:
        job_id (str): The job ID
        increment (int): The number of files processed
    """
    # Get the DynamoDB table name from environment variable or use default
    table_name = os.environ.get('JOBS_TABLE_NAME', 'MainframeAnalyzerJobs')
    
    try:
        # Get the table
        table = dynamodb.Table(table_name)
        
        # Update the job record
        table.update_item(
            Key={'job_id': job_id},
            UpdateExpression='SET processed_files = processed_files + :inc, updated_at = :time',
            ExpressionAttributeValues={
                ':inc': increment,
                ':time': int(time.time())
            }
        )
    except Exception as e:
        print(f"Error updating job progress: {str(e)}")
        # Continue processing even if update fails

def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda function handler that processes a single file.
    
    Expected event structure:
    {
        "job_id": "12345",
        "bucket_name": "my-bucket",
        "file_key": "path/to/file.pdf",
        "output_path": "mainframe-analysis/12345"
    }
    """
    print("Process File Lambda handler started")
    print(f"Processing file: {event.get('file_key')}")
    
    try:
        # Extract parameters from the event
        job_id = event.get('job_id')
        bucket_name = event.get('bucket_name')
        file_key = event.get('file_key')
        output_path = event.get('output_path', f"mainframe-analysis/{job_id}")
        
        # Validate required parameters
        if not all([job_id, bucket_name, file_key]):
            error_message = "Missing required parameters: job_id, bucket_name, or file_key"
            print(error_message)
            return {
                'status': 'error',
                'error': error_message
            }
        
        # Extract text from the file
        text = extract_text_from_file(bucket_name, file_key)
        
        # Generate a safe filename for the extracted text
        safe_filename = file_key.replace('/', '_')
        extracted_text_key = f"{output_path}/extracted/{safe_filename}.txt"
        
        # Upload the extracted text to S3
        s3_client.put_object(
            Bucket=bucket_name,
            Key=extracted_text_key,
            Body=text.encode('utf-8')
        )
        
        # Update the job progress
        update_job_progress(job_id)
        
        # Return the result
        return {
            'status': 'success',
            'job_id': job_id,
            'file_key': file_key,
            #'extracted_text_key': extracted_text_key,
            'output_key': extracted_text_key,
            'size_bytes': len(text.encode('utf-8'))
        }
        
    except Exception as e:
        print(f"Error processing file: {str(e)}")
        print(f"Traceback:\n{traceback.format_exc()}")
        return {
            'status': 'error',
            'error': str(e),
            'file_key': event.get('file_key')
        }
