#!/bin/bash

# Deploy script for the entire Mainframe Modernization Platform
# This script deploys all services and infrastructure components

set -e

# Default values
ENVIRONMENT="dev"
REGION=$(aws configure get region)
PLATFORM_STACK_NAME="mainframe-modernization-platform"
PROFILE=""

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
    echo "  --help                    Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 --env dev --region us-east-1"
    echo "  $0 --env prod --region us-west-2 --profile production"
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

# Validate required parameters
if [[ -z "$REGION" ]]; then
    print_error "Region is required. Set it via --region or configure AWS CLI."
    exit 1
fi

# Set AWS profile if provided
if [[ -n "$PROFILE" ]]; then
    export AWS_PROFILE="$PROFILE"
    print_status "Using AWS profile: $PROFILE"
fi

# Get AWS account ID
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
print_status "Deploying to AWS Account: $ACCOUNT_ID in region: $REGION"

# Change to script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."

print_status "Starting deployment of Mainframe Modernization Platform..."
print_status "Environment: $ENVIRONMENT"
print_status "Region: $REGION"
print_status "Stack Name: $PLATFORM_STACK_NAME"

# Step 1: Deploy the entire platform using the master template
print_status "Step 1: Deploying Mainframe Modernization Platform..."

# First, package and upload any Lambda code if needed
print_status "Preparing Lambda deployment packages..."

# Package CFN Generator Lambda functions
if [[ -d "services/cfn-generator/src" ]]; then
    cd services/cfn-generator
    if [[ -x "scripts/deploy.sh" ]]; then
        print_status "Packaging CFN Generator Lambda functions..."
        # Extract just the packaging part from the deploy script
        ./scripts/deploy.sh --package-only --env "$ENVIRONMENT" --region "$REGION" || true
    fi
    cd ../..
fi

# Package Mainframe Analyzer Lambda functions  
if [[ -d "services/mainframe-analyzer/src" ]]; then
    cd services/mainframe-analyzer
    if [[ -x "scripts/3.package-lambdas.sh" ]]; then
        print_status "Packaging Mainframe Analyzer Lambda functions..."
        ./scripts/3.package-lambdas.sh --region "$REGION" --env "$ENVIRONMENT" || true
    fi
    cd ../..
fi

# Deploy the master template
print_status "Deploying master CloudFormation template..."

aws cloudformation deploy \
    --template-file infrastructure/main.yaml \
    --stack-name "${PLATFORM_STACK_NAME}-${ENVIRONMENT}" \
    --parameter-overrides \
        Environment="$ENVIRONMENT" \
        FoundationModel="anthropic.claude-3-5-haiku-20241022-v1:0" \
        IdleSessionTTL=600 \
        DeployServices="both" \
    --capabilities CAPABILITY_NAMED_IAM \
    --region "$REGION" \
    --no-fail-on-empty-changeset

if [[ $? -eq 0 ]]; then
    print_success "Platform deployed successfully"
else
    print_error "Failed to deploy platform"
    exit 1
fi

# Step 4: Get deployment outputs
print_status "Step 4: Retrieving deployment information..."

# Get Supervisor Agent information
SUPERVISOR_AGENT_ID=$(aws cloudformation describe-stacks \
    --stack-name "${PLATFORM_STACK_NAME}-${ENVIRONMENT}" \
    --region "$REGION" \
    --query "Stacks[0].Outputs[?OutputKey=='SupervisorAgentId'].OutputValue" \
    --output text 2>/dev/null || echo "Not found")

SUPERVISOR_AGENT_ALIAS_ID=$(aws cloudformation describe-stacks \
    --stack-name "${PLATFORM_STACK_NAME}-${ENVIRONMENT}" \
    --region "$REGION" \
    --query "Stacks[0].Outputs[?OutputKey=='SupervisorAgentAliasId'].OutputValue" \
    --output text 2>/dev/null || echo "Not found")

# Display deployment summary
print_success "=== DEPLOYMENT COMPLETE ==="
echo ""
echo "Platform: Mainframe Modernization Platform"
echo "Environment: $ENVIRONMENT"
echo "Region: $REGION"
echo "Account: $ACCOUNT_ID"
echo ""
echo "=== BEDROCK AGENTS ==="
echo "Supervisor Agent ID: $SUPERVISOR_AGENT_ID"
echo "Supervisor Agent Alias ID: $SUPERVISOR_AGENT_ALIAS_ID"
echo ""
echo "=== NEXT STEPS ==="
echo "1. Navigate to the Amazon Bedrock console"
echo "2. Go to Agents section"
echo "3. Find your Supervisor Agent: ${PLATFORM_STACK_NAME}-agents-${ENVIRONMENT}"
echo "4. Use the Test tab to interact with the platform"
echo ""
echo "=== EXAMPLE INTERACTIONS ==="
echo "• 'Generate CloudFormation templates from s3://my-bucket/configs/'"
echo "• 'Analyze mainframe documentation in s3://my-bucket/docs/'"
echo "• 'Check the status of job 12345'"
echo ""
print_success "Platform deployment completed successfully!"

# Optional: Run basic health checks
print_status "Running basic health checks..."

# Check if stacks exist
STACKS_TO_CHECK=(
    "${PLATFORM_STACK_NAME}-${ENVIRONMENT}"
)

for stack in "${STACKS_TO_CHECK[@]}"; do
    STATUS=$(aws cloudformation describe-stacks \
        --stack-name "$stack" \
        --region "$REGION" \
        --query "Stacks[0].StackStatus" \
        --output text 2>/dev/null || echo "NOT_FOUND")
    
    if [[ "$STATUS" == "CREATE_COMPLETE" || "$STATUS" == "UPDATE_COMPLETE" ]]; then
        print_success "✓ Stack $stack is healthy"
    else
        print_warning "⚠ Stack $stack status: $STATUS"
    fi
done

print_success "Health checks completed!"
