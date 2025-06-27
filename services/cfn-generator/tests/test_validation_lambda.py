import unittest
import json
import os
import sys
import boto3
from unittest.mock import patch, MagicMock

# Add src directory to path for importing modules
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

# Import the module to test
from validation-lambda import lambda_function

class TestValidationLambda(unittest.TestCase):
    """Test cases for the validation lambda function"""

    def setUp(self):
        """Set up test fixtures"""
        # Create mock environment variables
        os.environ['JOBS_TABLE_NAME'] = 'test-jobs-table'
        
        # Sample event for testing
        self.event = {
            'job_id': '12345678-1234-5678-1234-567812345678',
            's3_location': 's3://test-bucket/IaC/cloudformation_template_1621234789.yaml',
            'perform_changeset_validation': True
        }
        
        # Mock context
        self.context = MagicMock()

    def tearDown(self):
        """Tear down test fixtures"""
        # Clean up environment variables
        if 'JOBS_TABLE_NAME' in os.environ:
            del os.environ['JOBS_TABLE_NAME']

    @patch('validation-lambda.lambda_function.update_job_status')
    @patch('validation-lambda.lambda_function.get_template_from_s3')
    @patch('validation-lambda.lambda_function.validate_template_syntax')
    @patch('validation-lambda.lambda_function.extract_parameters_from_template')
    @patch('validation-lambda.lambda_function.validate_with_changeset')
    def test_lambda_handler_success(self, mock_validate_with_changeset, mock_extract_parameters, 
                                   mock_validate_template_syntax, mock_get_template_from_s3, 
                                   mock_update_job_status):
        """Test successful execution of lambda_handler"""
        # Configure mocks
        mock_get_template_from_s3.return_value = "AWSTemplateFormatVersion: '2010-09-09'\nResources: {}"
        mock_validate_template_syntax.return_value = (True, None)
        mock_extract_parameters.return_value = {'Param1': 'default1', 'Param2': 'default2'}
        mock_validate_with_changeset.return_value = (True, {
            'status': 'VALID',
            'changes_count': 2,
            'capabilities': ['CAPABILITY_IAM'],
            'description': 'Template validation successful'
        })
        mock_update_job_status.return_value = True
        
        # Call the function
        response = lambda_function.lambda_handler(self.event, self.context)
        
        # Verify the response
        self.assertEqual(response['validation_status'], 'PASSED')
        self.assertEqual(response['job_id'], '12345678-1234-5678-1234-567812345678')
        
        # Verify mock calls
        mock_get_template_from_s3.assert_called_once_with('s3://test-bucket/IaC/cloudformation_template_1621234789.yaml')
        mock_validate_template_syntax.assert_called_once()
        mock_extract_parameters.assert_called_once()
        mock_validate_with_changeset.assert_called_once()
        mock_update_job_status.assert_called_with('12345678-1234-5678-1234-567812345678', 'VALIDATED', 'Template validation successful')

    @patch('validation-lambda.lambda_function.update_job_status')
    @patch('validation-lambda.lambda_function.get_template_from_s3')
    @patch('validation-lambda.lambda_function.validate_template_syntax')
    def test_lambda_handler_syntax_error(self, mock_validate_template_syntax, mock_get_template_from_s3, mock_update_job_status):
        """Test lambda_handler with syntax validation error"""
        # Configure mocks
        mock_get_template_from_s3.return_value = "Invalid YAML"
        mock_validate_template_syntax.return_value = (False, "Template format error")
        mock_update_job_status.return_value = True
        
        # Call the function
        response = lambda_function.lambda_handler(self.event, self.context)
        
        # Verify the response
        self.assertEqual(response['validation_status'], 'FAILED')
        self.assertEqual(response['validation_errors'], 'Template format error')
        
        # Verify mock calls
        mock_get_template_from_s3.assert_called_once()
        mock_validate_template_syntax.assert_called_once()
        mock_update_job_status.assert_called_with('12345678-1234-5678-1234-567812345678', 'VALIDATION_FAILED', 'Template syntax validation failed: Template format error')

    @patch('validation-lambda.lambda_function.update_job_status')
    @patch('validation-lambda.lambda_function.get_template_from_s3')
    @patch('validation-lambda.lambda_function.validate_template_syntax')
    @patch('validation-lambda.lambda_function.extract_parameters_from_template')
    @patch('validation-lambda.lambda_function.validate_with_changeset')
    def test_lambda_handler_changeset_error(self, mock_validate_with_changeset, mock_extract_parameters, 
                                          mock_validate_template_syntax, mock_get_template_from_s3, 
                                          mock_update_job_status):
        """Test lambda_handler with change set validation error"""
        # Configure mocks
        mock_get_template_from_s3.return_value = "AWSTemplateFormatVersion: '2010-09-09'\nResources: {}"
        mock_validate_template_syntax.return_value = (True, None)
        mock_extract_parameters.return_value = {'Param1': 'default1'}
        mock_validate_with_changeset.return_value = (False, {
            'status': 'INVALID',
            'reason': 'Resource type not supported',
            'description': 'Template validation failed'
        })
        mock_update_job_status.return_value = True
        
        # Call the function
        response = lambda_function.lambda_handler(self.event, self.context)
        
        # Verify the response
        self.assertEqual(response['validation_status'], 'FAILED')
        self.assertEqual(response['validation_errors'], 'Resource type not supported')
        
        # Verify mock calls
        mock_get_template_from_s3.assert_called_once()
        mock_validate_template_syntax.assert_called_once()
        mock_extract_parameters.assert_called_once()
        mock_validate_with_changeset.assert_called_once()
        mock_update_job_status.assert_called_with('12345678-1234-5678-1234-567812345678', 'VALIDATION_FAILED', 'Template deployment validation failed: Resource type not supported')

    def test_extract_parameters_from_template(self):
        """Test extract_parameters_from_template function"""
        # Test with JSON template
        json_template = '''
        {
            "Parameters": {
                "InstanceType": {
                    "Type": "String",
                    "Default": "t2.micro",
                    "Description": "EC2 instance type"
                },
                "KeyName": {
                    "Type": "AWS::EC2::KeyPair::KeyName",
                    "Description": "Name of an existing EC2 KeyPair"
                },
                "VpcId": {
                    "Type": "AWS::EC2::VPC::Id",
                    "Description": "VPC ID"
                }
            }
        }
        '''
        
        # Mock boto3 client for EC2 calls
        with patch('boto3.client') as mock_boto_client:
            # Mock EC2 client for VPC ID
            mock_ec2 = MagicMock()
            mock_ec2.describe_vpcs.return_value = {
                'Vpcs': [{'VpcId': 'vpc-12345678'}]
            }
            mock_boto_client.return_value = mock_ec2
            
            # Call the function
            params = lambda_function.extract_parameters_from_template(json_template)
            
            # Verify the result
            self.assertEqual(params['InstanceType'], 't2.micro')
            self.assertIn('VpcId', params)
            self.assertEqual(params['VpcId'], 'vpc-12345678')
            self.assertNotIn('KeyName', params)  # KeyPair should be skipped

if __name__ == '__main__':
    unittest.main()
