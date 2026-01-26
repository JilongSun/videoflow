from pydantic import BaseModel, Field
from typing import Optional, Annotated, Union

url = Annotated[str, "文件URL"]
base64 = Annotated[str, "base64编码后的文件内容"]
filesystem_v2 = Annotated[str, "filesystem-v2是n8n二进制数据管理系统中的一个存储标识符"]
file_content = Union[url, base64, filesystem_v2]

class WriteFileRequest(BaseModel):
    file_name: str = Field(..., description="要写入的文件名")
    content: file_content = Field(
        ..., description="要写入的文件内容,可以是URL或base64编码后的内容"
    )
    path: Optional[str] = Field(None, description="要写入的文件路径,非必须")


class ReadFileRequest(BaseModel):
    file_name: str = Field(..., description="要读取的文件名")
    path: Optional[str] = Field(None, description="要读取的文件路径,非必须")
