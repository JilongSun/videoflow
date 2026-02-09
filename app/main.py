# 加载 .env 文件中的环境变量
import os
from dotenv import load_dotenv

load_dotenv()
from videoflow.utils import log
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .routers import util_routers
from videoflow.feishu import amain
import uvicorn


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("启动fastapi应用")
    log.info("启动飞书连接端口")
    await amain()
    log.info("飞书连接端口启动成功")
    yield
    print("关闭应用")


app = FastAPI(
    title="VideoFlow API",
    description="A FastAPI application for VideoFlow project",
    version="1.0.0",
    lifespan=lifespan,
)


# 包含路由
app.include_router(util_routers)


@app.get("/")
async def root():
    return {"message": "Welcome to VideoFlow API"}
