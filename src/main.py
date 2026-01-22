from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.api.routes import router, agent


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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)