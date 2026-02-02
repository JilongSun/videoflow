from .logger_config import log
import sys, os

# 将 downloader 目录添加到 Python 路径中
downloader_path = os.path.join(os.path.dirname(__file__), "downloader")
print(downloader_path)
sys.path.insert(0, downloader_path)
