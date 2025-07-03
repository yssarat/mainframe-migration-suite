#!/bin/bash

# Cleanup script for the Mainframe Modernization Platform
# This script removes all AWS resources, local artifacts, and temporary files
# created during deployment and development

set -e

# Default values
ENVIRONMENT="dev"
REGION=$(aws configure get region)
PLATFORM_STACK_NAME="mainframe-modernization-platform"
PROFILE=""
FORCE_DELETE="false"
CLEAN_LOCAL_ONLY="false"
CLEAN_AWS_ONLY="false"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to show usage
usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --env ENVIRONMENT          Environment (dev, staging, prod) [default: dev]"
    echo "  --region REGION           AWS region [default: from AWS CLI config]"
    echo "  --stack-name STACK_NAME   Platform stack name [default: mainframe-modernization-platform]"
    echo "  --profile PROFILE         AWS profile to use"
    echo "  --force                   Skip confirmation prompts"
    echo "  --local-only              Clean only local files (skip AWS resources)"
    echo "  --aws-only                Clean only AWS resources (skip local files)"
    echo "  --help                    Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 --env dev --region us-east-1"
    echo "  $0 --env prod --region us-west-2 --profile production"
    echo "  $0 --local-only           # Clean only local artifacts"
    echo "  $0 --aws-only --force     # Clean only AWS resources without prompts"
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --env)
            ENVIRONMENT="$2"
            shift 2
            ;;
        --region)
            REGION="$2"
            shift 2
            ;;
        --stack-name)
            PLATFORM_STACK_NAME="$2"
            shift 2
            ;;
        --profile)
            PROFILE="$2"
            shift 2
            ;;
        --force)
            FORCE_DELETE="true"
            shift
            ;;
        --local-only)
            CLEAN_LOCAL_ONLY="true"
            shift
            ;;
        --aws-only)
            CLEAN_AWS_ONLY="true"
            shift
            ;;
        --help)
            usage
            exit 0
            ;;
        *)
            print_error "Unknown option: $1"
            usage
            exit 1
            ;;
    esac
done

# Validate inputs
if [[ -z "$REGION" ]]; then
    print_error "AWS region not specified and not found in AWS CLI config"
    exit 1
fi

if [[ "$CLEAN_LOCAL_ONLY" == "true" && "$CLEAN_AWS_ONLY" == "true" ]]; then
    print_error "Cannot specify both --local-only and --aws-only"
    exit 1
fi

# Get AWS account ID
if [[ "$CLEAN_AWS_ONLY" == "true" || "$CLEAN_LOCAL_ONLY" == "false" ]]; then
    if [[ -n "$PROFILE" ]]; then
        ACCOUNT_ID=$(aws sts get-caller-identity --profile "$PROFILE" --query Account --output text 2>/dev/null || echo "")
    else
        ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text 2>/dev/null || echo "")
    fi
    
    if [[ -z "$ACCOUNT_ID" ]]; then
        print_error "Failed to get AWS account ID. Please check your AWS credentials."
        exit 1
    fi
fi

# Display configuration
print_status "=== CLEANUP CONFIGURATION ==="
print_status "Environment: $ENVIRONMENT"
print_status "Region: $REGION"
print_status "Stack Name: $PLATFORM_STACK_NAME"
if [[ -n "$ACCOUNT_ID" ]]; then
    print_status "Account ID: $ACCOUNT_ID"
fi
if [[ -n "$PROFILE" ]]; then
    print_status "AWS Profile: $PROFILE"
fi
print_status "Force Delete: $FORCE_DELETE"
print_status "Local Only: $CLEAN_LOCAL_ONLY"
print_status "AWS Only: $CLEAN_AWS_ONLY"
echo ""

# Confirmation prompt
if [[ "$FORCE_DELETE" != "true" ]]; then
    print_warning "This will permanently delete AWS resources and local files."
    print_warning "This action cannot be undone!"
    echo ""
    read -p "Are you sure you want to proceed? (yes/no): " confirm
    if [[ "$confirm" != "yes" ]]; then
        print_status "Cleanup cancelled."
        exit 0
    fi
fi

# Function to safely delete S3 bucket and its contents
delete_s3_bucket() {
    local bucket_name="$1"
    local aws_cmd="aws"
    
    if [[ -n "$PROFILE" ]]; then
        aws_cmd="aws --profile $PROFILE"
    fi
    
    if $aws_cmd s3 ls "s3://${bucket_name}" >/dev/null 2>&1; then
        print_status "Deleting S3 bucket and contents: ${bucket_name}"
        
        # Delete all objects and versions first
        $aws_cmd s3 rm "s3://${bucket_name}" --recursive >/dev/null 2>&1 || true
        
        # Delete any versioned objects
        $aws_cmd s3api delete-objects --bucket "${bucket_name}" \
            --delete "$($aws_cmd s3api list-object-versions --bucket "${bucket_name}" \
            --query '{Objects: Versions[].{Key:Key,VersionId:VersionId}}' \
            --output json)" >/dev/null 2>&1 || true
        
        # Delete any delete markers
        $aws_cmd s3api delete-objects --bucket "${bucket_name}" \
            --delete "$($aws_cmd s3api list-object-versions --bucket "${bucket_name}" \
            --query '{Objects: DeleteMarkers[].{Key:Key,VersionId:VersionId}}' \
            --output json)" >/dev/null 2>&1 || true
        
        # Finally delete the bucket
        $aws_cmd s3 rb "s3://${bucket_name}" >/dev/null 2>&1 || true
        print_success "Deleted S3 bucket: ${bucket_name}"
    else
        print_status "S3 bucket does not exist: ${bucket_name}"
    fi
}

# Function to delete CloudFormation stack
delete_cloudformation_stack() {
    local stack_name="$1"
    local aws_cmd="aws"
    
    if [[ -n "$PROFILE" ]]; then
        aws_cmd="aws --profile $PROFILE"
    fi
    
    # Check if stack exists
    if $aws_cmd cloudformation describe-stacks --stack-name "$stack_name" --region "$REGION" >/dev/null 2>&1; then
        print_status "Deleting CloudFormation stack: $stack_name"
        
        $aws_cmd cloudformation delete-stack --stack-name "$stack_name" --region "$REGION"
        
        print_status "Waiting for stack deletion to complete..."
        $aws_cmd cloudformation wait stack-delete-complete --stack-name "$stack_name" --region "$REGION" || {
            print_warning "Stack deletion may have failed or timed out. Check AWS console for details."
        }
        
        print_success "Deleted CloudFormation stack: $stack_name"
    else
        print_status "CloudFormation stack does not exist: $stack_name"
    fi
}

# Function to delete Bedrock agents
delete_bedrock_agents() {
    local aws_cmd="aws"
    
    if [[ -n "$PROFILE" ]]; then
        aws_cmd="aws --profile $PROFILE"
    fi
    
    print_status "Cleaning up Bedrock agents..."
    
    # List and delete agent aliases first
    local agent_pattern="${PLATFORM_STACK_NAME}-.*-${ENVIRONMENT}"
    
    # Get all agents that match our pattern
    local agents=$($aws_cmd bedrock-agent list-agents --region "$REGION" --query "agentSummaries[?contains(agentName, '${PLATFORM_STACK_NAME}') && contains(agentName, '${ENVIRONMENT}')].agentId" --output text 2>/dev/null || echo "")
    
    if [[ -n "$agents" ]]; then
        for agent_id in $agents; do
            print_status "Processing Bedrock agent: $agent_id"
            
            # Delete all aliases for this agent
            local aliases=$($aws_cmd bedrock-agent list-agent-aliases --agent-id "$agent_id" --region "$REGION" --query "agentAliasSummaries[].agentAliasId" --output text 2>/dev/null || echo "")
            
            for alias_id in $aliases; do
                if [[ "$alias_id" != "TSTALIASID" ]]; then  # Don't delete the test alias
                    print_status "Deleting agent alias: $alias_id"
                    $aws_cmd bedrock-agent delete-agent-alias --agent-id "$agent_id" --agent-alias-id "$alias_id" --region "$REGION" >/dev/null 2>&1 || true
                fi
            done
            
            # Delete the agent
            print_status "Deleting Bedrock agent: $agent_id"
            $aws_cmd bedrock-agent delete-agent --agent-id "$agent_id" --region "$REGION" >/dev/null 2>&1 || true
        done
        print_success "Cleaned up Bedrock agents"
    else
        print_status "No Bedrock agents found to delete"
    fi
}

# Function to clean local artifacts
clean_local_artifacts() {
    print_status "=== CLEANING LOCAL ARTIFACTS ==="
    
    # Remove build artifacts
    print_status "Removing build artifacts..."
    find . -name "*.zip" -type f -delete 2>/dev/null || true
    find . -name "*-packaged.yaml" -type f -delete 2>/dev/null || true
    find . -name "output.json" -type f -delete 2>/dev/null || true
    
    # Remove Python cache files
    print_status "Removing Python cache files..."
    find . -name "*.pyc" -type f -delete 2>/dev/null || true
    find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
    find . -name "*.pyo" -type f -delete 2>/dev/null || true
    
    # Remove macOS system files
    print_status "Removing macOS system files..."
    find . -name ".DS_Store" -type f -delete 2>/dev/null || true
    
    # Remove log files
    print_status "Removing log files..."
    find . -name "*.log" -type f -delete 2>/dev/null || true
    
    # Remove dist directories
    print_status "Removing distribution directories..."
    find . -name "dist" -type d -exec rm -rf {} + 2>/dev/null || true
    
    # Remove temporary files
    print_status "Removing temporary files..."
    find . -name "*.tmp" -type f -delete 2>/dev/null || true
    find . -name "*.temp" -type f -delete 2>/dev/null || true
    find . -name "temp_*" -type f -delete 2>/dev/null || true
    
    # Remove IDE files
    print_status "Removing IDE files..."
    find . -name ".vscode" -type d -exec rm -rf {} + 2>/dev/null || true
    find . -name ".idea" -type d -exec rm -rf {} + 2>/dev/null || true
    find . -name "*.swp" -type f -delete 2>/dev/null || true
    find . -name "*.swo" -type f -delete 2>/dev/null || true
    
    # Remove node_modules if any
    print_status "Removing node_modules directories..."
    find . -name "node_modules" -type d -exec rm -rf {} + 2>/dev/null || true
    
    # Remove coverage files
    print_status "Removing coverage files..."
    find . -name ".coverage" -type f -delete 2>/dev/null || true
    find . -name "htmlcov" -type d -exec rm -rf {} + 2>/dev/null || true
    find . -name ".pytest_cache" -type d -exec rm -rf {} + 2>/dev/null || true
    
    print_success "Local artifacts cleaned"
}

# Function to clean AWS resources
clean_aws_resources() {
    print_status "=== CLEANING AWS RESOURCES ==="
    
    # Define resource names
    STACK_NAME="${PLATFORM_STACK_NAME}-${ENVIRONMENT}"
    TEMPLATE_BUCKET="mainframe-modernization-templates-${ACCOUNT_ID}-${REGION}"
    CFN_LAMBDA_BUCKET="cfn-generator-${ENVIRONMENT}-${ACCOUNT_ID}-${REGION}"
    ANALYZER_LAMBDA_BUCKET="mainframe-analyzer-${ENVIRONMENT}-${ACCOUNT_ID}-${REGION}"
    TRANSFORM_BUCKET="mainframe-transform-${ENVIRONMENT}-${ACCOUNT_ID}"
    
    print_status "Resources to be deleted:"
    print_status "- CloudFormation Stack: $STACK_NAME"
    print_status "- S3 Buckets:"
    print_status "  - $TEMPLATE_BUCKET"
    print_status "  - $CFN_LAMBDA_BUCKET"
    print_status "  - $ANALYZER_LAMBDA_BUCKET"
    print_status "  - $TRANSFORM_BUCKET"
    print_status "- Bedrock Agents (matching pattern)"
    echo ""
    
    # Delete CloudFormation stack first (this will delete most resources)
    delete_cloudformation_stack "$STACK_NAME"
    
    # Delete S3 buckets (these might not be deleted by CloudFormation if they contain objects)
    print_status "Deleting S3 buckets..."
    delete_s3_bucket "$TEMPLATE_BUCKET"
    delete_s3_bucket "$CFN_LAMBDA_BUCKET"
    delete_s3_bucket "$ANALYZER_LAMBDA_BUCKET"
    delete_s3_bucket "$TRANSFORM_BUCKET"
    
    # Delete Bedrock agents
    delete_bedrock_agents
    
    print_success "AWS resources cleaned"
}

# Main cleanup logic
print_status "=== STARTING CLEANUP ==="

if [[ "$CLEAN_AWS_ONLY" == "true" ]]; then
    clean_aws_resources
elif [[ "$CLEAN_LOCAL_ONLY" == "true" ]]; then
    clean_local_artifacts
else
    # Clean both local and AWS resources
    clean_local_artifacts
    clean_aws_resources
fi

print_success "=== CLEANUP COMPLETED ==="
print_status "Summary of actions performed:"

if [[ "$CLEAN_LOCAL_ONLY" != "true" ]]; then
    print_status "✓ Deleted CloudFormation stack: ${PLATFORM_STACK_NAME}-${ENVIRONMENT}"
    print_status "✓ Deleted S3 buckets and their contents"
    print_status "✓ Cleaned up Bedrock agents and aliases"
fi

if [[ "$CLEAN_AWS_ONLY" != "true" ]]; then
    print_status "✓ Removed local build artifacts and temporary files"
    print_status "✓ Cleaned Python cache files"
    print_status "✓ Removed system and IDE files"
fi

echo ""
print_warning "Note: Some AWS resources may take a few minutes to be fully deleted."
print_warning "Check the AWS console to verify all resources have been removed."
echo ""
print_success "Cleanup completed successfully!"
