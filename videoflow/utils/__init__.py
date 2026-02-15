from .logger_config import log
from pathlib import Path
import sys, os

# 将 downloader 目录添加到 Python 路径中
downloader_path = str(Path(__file__).parent)
sys.path.insert(0, downloader_path)
