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
from fastapi.responses import RedirectResponse
from viewer.api.routes import router

app = FastAPI(
    title="Content Analysis Viewer",
    description="ES 분석 결과 조회 서비스",
    version="0.1.0"
)

# 루트 경로에서 /viewer/로 리다이렉트
@app.get("/", include_in_schema=False)
async def root():
    return RedirectResponse(url="/viewer/")

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
    uvicorn.run("viewer.main:app", host="0.0.0.0", port=8787, reload=True)
