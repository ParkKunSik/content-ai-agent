from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.api.routes import agent, router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize the agent
    agent.set_up()
    yield
    # Shutdown: Clean up resources if needed (e.g., close DB connections)
    # agent.tear_down()


app = FastAPI(
    title="Content Analysis AI Agent (Local Wrapper)",
    lifespan=lifespan
)

# Register API Router
app.include_router(router)


# AWS Lambda handler (mangum)
# pip install -e ".[lambda]" 로 설치 필요
try:
    from mangum import Mangum
    handler = Mangum(app, lifespan="off")
except ImportError:
    # mangum이 설치되지 않은 경우 (로컬 개발 환경)
    handler = None


if __name__ == "__main__":
    import uvicorn
    from src.core.config import settings
    uvicorn.run(app, host=settings.SERVER_HOST, port=settings.SERVER_PORT)
