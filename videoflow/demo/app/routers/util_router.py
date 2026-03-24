from fastapi import APIRouter
from fastapi.responses import FileResponse
from videoflow.utils.file_processor import (
    write_file,
    get_file_path,
    file_processor_provider,
)
from videoflow.utils.crawlers.crawler import crawler
from videoflow.demo.app.models.router_model import WriteFileRequest, ReadFileRequest, SearchVideoRequest
from videoflow.utils import log

__all__ = ["router"]

router = APIRouter(prefix="/util", tags=["工具路由"])


@router.post("/write-file")
async def write_file_endpoint(request: WriteFileRequest):
    log.info(
        f"写文件接口接受参数: 文件名：{request.file_name}, 内容：{request.content if len(request.content) < 10 else request.content[:10]}, 类型: {type(request.content)}"
    )
    res = await write_file(request.file_name, request.content, request.path)
    if res:
        return {"message": "File writing success"}
    else:
        return {"message": "File writing failed"}


@router.post("/read-file")
async def read_file_endpoint(request: ReadFileRequest):
    log.info(f"读文件接口接受参数: 文件名：{request.file_name}, 路径：{request.path}")
    path = await get_file_path(request.file_name, request.path)
    return FileResponse(path, media_type="image/jpeg")


@router.post("/search-video")
async def search_video_endpoint(request: SearchVideoRequest):
    log.info(
        f"搜索视频接口接受参数: 关键词：{request.keyword}, 发布时间：{request.publish_time}"
    )
    list_url = await crawler.search_video(request.keyword, request.publish_time)
    if list_url:
        return {"message": "Video search success", "list_url": list_url}
    else:
        return {"message": "Video search failed", "list_url": None}


@router.post("/upload-file", deprecated=True)
async def upload_file_endpoint(request: ReadFileRequest):
    """通过ait8上传文件然后获得url"""
    log.info(f"上传文件接口接受参数: 文件名：{request.file_name}, 路径：{request.path}")
    tf = file_processor_provider.get_processor(request.file_name)
    res = await tf.get_url(request.file_name)
    if res:
        return {"message": "File upload success", "url": res}
    else:
        return {"message": "File upload failed", "url": None}
