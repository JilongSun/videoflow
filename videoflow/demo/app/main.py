import os
from dotenv import load_dotenv

load_dotenv()
from videoflow.utils import log
from contextlib import asynccontextmanager
from fastapi import FastAPI
from .routers import util_routers, chat_routers
from videoflow.demo.feishu import amain


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("启动 Demo FastAPI 应用")
    log.info("启动飞书连接端口")
    await amain()
    log.info("飞书连接端口启动成功")
    yield
    log.info("关闭应用")


app = FastAPI(
    title="VideoFlow Demo API",
    description="VideoFlow Demo - 飞书集成测试",
    version="2.0.0",
    lifespan=lifespan,
)

app.include_router(util_routers)
app.include_router(chat_routers)


@app.get("/")
async def root():
    return {"message": "Welcome to VideoFlow Demo API"}
