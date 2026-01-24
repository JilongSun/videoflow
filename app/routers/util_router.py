from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse, FileResponse
from ..utils.file_processor.provider import write_file, read_file, get_file_path
from ..models.router_model import WriteFileRequest, ReadFileRequest

__all__: list[str] = ["router"]


router = APIRouter(prefix="/util", tags=["工具路由"])


@router.post("/write-file")
async def write_file_endpoint(request: WriteFileRequest):
    print('要保存的文件内容',request.content, type(request.content))
    res = await write_file(request.file_name, request.content, request.path)
    print('write函数执行完毕')
    if res:
        return {"message": "File writing success"}
    else:
        return {"message": "File writing failed"}


@router.post("/read-file")
async def read_file_endpoint(
    request: ReadFileRequest,
):
    path = await get_file_path(request.file_name, request.path)
    return FileResponse(path, media_type="image/jpeg")
