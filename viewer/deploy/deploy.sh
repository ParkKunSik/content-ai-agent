#!/bin/bash
# Content Viewer - AWS SAM 배포 스크립트
#
# 사용법:
#   ./deploy/deploy.sh
#
# 예시:
#   ./deploy/deploy.sh          # dev 환경 배포

set -e

# 스크립트 디렉토리 기준으로 viewer 루트로 이동
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VIEWER_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$VIEWER_ROOT"

# 환경 설정 (기본값: dev)
ENVIRONMENT="${1:-dev}"

echo "=========================================="
echo "Content Viewer - AWS Lambda 배포"
echo "=========================================="
echo "환경: $ENVIRONMENT"
echo "디렉토리: $VIEWER_ROOT"
echo ""

# AWS SAM CLI 확인
if ! command -v sam &> /dev/null; then
    echo "Error: AWS SAM CLI가 설치되어 있지 않습니다."
    echo "설치: https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html"
    exit 1
fi

# requirements.txt 생성 (SAM 빌드용, pyproject.toml 기반)
echo "1. requirements.txt 생성 중 (pyproject.toml 기반)..."
pip install pip-tools -q 2>/dev/null || true
if command -v pip-compile &> /dev/null; then
    pip-compile pyproject.toml -o requirements.txt --extra lambda -q
else
    # pip-tools 없으면 기본 의존성 사용
    cat > requirements.txt << 'EOF'
fastapi
jinja2
pydantic>=2.0.0
pydantic-settings
python-dotenv
elasticsearch>=8.0.0,<9.0.0
requests
mangum>=0.17.0
EOF
fi

echo "2. SAM 빌드 중..."
sam build \
    --template-file deploy/template.yaml \
    --config-env "$ENVIRONMENT"

echo "3. SAM 배포 중..."
sam deploy \
    --template-file deploy/template.yaml \
    --config-env "$ENVIRONMENT" \
    --no-fail-on-empty-changeset

# requirements.txt 정리 (빌드 후 삭제)
rm -f requirements.txt

echo ""
echo "=========================================="
echo "배포 완료!"
echo "=========================================="

# 배포된 API URL 출력
STACK_NAME="content-viewer-$ENVIRONMENT"
API_URL=$(aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME" \
    --query "Stacks[0].Outputs[?OutputKey=='ViewerApiUrl'].OutputValue" \
    --output text 2>/dev/null || echo "N/A")

echo "API URL: $API_URL"
echo ""
