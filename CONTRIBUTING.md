# Contributing to Mainframe Modernization Platform

We welcome contributions to the Mainframe Modernization Platform! This document provides guidelines for contributing to the project.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Contributing Guidelines](#contributing-guidelines)
- [Pull Request Process](#pull-request-process)
- [Coding Standards](#coding-standards)
- [Testing](#testing)
- [Documentation](#documentation)

## Code of Conduct

This project adheres to a code of conduct that we expect all contributors to follow. Please be respectful and professional in all interactions.

## Getting Started

### Prerequisites

- AWS Account with appropriate permissions
- AWS CLI installed and configured
- Python 3.9 or higher
- Git
- Basic understanding of AWS services (Lambda, S3, DynamoDB, Step Functions, Bedrock)

### Development Setup

1. **Fork and Clone the Repository**
   ```bash
   git clone https://github.com/your-username/mainframe-modernization-platform.git
   cd mainframe-modernization-platform
   ```

2. **Set Up Python Environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Install Development Dependencies**
   ```bash
   pip install -r requirements-dev.txt
   ```

4. **Set Up Pre-commit Hooks**
   ```bash
   pre-commit install
   ```

## Contributing Guidelines

### Types of Contributions

We welcome several types of contributions:

- **Bug Reports**: Help us identify and fix issues
- **Feature Requests**: Suggest new functionality
- **Code Contributions**: Implement bug fixes or new features
- **Documentation**: Improve or add documentation
- **Testing**: Add or improve test coverage

### Before You Start

1. **Check Existing Issues**: Look for existing issues or discussions related to your contribution
2. **Create an Issue**: For significant changes, create an issue to discuss the approach
3. **Fork the Repository**: Create your own fork to work on

### Branch Naming Convention

Use descriptive branch names that indicate the type of change:

- `feature/add-new-service` - New features
- `bugfix/fix-lambda-timeout` - Bug fixes
- `docs/update-readme` - Documentation updates
- `refactor/improve-error-handling` - Code refactoring
- `test/add-integration-tests` - Testing improvements

## Pull Request Process

### 1. Prepare Your Changes

- Ensure your code follows the coding standards
- Add or update tests as needed
- Update documentation if required
- Run the test suite locally

### 2. Create a Pull Request

- Use a clear and descriptive title
- Provide a detailed description of changes
- Reference any related issues
- Include screenshots for UI changes (if applicable)

### 3. Pull Request Template

```markdown
## Description
Brief description of the changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Documentation update
- [ ] Refactoring
- [ ] Testing improvement

## Testing
- [ ] Unit tests pass
- [ ] Integration tests pass
- [ ] Manual testing completed

## Checklist
- [ ] Code follows style guidelines
- [ ] Self-review completed
- [ ] Documentation updated
- [ ] No breaking changes (or clearly documented)
```

### 4. Review Process

- All PRs require at least one review
- Address feedback promptly
- Keep PRs focused and reasonably sized
- Be responsive to questions and suggestions

## Coding Standards

### Python Code Style

- Follow PEP 8 style guidelines
- Use meaningful variable and function names
- Add docstrings to functions and classes
- Keep functions focused and reasonably sized

### Example Function Documentation

```python
def process_mainframe_document(file_path: str, document_type: str) -> Dict[str, Any]:
    """
    Process a mainframe document and extract relevant information.
    
    Args:
        file_path (str): Path to the document file
        document_type (str): Type of document (pdf, docx, txt)
    
    Returns:
        Dict[str, Any]: Extracted document information
    
    Raises:
        ValueError: If document type is not supported
        FileNotFoundError: If file does not exist
    """
    # Implementation here
    pass
```

### CloudFormation Templates

- Use consistent parameter naming
- Include comprehensive descriptions
- Follow AWS best practices
- Use appropriate resource naming conventions

### Lambda Functions

- Keep handler functions simple and focused
- Use environment variables for configuration
- Implement proper error handling
- Include appropriate logging

```python
import logging
import json
from typing import Dict, Any

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda function handler.
    
    Args:
        event: Lambda event data
        context: Lambda context object
    
    Returns:
        Response dictionary
    """
    try:
        logger.info(f"Processing event: {json.dumps(event)}")
        
        # Process the event
        result = process_event(event)
        
        return {
            'statusCode': 200,
            'body': json.dumps(result)
        }
    
    except Exception as e:
        logger.error(f"Error processing event: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }
```

## Testing

### Test Structure

```
tests/
├── unit/                    # Unit tests
│   ├── cfn-generator/
│   └── mainframe-analyzer/
├── integration/             # Integration tests
└── fixtures/               # Test data and fixtures
```

### Writing Tests

- Write unit tests for all new functions
- Include integration tests for workflows
- Use meaningful test names
- Test both success and failure scenarios

### Example Unit Test

```python
import pytest
from unittest.mock import Mock, patch
from src.analysis_lambda.lambda_function import lambda_handler

class TestAnalysisLambda:
    
    def test_successful_analysis(self):
        """Test successful document analysis."""
        event = {
            'job_id': 'test-job-123',
            'bucket_name': 'test-bucket',
            's3_folder': 'test-folder'
        }
        
        with patch('boto3.client') as mock_boto3:
            mock_s3 = Mock()
            mock_boto3.return_value = mock_s3
            
            result = lambda_handler(event, None)
            
            assert result['statusCode'] == 200
            assert 'job_id' in json.loads(result['body'])
    
    def test_missing_parameters(self):
        """Test handling of missing required parameters."""
        event = {}
        
        result = lambda_handler(event, None)
        
        assert result['statusCode'] == 400
        assert 'error' in json.loads(result['body'])
```

### Running Tests

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/unit/test_analysis_lambda.py

# Run with coverage
pytest --cov=src tests/
```

## Documentation

### Types of Documentation

1. **Code Documentation**: Docstrings and inline comments
2. **API Documentation**: Function and endpoint documentation
3. **User Documentation**: Usage guides and examples
4. **Architecture Documentation**: System design and architecture

### Documentation Standards

- Keep documentation up to date with code changes
- Use clear and concise language
- Include examples where helpful
- Follow Markdown standards for formatting

### Adding New Service Documentation

When adding a new service:

1. Create `services/your-service/README.md`
2. Document the service purpose and architecture
3. Include deployment instructions
4. Add usage examples
5. Update the main platform README

## Service-Specific Guidelines

### CloudFormation Generator Service

- Follow AWS CloudFormation best practices
- Validate templates before generation
- Include comprehensive error handling
- Support multiple resource types

### Mainframe Analyzer Service

- Support multiple document formats
- Implement efficient text extraction
- Provide meaningful analysis results
- Handle large document sets gracefully

### Adding New Services

When contributing a new service:

1. Follow the established directory structure
2. Implement consistent error handling
3. Add comprehensive tests
4. Include CloudFormation templates
5. Update the Supervisor Agent routing logic
6. Add service-specific documentation

## Getting Help

- **Issues**: Create an issue for bugs or feature requests
- **Discussions**: Use GitHub Discussions for questions
- **Documentation**: Check existing documentation first

## Recognition

Contributors will be recognized in the project's contributors list. Significant contributions may be highlighted in release notes.

Thank you for contributing to the Mainframe Modernization Platform!
