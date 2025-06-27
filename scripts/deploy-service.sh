#!/bin/bash

# Deploy script for individual services in the Mainframe Modernization Platform
# This script can deploy specific services independently

set -e

# Default values
ENVIRONMENT="dev"
REGION=$(aws configure get region)
SERVICE=""
STACK_NAME_PREFIX="mainframe-modernization-platform"
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
    echo "Usage: $0 --service SERVICE [OPTIONS]"
    echo ""
    echo "Required:"
    echo "  --service SERVICE         Service to deploy (cfn-generator, mainframe-analyzer, bedrock-agents)"
    echo ""
    echo "Options:"
    echo "  --env ENVIRONMENT         Environment (dev, staging, prod) [default: dev]"
    echo "  --region REGION          AWS region [default: from AWS CLI config]"
    echo "  --stack-prefix PREFIX    Stack name prefix [default: mainframe-modernization-platform]"
    echo "  --profile PROFILE        AWS profile to use"
    echo "  --help                   Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 --service cfn-generator --env dev --region us-east-1"
    echo "  $0 --service mainframe-analyzer --env prod --region us-west-2"
    echo "  $0 --service bedrock-agents --env dev --region us-east-1"
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --service)
            SERVICE="$2"
            shift 2
            ;;
        --env)
            ENVIRONMENT="$2"
            shift 2
            ;;
        --region)
            REGION="$2"
            shift 2
            ;;
        --stack-prefix)
            STACK_NAME_PREFIX="$2"
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
if [[ -z "$SERVICE" ]]; then
    print_error "Service is required. Use --service to specify which service to deploy."
    usage
    exit 1
fi

if [[ -z "$REGION" ]]; then
    print_error "Region is required. Set it via --region or configure AWS CLI."
    exit 1
fi

# Validate service name
case $SERVICE in
    cfn-generator|mainframe-analyzer|bedrock-agents)
        ;;
    *)
        print_error "Invalid service: $SERVICE"
        print_error "Valid services: cfn-generator, mainframe-analyzer, bedrock-agents"
        exit 1
        ;;
esac

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

print_status "Starting deployment of service: $SERVICE"
print_status "Environment: $ENVIRONMENT"
print_status "Region: $REGION"
print_status "Stack Prefix: $STACK_NAME_PREFIX"

# Deploy the specified service
case $SERVICE in
    bedrock-agents)
        print_status "Deploying Bedrock Agents..."
        
        aws cloudformation deploy \
            --template-file infrastructure/combined-mainframe-modernization-agents.yaml \
            --stack-name "${STACK_NAME_PREFIX}-agents-${ENVIRONMENT}" \
            --parameter-overrides \
                Environment="$ENVIRONMENT" \
                FoundationModel="anthropic.claude-3-5-haiku-20241022-v1:0" \
                IdleSessionTTL=600 \
            --capabilities CAPABILITY_NAMED_IAM \
            --region "$REGION" \
            --no-fail-on-empty-changeset
        
        if [[ $? -eq 0 ]]; then
            print_success "Bedrock agents deployed successfully"
            
            # Get agent information
            SUPERVISOR_AGENT_ID=$(aws cloudformation describe-stacks \
                --stack-name "${STACK_NAME_PREFIX}-agents-${ENVIRONMENT}" \
                --region "$REGION" \
                --query "Stacks[0].Outputs[?OutputKey=='SupervisorAgentId'].OutputValue" \
                --output text 2>/dev/null || echo "Not found")
            
            echo ""
            echo "=== BEDROCK AGENTS DEPLOYED ==="
            echo "Supervisor Agent ID: $SUPERVISOR_AGENT_ID"
            echo "Stack Name: ${STACK_NAME_PREFIX}-agents-${ENVIRONMENT}"
        else
            print_error "Failed to deploy Bedrock agents"
            exit 1
        fi
        ;;
        
    cfn-generator)
        print_status "Deploying CloudFormation Generator Service..."
        
        # Deploy using the infrastructure template
        aws cloudformation deploy \
            --template-file infrastructure/cfn-generator-service.yaml \
            --stack-name "${STACK_NAME_PREFIX}-cfn-generator-${ENVIRONMENT}" \
            --parameter-overrides \
                Environment="$ENVIRONMENT" \
                LambdaCodeBucket="cfn-generator-${ENVIRONMENT}-$(aws sts get-caller-identity --query Account --output text)-${REGION}" \
                BedrockModelId="arn:aws:bedrock:${REGION}:$(aws sts get-caller-identity --query Account --output text):inference-profile/anthropic.claude-3-5-haiku-20241022-v1:0" \
            --capabilities CAPABILITY_NAMED_IAM \
            --region "$REGION" \
            --no-fail-on-empty-changeset
        
        if [[ $? -eq 0 ]]; then
            print_success "CFN Generator Service deployed successfully"
            echo ""
            echo "=== CFN GENERATOR SERVICE DEPLOYED ==="
            echo "Stack Name: ${STACK_NAME_PREFIX}-cfn-generator-${ENVIRONMENT}"
        else
            print_error "Failed to deploy CFN Generator Service"
            exit 1
        fi
        ;;
        
    mainframe-analyzer)
        print_status "Deploying Mainframe Analyzer Service..."
        
        # Deploy using the infrastructure template
        aws cloudformation deploy \
            --template-file infrastructure/mainframe-analyzer-service.yaml \
            --stack-name "${STACK_NAME_PREFIX}-mainframe-analyzer-${ENVIRONMENT}" \
            --parameter-overrides \
                Environment="$ENVIRONMENT" \
                BedrockModelId="arn:aws:bedrock:${REGION}:$(aws sts get-caller-identity --query Account --output text):inference-profile/anthropic.claude-3-5-haiku-20241022-v1:0" \
            --capabilities CAPABILITY_NAMED_IAM \
            --region "$REGION" \
            --no-fail-on-empty-changeset
        
        if [[ $? -eq 0 ]]; then
            print_success "Mainframe Analyzer Service deployed successfully"
            echo ""
            echo "=== MAINFRAME ANALYZER SERVICE DEPLOYED ==="
            echo "Stack Name: ${STACK_NAME_PREFIX}-mainframe-analyzer-${ENVIRONMENT}"
        else
            print_error "Failed to deploy Mainframe Analyzer Service"
            exit 1
        fi
        ;;
esac

# Run health check for the deployed service
print_status "Running health check for $SERVICE..."

STACK_NAME="${STACK_NAME_PREFIX}-${SERVICE}-${ENVIRONMENT}"
if [[ "$SERVICE" == "bedrock-agents" ]]; then
    STACK_NAME="${STACK_NAME_PREFIX}-agents-${ENVIRONMENT}"
fi

STATUS=$(aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME" \
    --region "$REGION" \
    --query "Stacks[0].StackStatus" \
    --output text 2>/dev/null || echo "NOT_FOUND")

if [[ "$STATUS" == "CREATE_COMPLETE" || "$STATUS" == "UPDATE_COMPLETE" ]]; then
    print_success "✓ Service $SERVICE is healthy (Status: $STATUS)"
else
    print_warning "⚠ Service $SERVICE status: $STATUS"
fi

print_success "Service deployment completed!"

# Provide next steps based on the service deployed
echo ""
echo "=== NEXT STEPS ==="
case $SERVICE in
    bedrock-agents)
        echo "1. Navigate to the Amazon Bedrock console"
        echo "2. Go to Agents section"
        echo "3. Find your Supervisor Agent"
        echo "4. Use the Test tab to interact with the platform"
        ;;
    cfn-generator)
        echo "1. Upload resource configurations to S3"
        echo "2. Use the Bedrock agent or direct API to start template generation"
        echo "3. Monitor job status and retrieve generated templates"
        ;;
    mainframe-analyzer)
        echo "1. Upload mainframe documentation to S3 (PDF, DOCX, TXT)"
        echo "2. Use the Bedrock agent or direct API to start analysis"
        echo "3. Monitor job status and retrieve modernization recommendations"
        ;;
esac
