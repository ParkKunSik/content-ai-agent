"""
Content Analysis Viewer - FastAPI Application

로컬 실행 (viewer 디렉토리에서):
    cd viewer
    pip install -e ".[server]"
    uvicorn viewer.main:app --reload --port 8787

Lambda 배포:
    handler = viewer.main:handler
"""

import sys
from pathlib import Path

# viewer 패키지 경로를 sys.path에 추가 (IDE 직접 실행 지원)
_viewer_root = Path(__file__).parent.parent
if str(_viewer_root) not in sys.path:
    sys.path.insert(0, str(_viewer_root))

from fastapi import FastAPI
from viewer.api.routes import router

app = FastAPI(
    title="Content Analysis Viewer",
    description="ES 분석 결과 조회 서비스",
    version="0.1.0",
    redirect_slashes=False  # Lambda 환경에서 trailing slash 리다이렉션 루프 방지
)


# API Router 등록
app.include_router(router)


# AWS Lambda handler (Mangum)
try:
    from mangum import Mangum
    handler = Mangum(app, lifespan="off")
except ImportError:
    handler = None


if __name__ == "__main__":
    import uvicorn
    from viewer.config import settings
    uvicorn.run("viewer.main:app", host=settings.SERVER_HOST, port=settings.SERVER_PORT, reload=True)
