from pydantic import BaseModel, Field
from typing import Optional, Annotated, Union

url = Annotated[str, "文件URL"]
bin_url = Annotated[bytes, "二进制文件URL"]
file_content = Union[url, bin_url]


class WriteFileRequest(BaseModel):
    file_name: str = Field(..., description="要写入的文件名")
    content: file_content = Field(
        ..., description="要写入的文件内容,可以是URL或二进制内容"
    )
    path: Optional[str] = Field(None, description="要写入的文件路径,非必须")


class ReadFileRequest(BaseModel):
    file_name: str = Field(..., description="要读取的文件名")
    path: Optional[str] = Field(None, description="要读取的文件路径,非必须")
