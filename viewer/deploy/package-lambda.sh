#!/bin/bash
#
# Lambda 패키징 스크립트 (Docker 사용)
#
# 사전 확인 (필수):
#   - Lambda 런타임 버전과 Docker 이미지 버전 일치 필요 (예: Python 3.12)
#   - Lambda 아키텍처 확인: 콘솔 → 함수 → 일반 구성 → 아키텍처
#
# 사용법:
#   ./deploy/package-lambda.sh
#   ./deploy/package-lambda.sh arm64  # arm64 Lambda인 경우
#

set -e  # 에러 발생 시 중단

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VIEWER_DIR="$(dirname "$SCRIPT_DIR")"
CONTAINER_NAME="lambda-build"
OUTPUT_FILE="lambda-package.zip"

# 아키텍처 설정 (기본값: x86_64)
ARCH="${1:-amd64}"
if [ "$ARCH" = "arm64" ]; then
    PLATFORM="linux/arm64"
else
    PLATFORM="linux/amd64"
fi

echo "=== Lambda 패키징 시작 ==="
echo "플랫폼: $PLATFORM"
echo "작업 디렉토리: $VIEWER_DIR"

cd "$VIEWER_DIR"

# 1. 초기화
echo ""
echo "[1/5] 초기화..."
rm -rf "$OUTPUT_FILE"
docker rm -f "$CONTAINER_NAME" 2>/dev/null || true

# 2. Lambda 런타임 컨테이너 생성
echo ""
echo "[2/5] Lambda 런타임 컨테이너 생성..."
docker run -d --name "$CONTAINER_NAME" --platform "$PLATFORM" --entrypoint tail \
    public.ecr.aws/lambda/python:3.12 -f /dev/null

# 3. 의존성 설치
echo ""
echo "[3/5] 의존성 설치..."
docker exec "$CONTAINER_NAME" pip install \
    fastapi jinja2 'pydantic>=2.0.0' pydantic-settings \
    python-dotenv 'elasticsearch>=8.0.0,<9.0.0' requests 'mangum>=0.17.0' \
    --target /tmp/package

# 4. viewer 코드 복사 + zip 생성
echo ""
echo "[4/5] viewer 코드 복사 및 zip 생성..."
docker cp viewer "$CONTAINER_NAME":/tmp/package/

docker exec "$CONTAINER_NAME" python -c "
import zipfile, os
with zipfile.ZipFile('/tmp/lambda-package.zip', 'w', zipfile.ZIP_DEFLATED) as zf:
    for root, dirs, files in os.walk('/tmp/package'):
        dirs[:] = [d for d in dirs if '__pycache__' not in d and 'streamlit' not in d and '.dist-info' not in d and '.egg-info' not in d]
        for file in files:
            filepath = os.path.join(root, file)
            arcname = os.path.relpath(filepath, '/tmp/package')
            zf.write(filepath, arcname)
"

# 5. zip 추출 및 정리
echo ""
echo "[5/5] zip 파일 추출 및 정리..."
docker cp "$CONTAINER_NAME":/tmp/lambda-package.zip "./$OUTPUT_FILE"
docker rm -f "$CONTAINER_NAME"

# 결과 확인
echo ""
echo "=== 패키징 완료 ==="
echo ""
echo "zip 내용 확인:"
unzip -l "$OUTPUT_FILE" | grep -E "fastapi/|viewer/main" | head -5
echo ""
ls -lh "$OUTPUT_FILE"
echo ""
echo "Lambda 콘솔에서 $OUTPUT_FILE 파일을 업로드하세요."
