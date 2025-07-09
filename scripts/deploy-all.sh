#!/bin/bash

# Deploy script for the entire Mainframe Modernization Platform
# This script deploys all services and infrastructure components
# FIXED VERSION - Resolves "No pre-built Lambda packages in the dist directory" error

set -e

# Default values
ENVIRONMENT="dev"
REGION=$(aws configure get region)
PLATFORM_STACK_NAME="mainframe-modernization-platform"
PROFILE=""
CLEAN_BUCKETS="true"
CLEAN_AGENTS="true"

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
    echo "  --no-clean-buckets        Skip cleaning existing S3 buckets (may cause conflicts)"
    echo "  --no-clean-agents         Skip cleaning existing Bedrock agent aliases (may cause conflicts)"
    echo "  --help                    Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 --env dev --region us-east-1"
    echo "  $0 --env prod --region us-west-2 --profile production"
    echo "  $0 --env dev --no-clean-buckets  # Keep existing buckets"
    echo "  $0 --env dev --no-clean-agents   # Keep existing agent aliases"
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
        --no-clean-buckets)
            CLEAN_BUCKETS="false"
            shift
            ;;
        --no-clean-agents)
            CLEAN_AGENTS="false"
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

# Validate required parameters
if [[ -z "$REGION" ]]; then
    print_error "Region is required. Set it via --region or configure AWS CLI."
    exit 1
fi

# Check for required tools
if [[ "$CLEAN_AGENTS" == "true" ]] && ! command -v jq &> /dev/null; then
    print_error "jq is required for agent cleanup but not installed. Install jq or use --no-clean-agents"
    exit 1
fi

# Set AWS profile if provided
if [[ -n "$PROFILE" ]]; then
    export AWS_PROFILE="$PROFILE"
    print_status "Using AWS profile: $PROFILE"
fi

# Get AWS account ID
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text --profile "${PROFILE:-}")
print_status "Deploying to AWS Account: $ACCOUNT_ID in region: $REGION"

# Change to script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."

print_status "Starting deployment of Mainframe Modernization Platform..."
print_status "Environment: $ENVIRONMENT"
print_status "Region: $REGION"
print_status "Stack Name: $PLATFORM_STACK_NAME"

# Function to safely delete S3 bucket and its contents
delete_s3_bucket() {
    local bucket_name="$1"
    if aws s3 ls "s3://${bucket_name}" --profile "${PROFILE:-}" >/dev/null 2>&1; then
        print_status "Deleting existing S3 bucket and contents: ${bucket_name}"
        # Delete all objects and versions first
        aws s3 rm "s3://${bucket_name}" --recursive --profile "${PROFILE:-}" >/dev/null 2>&1 || true
        # Delete any versioned objects
        aws s3api delete-objects --bucket "${bucket_name}" \
            --delete "$(aws s3api list-object-versions --bucket "${bucket_name}" \
            --query '{Objects: Versions[].{Key:Key,VersionId:VersionId}}' \
            --output json --profile "${PROFILE:-}")" --profile "${PROFILE:-}" >/dev/null 2>&1 || true
        # Delete any delete markers
        aws s3api delete-objects --bucket "${bucket_name}" \
            --delete "$(aws s3api list-object-versions --bucket "${bucket_name}" \
            --query '{Objects: DeleteMarkers[].{Key:Key,VersionId:VersionId}}' \
            --output json --profile "${PROFILE:-}")" --profile "${PROFILE:-}" >/dev/null 2>&1 || true
        # Finally delete the bucket
        aws s3 rb "s3://${bucket_name}" --profile "${PROFILE:-}" >/dev/null 2>&1 || true
        print_success "Deleted S3 bucket: ${bucket_name}"
    fi
}

# Step 0a: Clean up existing Bedrock agent aliases to prevent conflicts
if [[ "$CLEAN_AGENTS" == "true" ]]; then
    print_status "Step 0a: Cleaning up existing Bedrock agent aliases..."
    
    # Function to safely delete agent alias
    delete_agent_alias() {
        local agent_id="$1"
        local agent_alias_id="$2"
        local agent_name="$3"
        
        if aws bedrock-agent get-agent-alias --agent-id "$agent_id" --agent-alias-id "$agent_alias_id" --region "$REGION" --profile "${PROFILE:-}" >/dev/null 2>&1; then
            print_status "Deleting existing agent alias for $agent_name (Agent ID: $agent_id, Alias ID: $agent_alias_id)"
            aws bedrock-agent delete-agent-alias --agent-id "$agent_id" --agent-alias-id "$agent_alias_id" --region "$REGION" --profile "${PROFILE:-}" >/dev/null 2>&1 || {
                print_warning "Failed to delete agent alias for $agent_name, continuing..."
            }
            print_success "Deleted agent alias for $agent_name"
        else
            print_status "No existing agent alias found for $agent_name"
        fi
    }
    
    # Get list of existing agents and clean up their aliases
    print_status "Scanning for existing Bedrock agents..."
    EXISTING_AGENTS=$(aws bedrock-agent list-agents --region "$REGION" --profile "${PROFILE:-}" --query "agentSummaries[?contains(agentName, 'cfn-generator') || contains(agentName, 'MainframeAnalyzer') || contains(agentName, 'mainframe-analyzer')].{agentId:agentId,agentName:agentName}" --output json 2>/dev/null || echo "[]")
    
    if [[ "$EXISTING_AGENTS" != "[]" ]]; then
        echo "$EXISTING_AGENTS" | jq -r '.[] | "\(.agentId) \(.agentName)"' | while read -r agent_id agent_name; do
            print_status "Checking agent: $agent_name ($agent_id)"
            
            # Get aliases for this agent
            ALIASES=$(aws bedrock-agent list-agent-aliases --agent-id "$agent_id" --region "$REGION" --profile "${PROFILE:-}" --query "agentAliasSummaries[].agentAliasId" --output text 2>/dev/null || echo "")
            
            if [[ -n "$ALIASES" ]]; then
                for alias_id in $ALIASES; do
                    delete_agent_alias "$agent_id" "$alias_id" "$agent_name"
                done
            fi
        done
    else
        print_status "No existing agents found that match our naming patterns"
    fi
    
    print_success "Agent alias cleanup completed"
else
    print_status "Step 0a: Skipping Bedrock agent alias cleanup (--no-clean-agents specified)"
fi

# Step 0b: Clean up and create required S3 buckets
if [[ "$CLEAN_BUCKETS" == "true" ]]; then
    print_status "Step 0b: Cleaning up existing S3 buckets and creating fresh ones..."
else
    print_status "Step 0b: Creating required S3 buckets (skipping cleanup)..."
fi

# Define bucket names
TEMPLATE_BUCKET="mainframe-modernization-templates-${ACCOUNT_ID}-${REGION}"
CFN_LAMBDA_BUCKET="cfn-generator-${ENVIRONMENT}-${ACCOUNT_ID}-${REGION}"
ANALYZER_LAMBDA_BUCKET="mainframe-analyzer-${ENVIRONMENT}-${ACCOUNT_ID}-${REGION}"
TRANSFORM_BUCKET="mainframe-transform-${ENVIRONMENT}-${ACCOUNT_ID}"
PROMPTS_BUCKET="mainframe-modernization-prompts-${ENVIRONMENT}-${ACCOUNT_ID}"

# Delete existing buckets to prevent conflicts (if cleanup enabled)
if [[ "$CLEAN_BUCKETS" == "true" ]]; then
    print_status "Cleaning up existing S3 buckets..."
    delete_s3_bucket "$TEMPLATE_BUCKET"
    delete_s3_bucket "$CFN_LAMBDA_BUCKET"
    delete_s3_bucket "$ANALYZER_LAMBDA_BUCKET"
    # Note: We'll recreate the transform bucket but preserve the layer
    delete_s3_bucket "$TRANSFORM_BUCKET"
    # Delete the prompts bucket created by CloudFormation
    delete_s3_bucket "$PROMPTS_BUCKET"
    
    # Create fresh buckets
    print_status "Creating fresh S3 buckets..."
    
    print_status "Creating S3 bucket for CloudFormation templates: ${TEMPLATE_BUCKET}"
    aws s3 mb "s3://${TEMPLATE_BUCKET}" --region "$REGION" --profile "${PROFILE:-}"
    
    print_status "Creating S3 bucket for CFN Generator Lambda code: ${CFN_LAMBDA_BUCKET}"
    aws s3 mb "s3://${CFN_LAMBDA_BUCKET}" --region "$REGION" --profile "${PROFILE:-}"
    
    print_status "Creating S3 bucket for Mainframe Analyzer Lambda code: ${ANALYZER_LAMBDA_BUCKET}"
    aws s3 mb "s3://${ANALYZER_LAMBDA_BUCKET}" --region "$REGION" --profile "${PROFILE:-}"
    
    print_status "Creating S3 bucket for mainframe transform: ${TRANSFORM_BUCKET}"
    aws s3 mb "s3://${TRANSFORM_BUCKET}" --region "$REGION" --profile "${PROFILE:-}"
else
    # Create buckets only if they don't exist (original behavior)
    if ! aws s3 ls "s3://${TEMPLATE_BUCKET}" --profile "${PROFILE:-}" >/dev/null 2>&1; then
        print_status "Creating S3 bucket for CloudFormation templates: ${TEMPLATE_BUCKET}"
        aws s3 mb "s3://${TEMPLATE_BUCKET}" --region "$REGION" --profile "${PROFILE:-}"
    else
        print_status "S3 bucket for templates already exists: ${TEMPLATE_BUCKET}"
    fi
    
    if ! aws s3 ls "s3://${CFN_LAMBDA_BUCKET}" --profile "${PROFILE:-}" >/dev/null 2>&1; then
        print_status "Creating S3 bucket for CFN Generator Lambda code: ${CFN_LAMBDA_BUCKET}"
        aws s3 mb "s3://${CFN_LAMBDA_BUCKET}" --region "$REGION" --profile "${PROFILE:-}"
    else
        print_status "S3 bucket for CFN Generator Lambda code already exists: ${CFN_LAMBDA_BUCKET}"
    fi
    
    if ! aws s3 ls "s3://${ANALYZER_LAMBDA_BUCKET}" --profile "${PROFILE:-}" >/dev/null 2>&1; then
        print_status "Creating S3 bucket for Mainframe Analyzer Lambda code: ${ANALYZER_LAMBDA_BUCKET}"
        aws s3 mb "s3://${ANALYZER_LAMBDA_BUCKET}" --region "$REGION" --profile "${PROFILE:-}"
    else
        print_status "S3 bucket for Mainframe Analyzer Lambda code already exists: ${ANALYZER_LAMBDA_BUCKET}"
    fi
    
    if ! aws s3 ls "s3://${TRANSFORM_BUCKET}" --profile "${PROFILE:-}" >/dev/null 2>&1; then
        print_status "Creating S3 bucket for mainframe transform: ${TRANSFORM_BUCKET}"
        aws s3 mb "s3://${TRANSFORM_BUCKET}" --region "$REGION" --profile "${PROFILE:-}"
    else
        print_status "S3 bucket for mainframe transform already exists: ${TRANSFORM_BUCKET}"
    fi
fi

# Step 1: Package CloudFormation templates
print_status "Step 1: Packaging CloudFormation templates..."

print_status "Packaging nested CloudFormation templates to S3..."
aws cloudformation package \
    --template-file infrastructure/main.yaml \
    --s3-bucket "${TEMPLATE_BUCKET}" \
    --output-template-file infrastructure/main-packaged.yaml \
    --region "$REGION" \
    --profile "${PROFILE:-}"

if [[ $? -ne 0 ]]; then
    print_error "Failed to package CloudFormation templates"
    exit 1
fi

print_success "CloudFormation templates packaged successfully"

# Step 2: Create and upload PyPDF Lambda Layer
print_status "Step 2a: Creating PyPDF Lambda Layer..."

# Check if layer already exists in S3
if aws s3 ls "s3://${ANALYZER_LAMBDA_BUCKET}/layer/pypdfdocxlayer.zip" --profile "${PROFILE:-}" >/dev/null 2>&1; then
    print_status "PyPDF layer already exists in S3, skipping creation..."
else
    print_status "Creating PyPDF layer..."
    
    # Create PyPDF layer with required dependencies
    LAYER_DIR="/tmp/pypdf_layer_$$"
    mkdir -p "$LAYER_DIR"
    cd "$LAYER_DIR"
    
    print_status "Creating Python virtual environment for layer dependencies..."
    python3 -m venv pypdf_env
    source pypdf_env/bin/activate
    
    print_status "Installing PyPDF layer dependencies..."
    pip install PyPDF2==3.0.1 python-docx==0.8.11 openpyxl==3.1.2 lxml et-xmlfile -t python/ --quiet
    
    print_status "Creating layer zip file..."
    zip -r pypdf_layer.zip python/ >/dev/null 2>&1
    
    print_status "Uploading PyPDF layer to S3..."
    aws s3 cp pypdf_layer.zip "s3://${ANALYZER_LAMBDA_BUCKET}/layer/pypdfdocxlayer.zip" --region "$REGION" --profile "${PROFILE:-}"
    
    # Cleanup
    deactivate
    cd - >/dev/null
    rm -rf "$LAYER_DIR"
    
    print_success "PyPDF Lambda layer created and uploaded successfully"
fi

# Step 2b: Package Lambda functions
print_status "Step 2b: Preparing Lambda deployment packages..."

# FIXED: Package CFN Generator Lambda functions with proper directory context
if [[ -d "services/cfn-generator/src" ]]; then
    print_status "Processing CFN Generator Lambda functions..."
    
    # Check if pre-built packages exist in the service's dist directory
    if [[ -d "services/cfn-generator/dist" ]] && [[ -n "$(ls -A services/cfn-generator/dist/*.zip 2>/dev/null)" ]]; then
        print_status "Found pre-built CFN Generator Lambda packages, uploading to S3..."
        aws s3 cp services/cfn-generator/dist/ "s3://${CFN_LAMBDA_BUCKET}/lambda/" --recursive --region "$REGION" --profile "${PROFILE:-}" || {
            print_error "Failed to upload pre-built CFN Generator Lambda packages"
            exit 1
        }
        
        # Fix naming for packages that need -lambda suffix
        for package in completion generator; do
            if aws s3 ls "s3://${CFN_LAMBDA_BUCKET}/lambda/${package}.zip" --profile "${PROFILE:-}" >/dev/null 2>&1; then
                aws s3 cp "s3://${CFN_LAMBDA_BUCKET}/lambda/${package}.zip" "s3://${CFN_LAMBDA_BUCKET}/lambda/${package}-lambda.zip" --region "$REGION" --profile "${PROFILE:-}" || true
            fi
        done
        print_success "CFN Generator Lambda packages uploaded successfully"
    else
        print_status "No pre-built CFN Generator packages found, creating them manually..."
        
        # Manual packaging for CFN Generator Lambda functions
        cd services/cfn-generator
        mkdir -p dist
        cd src
        for dir in */; do
            if [[ -f "${dir}lambda_function.py" ]]; then
                print_status "Packaging ${dir%/} Lambda function..."
                cd "$dir"
                zip -r "../../dist/${dir%/}.zip" . >/dev/null 2>&1
                cd ..
            fi
        done
        cd ..
        
        # Upload to S3 with correct naming
        print_status "Uploading CFN Generator Lambda packages to S3..."
        aws s3 cp dist/ "s3://${CFN_LAMBDA_BUCKET}/lambda/" --recursive --region "$REGION" --profile "${PROFILE:-}" || {
            print_error "Failed to upload CFN Generator Lambda packages"
            exit 1
        }
        
        # Fix naming for packages that need -lambda suffix
        for package in completion generator; do
            if aws s3 ls "s3://${CFN_LAMBDA_BUCKET}/lambda/${package}.zip" --profile "${PROFILE:-}" >/dev/null 2>&1; then
                aws s3 cp "s3://${CFN_LAMBDA_BUCKET}/lambda/${package}.zip" "s3://${CFN_LAMBDA_BUCKET}/lambda/${package}-lambda.zip" --region "$REGION" --profile "${PROFILE:-}" || true
            fi
        done
        
        cd ../..
        print_success "CFN Generator Lambda packages created and uploaded successfully"
    fi
fi

# FIXED: Package Mainframe Analyzer Lambda functions with proper directory context
if [[ -d "services/mainframe-analyzer/src" ]]; then
    print_status "Processing Mainframe Analyzer Lambda functions..."
    
    # Check if pre-built packages exist in the service's dist directory
    if [[ -d "services/mainframe-analyzer/dist" ]] && [[ -n "$(ls -A services/mainframe-analyzer/dist/*.zip 2>/dev/null)" ]]; then
        print_status "Found pre-built Mainframe Analyzer Lambda packages, uploading to S3..."
        aws s3 cp services/mainframe-analyzer/dist/ "s3://${ANALYZER_LAMBDA_BUCKET}/lambda/" --recursive --region "$REGION" --profile "${PROFILE:-}" || {
            print_error "Failed to upload pre-built Mainframe Analyzer Lambda packages"
            exit 1
        }
        print_success "Mainframe Analyzer Lambda packages uploaded successfully"
    else
        print_status "No pre-built Mainframe Analyzer packages found, creating them manually..."
        
        # Manual packaging for Mainframe Analyzer Lambda functions
        cd services/mainframe-analyzer
        mkdir -p dist
        cd src
        for dir in */; do
            if [[ -f "${dir}lambda_function.py" ]]; then
                print_status "Packaging ${dir%/} Lambda function..."
                # Create a temporary directory for packaging
                TEMP_DIR="/tmp/lambda_package_${dir%/}_$$"
                mkdir -p "$TEMP_DIR"
                
                # Copy the Lambda function files
                cp -r "$dir"* "$TEMP_DIR/"
                
                # Copy the shared directory if it exists and the Lambda function imports it
                if [[ -d "shared" ]] && grep -q "from shared" "${dir}lambda_function.py" 2>/dev/null; then
                    cp -r shared "$TEMP_DIR/"
                fi
                
                # Create the zip package from the current directory
                CURRENT_DIR=$(pwd)
                cd "$TEMP_DIR"
                zip -r "$CURRENT_DIR/../dist/${dir%/}.zip" . >/dev/null 2>&1
                cd "$CURRENT_DIR"
                
                # Cleanup
                rm -rf "$TEMP_DIR"
            fi
        done
        cd ..
        
        # Upload to S3
        print_status "Uploading Mainframe Analyzer Lambda packages to S3..."
        aws s3 cp dist/ "s3://${ANALYZER_LAMBDA_BUCKET}/lambda/" --recursive --region "$REGION" --profile "${PROFILE:-}" || {
            print_error "Failed to upload Mainframe Analyzer Lambda packages"
            exit 1
        }
        
        cd ../..
        print_success "Mainframe Analyzer Lambda packages created and uploaded successfully"
    fi
fi

# Step 3: Deploy the master template with enhanced monitoring
print_status "Step 3: Deploying master CloudFormation template..."

STACK_NAME="${PLATFORM_STACK_NAME}-${ENVIRONMENT}"

# Function to check stack status
check_stack_status() {
    local stack_name="$1"
    aws cloudformation describe-stacks \
        --stack-name "$stack_name" \
        --region "$REGION" \
        --profile "${PROFILE:-}" \
        --query "Stacks[0].StackStatus" \
        --output text 2>/dev/null || echo "STACK_NOT_FOUND"
}

# Check if stack exists and is in a failed state
CURRENT_STATUS=$(check_stack_status "$STACK_NAME")
if [[ "$CURRENT_STATUS" == "ROLLBACK_COMPLETE" || "$CURRENT_STATUS" == "CREATE_FAILED" || "$CURRENT_STATUS" == "UPDATE_ROLLBACK_COMPLETE" ]]; then
    print_warning "Stack $STACK_NAME is in $CURRENT_STATUS state. Deleting before redeployment..."
    aws cloudformation delete-stack --stack-name "$STACK_NAME" --region "$REGION" --profile "${PROFILE:-}"
    
    print_status "Waiting for stack deletion to complete..."
    aws cloudformation wait stack-delete-complete --stack-name "$STACK_NAME" --region "$REGION" --profile "${PROFILE:-}"
    print_success "Stack deleted successfully"
fi

# Function to get stack events (most recent first)
get_stack_events() {
    local stack_name="$1"
    local max_items="${2:-10}"
    aws cloudformation describe-stack-events \
        --stack-name "$stack_name" \
        --region "$REGION" \
        --profile "${PROFILE:-}" \
        --max-items "$max_items" \
        --query "StackEvents[*].[Timestamp,LogicalResourceId,ResourceStatus,ResourceStatusReason]" \
        --output table 2>/dev/null || echo "No events found"
}

# Function to get failed resources
get_failed_resources() {
    local stack_name="$1"
    aws cloudformation describe-stack-events \
        --stack-name "$stack_name" \
        --region "$REGION" \
        --profile "${PROFILE:-}" \
        --query "StackEvents[?contains(ResourceStatus, 'FAILED')].[LogicalResourceId,ResourceStatus,ResourceStatusReason,Timestamp]" \
        --output table 2>/dev/null
}

# Start deployment
print_status "Starting CloudFormation deployment..."
aws cloudformation deploy \
    --template-file infrastructure/main-packaged.yaml \
    --stack-name "$STACK_NAME" \
    --parameter-overrides \
        Environment="$ENVIRONMENT" \
        FoundationModel="us.anthropic.claude-3-7-sonnet-20250219-v1:0" \
        IdleSessionTTL=600 \
        DeployServices="both" \
        LambdaCodeBucket="" \
    --capabilities CAPABILITY_NAMED_IAM \
    --region "$REGION" \
    --profile "${PROFILE:-}" \
    --no-fail-on-empty-changeset &

DEPLOY_PID=$!

# Monitor deployment progress
print_status "Monitoring deployment progress..."
LAST_STATUS=""
DOTS_COUNT=0

while kill -0 $DEPLOY_PID 2>/dev/null; do
    CURRENT_STATUS=$(check_stack_status "$STACK_NAME")
    
    if [[ "$CURRENT_STATUS" != "$LAST_STATUS" ]]; then
        if [[ "$CURRENT_STATUS" != "STACK_NOT_FOUND" ]]; then
            print_status "Stack Status: $CURRENT_STATUS"
        fi
        LAST_STATUS="$CURRENT_STATUS"
        DOTS_COUNT=0
    else
        # Print progress dots
        echo -n "."
        DOTS_COUNT=$((DOTS_COUNT + 1))
        if [[ $DOTS_COUNT -ge 60 ]]; then
            echo ""
            DOTS_COUNT=0
        fi
    fi
    
    sleep 5
done

# Wait for the deployment command to complete and get its exit code
wait $DEPLOY_PID
DEPLOY_EXIT_CODE=$?

echo "" # New line after dots

# Check final status
FINAL_STATUS=$(check_stack_status "$STACK_NAME")
print_status "Final Stack Status: $FINAL_STATUS"

if [[ $DEPLOY_EXIT_CODE -eq 0 ]]; then
    case "$FINAL_STATUS" in
        "CREATE_COMPLETE"|"UPDATE_COMPLETE")
            print_success "Platform deployed successfully!"
            ;;
        *)
            print_warning "Deployment command succeeded but stack status is: $FINAL_STATUS"
            ;;
    esac
else
    print_error "CloudFormation deployment failed!"
    print_error "Final Stack Status: $FINAL_STATUS"
    
    case "$FINAL_STATUS" in
        "CREATE_FAILED"|"UPDATE_FAILED"|"ROLLBACK_COMPLETE"|"UPDATE_ROLLBACK_COMPLETE")
            print_error "=== DEPLOYMENT FAILURE DETAILS ==="
            print_error "Recent Stack Events:"
            get_stack_events "$STACK_NAME" 15
            
            print_error ""
            print_error "Failed Resources:"
            get_failed_resources "$STACK_NAME"
            
            print_error ""
            print_error "Checking IAM permissions:"
            aws iam get-user --profile "${PROFILE:-}" || print_error "Unable to get IAM user information"
            
            print_error ""
            print_error "To get more details, run:"
            print_error "aws cloudformation describe-stack-events --stack-name $STACK_NAME --region $REGION --profile ${PROFILE:-}"
            ;;
        *)
            print_error "Unexpected stack status. Check the AWS Console for more details."
            ;;
    esac
    
    exit 1
fi

# Step 4: Get deployment outputs
print_status "Step 4: Retrieving deployment information..."

# Get Supervisor Agent information
SUPERVISOR_AGENT_ID=$(aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME" \
    --region "$REGION" \
    --profile "${PROFILE:-}" \
    --query "Stacks[0].Outputs[?OutputKey=='SupervisorAgentId'].OutputValue" \
    --output text 2>/dev/null || echo "Not found")

SUPERVISOR_AGENT_ALIAS_ID=$(aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME" \
    --region "$REGION" \
    --profile "${PROFILE:-}" \
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
echo "=== S3 BUCKETS CREATED ==="
echo "Templates: ${TEMPLATE_BUCKET}"
echo "CFN Generator Lambda: ${CFN_LAMBDA_BUCKET}"
echo "Mainframe Analyzer Lambda: ${ANALYZER_LAMBDA_BUCKET}"
echo "Transform Data: ${TRANSFORM_BUCKET}"
echo "AI Prompts: ${PROMPTS_BUCKET}"
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
echo "• 'Analyze mainframe documentation in s3://${TRANSFORM_BUCKET}/sample-docs/'"
echo "• 'Check the status of job 12345'"
echo ""
echo "=== SAMPLE FILES UPLOADED ==="
echo "Ready-to-test mainframe documentation:"
echo "• s3://${TRANSFORM_BUCKET}/sample-docs/CBACT01C-cbl-0.4.4.pdf (COBOL program)"
echo "• s3://${TRANSFORM_BUCKET}/sample-docs/READACCT-jcl-0.4.4.pdf (JCL job)"
echo ""
print_success "Platform deployment completed successfully!"

# Upload AI prompts to the prompts bucket
print_status "Uploading AI prompts to S3..."
upload_prompts_to_s3() {
    local prompts_dir="./prompts"
    
    if [ ! -d "$prompts_dir" ]; then
        print_warning "Prompts directory not found: $prompts_dir"
        return 1
    fi
    
    print_status "Uploading analysis-agent prompts (shared by Analysis & Chunk Processor Lambda functions)..."
    
    # Upload analysis agent prompts
    aws s3 cp "$prompts_dir/analysis-agent/python-prompt.txt" "s3://$PROMPTS_BUCKET/analysis-agent/python-prompt.txt" \
        --content-type "text/plain" --region "$REGION" --profile "${PROFILE:-}" || {
        print_warning "Failed to upload python-prompt.txt"
    }
    
    aws s3 cp "$prompts_dir/analysis-agent/dotnet-prompt.txt" "s3://$PROMPTS_BUCKET/analysis-agent/dotnet-prompt.txt" \
        --content-type "text/plain" --region "$REGION" --profile "${PROFILE:-}" || {
        print_warning "Failed to upload dotnet-prompt.txt"
    }
    
    aws s3 cp "$prompts_dir/analysis-agent/java-prompt.txt" "s3://$PROMPTS_BUCKET/analysis-agent/java-prompt.txt" \
        --content-type "text/plain" --region "$REGION" --profile "${PROFILE:-}" || {
        print_warning "Failed to upload java-prompt.txt"
    }
    
    aws s3 cp "$prompts_dir/analysis-agent/go-prompt.txt" "s3://$PROMPTS_BUCKET/analysis-agent/go-prompt.txt" \
        --content-type "text/plain" --region "$REGION" --profile "${PROFILE:-}" || {
        print_warning "Failed to upload go-prompt.txt"
    }
    
    aws s3 cp "$prompts_dir/analysis-agent/javascript-prompt.txt" "s3://$PROMPTS_BUCKET/analysis-agent/javascript-prompt.txt" \
        --content-type "text/plain" --region "$REGION" --profile "${PROFILE:-}" || {
        print_warning "Failed to upload javascript-prompt.txt"
    }
    
    aws s3 cp "$prompts_dir/analysis-agent/default-prompt.txt" "s3://$PROMPTS_BUCKET/analysis-agent/default-prompt.txt" \
        --content-type "text/plain" --region "$REGION" --profile "${PROFILE:-}" || {
        print_warning "Failed to upload default-prompt.txt"
    }
    
    # Upload template files if they exist
    if [ -d "$prompts_dir/templates" ]; then
        print_status "Uploading template files..."
        aws s3 sync "$prompts_dir/templates/" "s3://$PROMPTS_BUCKET/templates/" \
            --content-type "text/plain" --region "$REGION" --profile "${PROFILE:-}" || {
            print_warning "Failed to upload template files"
        }
    fi
    
    print_success "AI prompts uploaded successfully to: s3://$PROMPTS_BUCKET/"
}

# Call the prompt upload function
upload_prompts_to_s3

# Upload sample mainframe documentation files for testing
print_status "Uploading sample mainframe documentation files for testing..."

if [[ -d "tests/mainframe-docs" ]]; then
    # Upload sample files to the transform bucket for immediate testing
    aws s3 cp tests/mainframe-docs/ "s3://${TRANSFORM_BUCKET}/sample-docs/" --recursive --region "$REGION" --profile "${PROFILE:-}" || {
        print_warning "Failed to upload sample documentation files"
    }
    print_success "Sample mainframe documentation uploaded to: s3://${TRANSFORM_BUCKET}/sample-docs/"
else
    print_warning "No sample documentation found in tests/mainframe-docs/ directory"
fi

# Optional: Run basic health checks
print_status "Running basic health checks..."

# Check if stacks are in CREATE_COMPLETE or UPDATE_COMPLETE state
STACK_STATUS=$(aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME" \
    --region "$REGION" \
    --profile "${PROFILE:-}" \
    --query "Stacks[0].StackStatus" \
    --output text 2>/dev/null || echo "UNKNOWN")

if [[ "$STACK_STATUS" == "CREATE_COMPLETE" || "$STACK_STATUS" == "UPDATE_COMPLETE" ]]; then
    print_success "Stack status: $STACK_STATUS"
else
    print_warning "Stack status: $STACK_STATUS"
fi

# Clean up dist folders to ensure fresh builds on next deployment
print_status "Cleaning up deployment packages to ensure fresh builds next time..."
if [ -d "services/cfn-generator/dist" ]; then
    rm -rf services/cfn-generator/dist
    print_success "Cleaned up CFN Generator dist folder"
fi

if [ -d "services/mainframe-analyzer/dist" ]; then
    rm -rf services/mainframe-analyzer/dist
    print_success "Cleaned up Mainframe Analyzer dist folder"
fi

print_success "Deployment script completed!"
