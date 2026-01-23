from pydantic import BaseModel, Field
from typing import Optional


class WriteFileRequest(BaseModel):
    file_name: str = Field(..., description="要写入的文件名")
    content: bytes = Field(..., description="要写入的文件内容")
    path: Optional[str] = Field(None, description="要写入的文件路径,非必须")


class ReadFileRequest(BaseModel):
    file_name: str = Field(..., description="要读取的文件名")
    path: str = Field(..., description="要读取的文件路径")
    path: Optional[str] = Field(None, description="要读取的文件路径,非必须")
