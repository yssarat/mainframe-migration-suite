"""
Prompt Manager for Mainframe Analyzer Service

This module provides centralized prompt management with S3 storage and local caching.
Supports multiple programming languages and fallback mechanisms.
"""

import boto3
import os
import time
import logging
from typing import Optional, Dict
from botocore.exceptions import ClientError, NoCredentialsError

# Configure logging
logger = logging.getLogger(__name__)

class PromptManager:
    """
    Manages prompts stored in S3 with local caching and language support.
    
    Features:
    - S3-based prompt storage with versioning
    - Local caching with TTL
    - Multi-language support (Python, .NET, Java)
    - Fallback mechanisms for reliability
    - Error handling and logging
    """
    
    def __init__(self):
        """Initialize the PromptManager with configuration from environment variables."""
        self.s3_client = boto3.client('s3')
        self.bucket_name = os.environ.get('PROMPTS_BUCKET')
        self.cache_ttl = int(os.environ.get('CACHE_TTL_SECONDS', '300'))  # 5 minutes default
        self.default_language = os.environ.get('DEFAULT_LANGUAGE', 'python')
        
        # Local cache storage
        self.cache = {}
        self.cache_timestamps = {}
        
        # Validate configuration
        if not self.bucket_name:
            logger.warning("PROMPTS_BUCKET environment variable not set")
        
        logger.info(f"PromptManager initialized with bucket: {self.bucket_name}, TTL: {self.cache_ttl}s")
    
    def get_prompt(self, agent_type: str, language: str = None) -> str:
        """
        Get prompt for specified agent type and language with caching.
        
        Args:
            agent_type: Type of agent ('analysis-agent', 'chunk-processor-agent')
            language: Target language ('python', 'dotnet', 'java'). Uses default if None.
            
        Returns:
            Prompt content as string, or fallback prompt if not found
        """
        if not language:
            language = self.default_language
        
        cache_key = f"{agent_type}_{language}"
        
        # Check cache first
        if self._is_cache_valid(cache_key):
            logger.debug(f"Cache hit for {cache_key}")
            return self.cache[cache_key]
        
        # Try to get language-specific prompt
        prompt = self._get_language_specific_prompt(agent_type, language)
        
        # Fallback to default prompt if language-specific not found
        if not prompt and language != 'python':
            logger.info(f"Language-specific prompt not found for {language}, falling back to default")
            prompt = self._get_language_specific_prompt(agent_type, 'python')
        
        # Final fallback to system prompt
        if not prompt:
            logger.info(f"No S3 prompt found for {agent_type}, falling back to system default")
            prompt = self._get_default_prompt(agent_type)
        
        # Cache the result
        if prompt:
            self.cache[cache_key] = prompt
            self.cache_timestamps[cache_key] = time.time()
            logger.info(f"Cached prompt for {cache_key} ({len(prompt)} characters)")
        
        return prompt
    
    def _get_language_specific_prompt(self, agent_type: str, language: str) -> Optional[str]:
        """Get language-specific prompt from S3."""
        s3_key = f"{agent_type}/{language}-prompt.txt"
        return self._get_from_s3(s3_key)
    
    def _get_from_s3(self, s3_key: str) -> Optional[str]:
        """
        Retrieve prompt content from S3 with error handling.
        
        Args:
            s3_key: S3 object key
            
        Returns:
            Prompt content or None if not found/error
        """
        if not self.bucket_name:
            logger.error("No S3 bucket configured for prompts")
            return None
        
        try:
            logger.debug(f"Fetching prompt from s3://{self.bucket_name}/{s3_key}")
            response = self.s3_client.get_object(Bucket=self.bucket_name, Key=s3_key)
            content = response['Body'].read().decode('utf-8')
            logger.info(f"Successfully retrieved prompt from S3: {s3_key} ({len(content)} characters)")
            return content
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'NoSuchKey':
                logger.debug(f"Prompt not found in S3: {s3_key}")
            elif error_code == 'NoSuchBucket':
                logger.error(f"S3 bucket not found: {self.bucket_name}")
            else:
                logger.error(f"S3 error retrieving {s3_key}: {e}")
            return None
            
        except NoCredentialsError:
            logger.error("AWS credentials not configured")
            return None
            
        except Exception as e:
            logger.error(f"Unexpected error retrieving prompt from S3: {e}")
            return None
    
    def _is_cache_valid(self, cache_key: str) -> bool:
        """
        Check if cached prompt is still valid based on TTL.
        
        Args:
            cache_key: Cache key to check
            
        Returns:
            True if cache is valid, False otherwise
        """
        if cache_key not in self.cache or cache_key not in self.cache_timestamps:
            return False
        
        age = time.time() - self.cache_timestamps[cache_key]
        return age < self.cache_ttl
    
    def _get_default_prompt(self, agent_type: str) -> str:
        """
        Get fallback prompt when S3 retrieval fails.
        
        Args:
            agent_type: Type of agent
            
        Returns:
            Default prompt content
        """
        if agent_type == 'analysis-agent':
            return """You are an expert AWS architect specializing in mainframe modernization.

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
[Complete project documentation]
```

Generate complete, deployable AWS solutions for mainframe modernization."""
        
        elif agent_type == 'chunk-processor-agent':
            return """You are an expert AWS architect specializing in mainframe modernization.

This is a chunk of a larger mainframe modernization analysis. Generate AWS artifacts that integrate with the overall solution.

Focus on creating complete, production-ready components that work together as part of the larger modernization effort."""
        
        else:
            return "You are an expert AWS architect specializing in mainframe modernization."
    
    def clear_cache(self):
        """Clear all cached prompts. Useful for testing or forcing refresh."""
        self.cache.clear()
        self.cache_timestamps.clear()
        logger.info("Prompt cache cleared")
    
    def get_cache_stats(self) -> Dict[str, int]:
        """
        Get cache statistics for monitoring.
        
        Returns:
            Dictionary with cache statistics
        """
        valid_entries = sum(1 for key in self.cache.keys() if self._is_cache_valid(key))
        
        return {
            'total_entries': len(self.cache),
            'valid_entries': valid_entries,
            'expired_entries': len(self.cache) - valid_entries,
            'cache_ttl_seconds': self.cache_ttl
        }
    
    def preload_prompts(self, agent_types: list, languages: list = None):
        """
        Preload prompts into cache for better performance.
        
        Args:
            agent_types: List of agent types to preload
            languages: List of languages to preload (defaults to common languages)
        """
        if not languages:
            languages = ['python', 'dotnet', 'java']
        
        logger.info(f"Preloading prompts for agents: {agent_types}, languages: {languages}")
        
        for agent_type in agent_types:
            for language in languages:
                try:
                    self.get_prompt(agent_type, language)
                except Exception as e:
                    logger.warning(f"Failed to preload prompt for {agent_type}/{language}: {e}")
        
        logger.info("Prompt preloading completed")


# Global instance for reuse across Lambda invocations
_prompt_manager_instance = None

def get_prompt_manager() -> PromptManager:
    """
    Get singleton PromptManager instance for efficient reuse.
    
    Returns:
        PromptManager instance
    """
    global _prompt_manager_instance
    
    if _prompt_manager_instance is None:
        _prompt_manager_instance = PromptManager()
    
    return _prompt_manager_instance
