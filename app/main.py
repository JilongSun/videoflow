from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .routers import util_routers
import uvicorn

app = FastAPI(
    title="VideoFlow API",
    description="A FastAPI application for VideoFlow project",
    version="1.0.0"
)


# 包含路由
app.include_router(util_routers)

@app.get("/")
async def root():
    return {"message": "Welcome to VideoFlow API"}

