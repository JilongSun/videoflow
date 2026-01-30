from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse, FileResponse
from videoflow.utils.file_processor import write_file, read_file, get_file_path
from ..models.router_model import WriteFileRequest, ReadFileRequest
from videoflow.utils import log

__all__ = ["router"]


router = APIRouter(prefix="/util", tags=["工具路由"])


@router.post("/write-file")
async def write_file_endpoint(request: WriteFileRequest):
    log.info(
        f"写文件接口接受参数: 文件名：{request.file_name}, 内容：{request.content if len(request.content) < 10 else request.content[:10]}, 类型: {type(request.content)}"
    )
    res = await write_file(request.file_name, request.content, request.path)
    print("write函数执行完毕")
    if res:
        return {"message": "File writing success"}
    else:
        return {"message": "File writing failed"}


@router.post("/read-file")
async def read_file_endpoint(
    request: ReadFileRequest,
):
    log.info(f"读文件接口接受参数: 文件名：{request.file_name}, 路径：{request.path}")
    path = await get_file_path(request.file_name, request.path)
    return FileResponse(path, media_type="image/jpeg")
