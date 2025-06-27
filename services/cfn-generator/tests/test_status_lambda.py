import unittest
import json
import os
import sys
import boto3
from unittest.mock import patch, MagicMock

# Add src directory to path for importing modules
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

# Import the module to test
from status-lambda import lambda_function

class TestStatusLambda(unittest.TestCase):
    """Test cases for the status_lambda module"""

    def setUp(self):
        """Set up test fixtures"""
        # Create mock environment variables
        os.environ['JOBS_TABLE_NAME'] = 'test-jobs-table'
        os.environ['STATE_MACHINE_ARN'] = 'arn:aws:states:us-east-1:123456789012:stateMachine:test-state-machine'
        
        # Sample event for testing
        self.event = {
            'job_id': '12345678-1234-5678-1234-567812345678'
        }
        
        # Sample Bedrock agent event for testing
        self.bedrock_event = {
            'actionGroup': 'CheckStatus',
            'apiPath': '/check-status',
            'httpMethod': 'POST',
            'requestBody': {
                'content': {
                    'application/json': {
                        'properties': [
                            {
                                'name': 'job_id',
                                'value': '12345678-1234-5678-1234-567812345678'
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

    @patch('status-lambda.lambda_function.get_job_status')
    @patch('status-lambda.lambda_function.get_step_function_execution_status')
    def test_lambda_handler_success(self, mock_get_step_function_execution_status, mock_get_job_status):
        """Test successful execution of lambda_handler"""
        # Configure mocks
        mock_get_job_status.return_value = (True, {
            'job_id': '12345678-1234-5678-1234-567812345678',
            'status': 'COMPLETED',
            'created_at': 1621234567,
            'updated_at': 1621234789,
            's3_location': 's3://test-bucket/IaC/cloudformation_template_1621234789.yaml',
            'zip_location': 's3://test-bucket/Archive/cfn_template_1621234789.zip',
            'config_zip_location': 's3://test-bucket/Archive/config_files_1621234789.zip',
            'message': 'CloudFormation template generation completed successfully'
        })
        mock_get_step_function_execution_status.return_value = (True, {
            'status': 'SUCCEEDED',
            'startDate': '2023-05-18T12:00:00Z',
            'stopDate': '2023-05-18T12:05:00Z'
        })
        
        # Call the function
        response = lambda_function.lambda_handler(self.event, self.context)
        
        # Verify the response
        self.assertEqual(response['statusCode'], 200)
        body = json.loads(response['body'])
        self.assertEqual(body['job_id'], '12345678-1234-5678-1234-567812345678')
        self.assertEqual(body['status'], 'COMPLETED')
        self.assertEqual(body['s3_location'], 's3://test-bucket/IaC/cloudformation_template_1621234789.yaml')
        
        # Verify mock calls
        mock_get_job_status.assert_called_once_with('12345678-1234-5678-1234-567812345678')
        mock_get_step_function_execution_status.assert_called_once_with('12345678-1234-5678-1234-567812345678')

    @patch('status-lambda.lambda_function.get_job_status')
    def test_lambda_handler_job_not_found(self, mock_get_job_status):
        """Test lambda_handler with job not found"""
        # Configure mock
        mock_get_job_status.return_value = (False, "Job not found: 12345678-1234-5678-1234-567812345678")
        
        # Call the function
        response = lambda_function.lambda_handler(self.event, self.context)
        
        # Verify the response
        self.assertEqual(response['statusCode'], 404)
        body = json.loads(response['body'])
        self.assertEqual(body['message'], "Job not found: 12345678-1234-5678-1234-567812345678")
        
        # Verify mock calls
        mock_get_job_status.assert_called_once_with('12345678-1234-5678-1234-567812345678')

    def test_lambda_handler_missing_job_id(self):
        """Test lambda_handler with missing job_id"""
        # Call the function with missing job_id
        response = lambda_function.lambda_handler({}, self.context)
        
        # Verify the response
        self.assertEqual(response['statusCode'], 400)
        body = json.loads(response['body'])
        self.assertEqual(body['message'], "Missing required parameter: job_id")

    @patch('status-lambda.lambda_function.get_job_status')
    @patch('status-lambda.lambda_function.get_step_function_execution_status')
    def test_lambda_handler_bedrock_agent(self, mock_get_step_function_execution_status, mock_get_job_status):
        """Test lambda_handler with Bedrock agent event"""
        # Configure mocks
        mock_get_job_status.return_value = (True, {
            'job_id': '12345678-1234-5678-1234-567812345678',
            'status': 'COMPLETED',
            'created_at': 1621234567,
            'updated_at': 1621234789,
            's3_location': 's3://test-bucket/IaC/cloudformation_template_1621234789.yaml',
            'zip_location': 's3://test-bucket/Archive/cfn_template_1621234789.zip',
            'config_zip_location': 's3://test-bucket/Archive/config_files_1621234789.zip',
            'message': 'CloudFormation template generation completed successfully'
        })
        mock_get_step_function_execution_status.return_value = (True, {
            'status': 'SUCCEEDED',
            'startDate': '2023-05-18T12:00:00Z',
            'stopDate': '2023-05-18T12:05:00Z'
        })
        
        # Call the function
        response = lambda_function.lambda_handler(self.bedrock_event, self.context)
        
        # Verify the response
        self.assertEqual(response['messageVersion'], '1.0')
        self.assertEqual(response['response']['httpStatusCode'], 200)
        
        # Verify mock calls
        mock_get_job_status.assert_called_once_with('12345678-1234-5678-1234-567812345678')
        mock_get_step_function_execution_status.assert_called_once_with('12345678-1234-5678-1234-567812345678')

if __name__ == '__main__':
    unittest.main()
