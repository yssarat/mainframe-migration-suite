#!/bin/bash

# Validation script for Mainframe Modernization Platform
# This script checks for hardcoded account numbers and validates deployment artifacts

set -e

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

# Change to script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."

print_status "Starting validation of Mainframe Modernization Platform..."

# Check 1: Validate no hardcoded account numbers
print_status "Check 1: Validating no hardcoded account numbers..."

HARDCODED_ACCOUNTS=$(find . -name "*.yaml" -o -name "*.yml" -o -name "*.json" -o -name "*.sh" | \
    xargs grep -l "[0-9]\{12\}" 2>/dev/null | \
    xargs grep -l "arn:aws:" 2>/dev/null || true)

if [[ -n "$HARDCODED_ACCOUNTS" ]]; then
    print_error "Found hardcoded account numbers in the following files:"
    echo "$HARDCODED_ACCOUNTS"
    exit 1
else
    print_success "No hardcoded account numbers found"
fi

# Check 2: Validate CloudFormation templates
print_status "Check 2: Validating CloudFormation templates..."

TEMPLATES=(
    "infrastructure/combined-mainframe-modernization-agents.yaml"
    "infrastructure/cfn-generator-service.yaml"
    "infrastructure/mainframe-analyzer-service.yaml"
    "infrastructure/main.yaml"
)

for template in "${TEMPLATES[@]}"; do
    if [[ -f "$template" ]]; then
        print_status "Validating $template..."
        aws cloudformation validate-template --template-body file://"$template" > /dev/null 2>&1
        if [[ $? -eq 0 ]]; then
            print_success "✓ $template is valid"
        else
            print_error "✗ $template is invalid"
            exit 1
        fi
    else
        print_warning "Template $template not found"
    fi
done

# Check 3: Validate required files exist
print_status "Check 3: Validating required files exist..."

REQUIRED_FILES=(
    "README.md"
    "requirements.txt"
    ".gitignore"
    "LICENSE"
    "CONTRIBUTING.md"
    "scripts/deploy-all.sh"
    "scripts/deploy-service.sh"
    "infrastructure/combined-mainframe-modernization-agents.yaml"
    "infrastructure/main.yaml"
)

for file in "${REQUIRED_FILES[@]}"; do
    if [[ -f "$file" ]]; then
        print_success "✓ $file exists"
    else
        print_error "✗ Required file $file is missing"
        exit 1
    fi
done

# Check 4: Validate script permissions
print_status "Check 4: Validating script permissions..."

EXECUTABLE_SCRIPTS=(
    "scripts/deploy-all.sh"
    "scripts/deploy-service.sh"
    "scripts/validate-deployment.sh"
)

for script in "${EXECUTABLE_SCRIPTS[@]}"; do
    if [[ -x "$script" ]]; then
        print_success "✓ $script is executable"
    else
        print_warning "⚠ $script is not executable, fixing..."
        chmod +x "$script"
        print_success "✓ Fixed permissions for $script"
    fi
done

# Check 5: Validate service structure
print_status "Check 5: Validating service structure..."

SERVICES=("cfn-generator" "mainframe-analyzer")

for service in "${SERVICES[@]}"; do
    SERVICE_DIR="services/$service"
    if [[ -d "$SERVICE_DIR" ]]; then
        print_success "✓ Service $service directory exists"
        
        # Check for required service components
        if [[ -d "$SERVICE_DIR/src" ]]; then
            print_success "  ✓ $service source code exists"
        else
            print_warning "  ⚠ $service source code directory missing"
        fi
        
        if [[ -f "$SERVICE_DIR/README.md" ]]; then
            print_success "  ✓ $service documentation exists"
        else
            print_warning "  ⚠ $service README.md missing"
        fi
    else
        print_error "✗ Service $service directory missing"
        exit 1
    fi
done

# Check 6: Validate AWS CLI configuration
print_status "Check 6: Validating AWS CLI configuration..."

if command -v aws &> /dev/null; then
    print_success "✓ AWS CLI is installed"
    
    # Check if AWS credentials are configured
    if aws sts get-caller-identity > /dev/null 2>&1; then
        ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
        REGION=$(aws configure get region)
        print_success "✓ AWS credentials configured (Account: $ACCOUNT_ID, Region: $REGION)"
    else
        print_warning "⚠ AWS credentials not configured or invalid"
    fi
else
    print_error "✗ AWS CLI is not installed"
    exit 1
fi

# Check 7: Validate parameter substitution in templates
print_status "Check 7: Validating parameter substitution in templates..."

# Check that templates use AWS pseudo parameters instead of hardcoded values
PSEUDO_PARAM_USAGE=$(grep -r "\${AWS::AccountId}\|\${AWS::Region}" infrastructure/ | wc -l)

if [[ $PSEUDO_PARAM_USAGE -gt 0 ]]; then
    print_success "✓ Templates use AWS pseudo parameters ($PSEUDO_PARAM_USAGE occurrences)"
else
    print_warning "⚠ Templates may not be using AWS pseudo parameters"
fi

# Summary
print_success "=== VALIDATION COMPLETE ==="
echo ""
echo "Platform validation completed successfully!"
echo ""
echo "=== NEXT STEPS ==="
echo "1. Deploy the platform: ./scripts/deploy-all.sh --region us-east-1 --env dev"
echo "2. Or deploy individual services: ./scripts/deploy-service.sh --service bedrock-agents --region us-east-1 --env dev"
echo "3. Monitor deployment in CloudFormation console"
echo ""
print_success "Platform is ready for deployment!"
