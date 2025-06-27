import unittest
import json
import os
import sys
import boto3
import uuid
from unittest.mock import patch, MagicMock

# Add src directory to path for importing modules
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

# Import the module to test
from initial-lambda import lambda_function

class TestInitialLambda(unittest.TestCase):
    """Test cases for the initial_lambda module"""

    def setUp(self):
        """Set up test fixtures"""
        # Create mock environment variables
        os.environ['JOBS_TABLE_NAME'] = 'test-jobs-table'
        os.environ['STATE_MACHINE_ARN'] = 'arn:aws:states:us-east-1:123456789012:stateMachine:test-state-machine'
        
        # Sample event for testing
        self.event = {
            'bucket_name': 'test-bucket',
            's3_folder': 'test-folder'
        }
        
        # Sample Bedrock agent event for testing
        self.bedrock_event = {
            'actionGroup': 'GenerateTemplate',
            'apiPath': '/generate-template',
            'httpMethod': 'POST',
            'requestBody': {
                'content': {
                    'application/json': {
                        'properties': [
                            {
                                'name': 'bucket_name',
                                'value': 'test-bucket'
                            },
                            {
                                'name': 's3_folder',
                                'value': 'test-folder'
                            }
                        ]
                    }
                }
            }
        }
        
        # Mock context
        self.context = MagicMock()

    def tearDown(self):
        """Tear down test fixtures"""
        # Clean up environment variables
        if 'JOBS_TABLE_NAME' in os.environ:
            del os.environ['JOBS_TABLE_NAME']
        if 'STATE_MACHINE_ARN' in os.environ:
            del os.environ['STATE_MACHINE_ARN']

    @patch('initial-lambda.lambda_function.verify_s3_bucket_exists')
    @patch('initial-lambda.lambda_function.verify_s3_folder_exists')
    @patch('initial-lambda.lambda_function.create_job_record')
    @patch('initial-lambda.lambda_function.start_step_function')
    @patch('initial-lambda.lambda_function.uuid.uuid4')
    def test_lambda_handler_success(self, mock_uuid4, mock_start_step_function, 
                                   mock_create_job_record, mock_verify_s3_folder_exists, 
                                   mock_verify_s3_bucket_exists):
        """Test successful execution of lambda_handler"""
        # Configure mocks
        mock_uuid4.return_value = uuid.UUID('12345678-1234-5678-1234-567812345678')
        mock_verify_s3_bucket_exists.return_value = (True, "")
        mock_verify_s3_folder_exists.return_value = (True, "", 10)
        mock_create_job_record.return_value = True
        mock_start_step_function.return_value = (True, "arn:aws:states:us-east-1:123456789012:execution:test-state-machine:execution-id")
        
        # Call the function
        response = lambda_function.lambda_handler(self.event, self.context)
        
        # Verify the response
        self.assertEqual(response['statusCode'], 202)
        body = json.loads(response['body'])
        self.assertEqual(body['job_id'], '12345678-1234-5678-1234-567812345678')
        self.assertEqual(body['status'], 'PENDING')
        self.assertEqual(body['files_found'], 10)
        
        # Verify mock calls
        mock_verify_s3_bucket_exists.assert_called_once_with('test-bucket')
        mock_verify_s3_folder_exists.assert_called_once_with('test-bucket', 'test-folder')
        mock_create_job_record.assert_called_once_with('12345678-1234-5678-1234-567812345678', 'test-bucket', 'test-folder')
        mock_start_step_function.assert_called_once_with('12345678-1234-5678-1234-567812345678', 'test-bucket', 'test-folder')

    @patch('initial-lambda.lambda_function.verify_s3_bucket_exists')
    def test_lambda_handler_invalid_bucket(self, mock_verify_s3_bucket_exists):
        """Test lambda_handler with invalid bucket"""
        # Configure mock
        mock_verify_s3_bucket_exists.return_value = (False, "Error accessing S3 bucket")
        
        # Call the function
        response = lambda_function.lambda_handler(self.event, self.context)
        
        # Verify the response
        self.assertEqual(response['statusCode'], 404)
        body = json.loads(response['body'])
        self.assertEqual(body['message'], "Error accessing S3 bucket")
        
        # Verify mock calls
        mock_verify_s3_bucket_exists.assert_called_once_with('test-bucket')

    @patch('initial-lambda.lambda_function.verify_s3_bucket_exists')
    @patch('initial-lambda.lambda_function.verify_s3_folder_exists')
    def test_lambda_handler_invalid_folder(self, mock_verify_s3_folder_exists, mock_verify_s3_bucket_exists):
        """Test lambda_handler with invalid folder"""
        # Configure mocks
        mock_verify_s3_bucket_exists.return_value = (True, "")
        mock_verify_s3_folder_exists.return_value = (False, "S3 folder is empty", 0)
        
        # Call the function
        response = lambda_function.lambda_handler(self.event, self.context)
        
        # Verify the response
        self.assertEqual(response['statusCode'], 404)
        body = json.loads(response['body'])
        self.assertEqual(body['message'], "S3 folder is empty")
        
        # Verify mock calls
        mock_verify_s3_bucket_exists.assert_called_once_with('test-bucket')
        mock_verify_s3_folder_exists.assert_called_once_with('test-bucket', 'test-folder')

    def test_lambda_handler_missing_parameters(self):
        """Test lambda_handler with missing parameters"""
        # Call the function with missing bucket_name
        response = lambda_function.lambda_handler({'s3_folder': 'test-folder'}, self.context)
        
        # Verify the response
        self.assertEqual(response['statusCode'], 400)
        body = json.loads(response['body'])
        self.assertEqual(body['message'], "Missing required parameter: bucket_name")

    @patch('initial-lambda.lambda_function.verify_s3_bucket_exists')
    @patch('initial-lambda.lambda_function.verify_s3_folder_exists')
    @patch('initial-lambda.lambda_function.create_job_record')
    @patch('initial-lambda.lambda_function.start_step_function')
    @patch('initial-lambda.lambda_function.uuid.uuid4')
    def test_lambda_handler_bedrock_agent(self, mock_uuid4, mock_start_step_function, 
                                         mock_create_job_record, mock_verify_s3_folder_exists, 
                                         mock_verify_s3_bucket_exists):
        """Test lambda_handler with Bedrock agent event"""
        # Configure mocks
        mock_uuid4.return_value = uuid.UUID('12345678-1234-5678-1234-567812345678')
        mock_verify_s3_bucket_exists.return_value = (True, "")
        mock_verify_s3_folder_exists.return_value = (True, "", 10)
        mock_create_job_record.return_value = True
        mock_start_step_function.return_value = (True, "arn:aws:states:us-east-1:123456789012:execution:test-state-machine:execution-id")
        
        # Call the function
        response = lambda_function.lambda_handler(self.bedrock_event, self.context)
        
        # Verify the response
        self.assertEqual(response['messageVersion'], '1.0')
        self.assertEqual(response['response']['httpStatusCode'], 202)
        
        # Verify mock calls
        mock_verify_s3_bucket_exists.assert_called_once_with('test-bucket')
        mock_verify_s3_folder_exists.assert_called_once_with('test-bucket', 'test-folder')
        mock_create_job_record.assert_called_once_with('12345678-1234-5678-1234-567812345678', 'test-bucket', 'test-folder')
        mock_start_step_function.assert_called_once_with('12345678-1234-5678-1234-567812345678', 'test-bucket', 'test-folder')

    def test_validate_input_parameters(self):
        """Test validate_input_parameters function"""
        # Test valid parameters
        is_valid, error_message = lambda_function.validate_input_parameters({
            'bucket_name': 'valid-bucket-name',
            's3_folder': 'valid/folder/path'
        })
        self.assertTrue(is_valid)
        self.assertEqual(error_message, "")
        
        # Test missing bucket_name
        is_valid, error_message = lambda_function.validate_input_parameters({
            's3_folder': 'valid/folder/path'
        })
        self.assertFalse(is_valid)
        self.assertEqual(error_message, "Missing required parameter: bucket_name")
        
        # Test invalid bucket name
        is_valid, error_message = lambda_function.validate_input_parameters({
            'bucket_name': 'Invalid_Bucket_Name',
            's3_folder': 'valid/folder/path'
        })
        self.assertFalse(is_valid)
        self.assertEqual(error_message, "Invalid S3 bucket name format")
        
        # Test missing s3_folder
        is_valid, error_message = lambda_function.validate_input_parameters({
            'bucket_name': 'valid-bucket-name'
        })
        self.assertFalse(is_valid)
        self.assertEqual(error_message, "Missing required parameter: s3_folder")
        
        # Test invalid folder path
        is_valid, error_message = lambda_function.validate_input_parameters({
            'bucket_name': 'valid-bucket-name',
            's3_folder': '/invalid/folder/path'
        })
        self.assertFalse(is_valid)
        self.assertEqual(error_message, "S3 folder path should not start with '/'")

if __name__ == '__main__':
    unittest.main()
