from loguru import logger
import sys, os
from pathlib import Path
from typing import Optional


class LoggerConfig:
    """
    基于loguru的日志配置类
    """
    
    def __init__(self, 
                 log_dir: str = "logs", 
                 log_level: str = "INFO",
                 rotation: str = "10 MB",
                 retention: str = "7 days",
                 format: str = "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
                 serialize: bool = False):
        """
        初始化日志配置
        
        Args:
            log_dir: 日志存储目录
            log_level: 日志级别
            rotation: 日志轮转大小
            retention: 日志保留时间
            format: 日志格式
            serialize: 是否序列化输出
        """
        self.log_dir = Path(log_dir)
        self.log_level = log_level
        self.rotation = rotation
        self.retention = retention
        self.format = format
        self.serialize = serialize
        
        # 创建日志目录
        self.log_dir.mkdir(exist_ok=True)
        
        # 配置日志
        self.setup_logger()
    
    def setup_logger(self):
        """配置日志记录器"""
        # 移除默认的sink
        logger.remove()
        
        # 添加控制台输出
        logger.add(
            sys.stdout,
            level=self.log_level,
            format=self.format,
            colorize=True,
            backtrace=True,
            diagnose=True
        )
        
        # 添加文件输出（每天一个文件，保留7天）
        logger.add(
            self.log_dir / "app_{time:YYYY-MM-DD}.log",
            level=self.log_level,
            format=self.format,
            rotation="00:00",  # 每天午夜轮转
            retention=self.retention,
            compression="zip",
            serialize=self.serialize,
            encoding="utf-8"
        )
        
        # 添加错误日志文件
        logger.add(
            self.log_dir / "error_{time:YYYY-MM-DD}.log",
            level="ERROR",
            format=self.format,
            rotation=self.rotation,
            retention=self.retention,
            compression="zip",
            serialize=self.serialize,
            encoding="utf-8"
        )
    
    def get_logger(self):
        """获取配置好的logger实例"""
        return logger


# 全局日志实例
log_config = LoggerConfig()
log = log_config.get_logger()


# 便捷的日志记录函数
def get_logger(name: Optional[str] = None):
    """
    获取日志记录器
    
    Args:
        name: 记录器名称，如果为None则返回全局记录器
    """
    if name:
        return logger.bind(name=name)
    return logger


# 示例用法
if __name__ == "__main__":
    # 使用全局日志记录器
    log.info("这是信息日志")
    log.debug("这是调试日志")
    log.warning("这是警告日志")
    log.error("这是错误日志")
    
    # 使用带名称的日志记录器
    named_logger = get_logger("MyApp")
    named_logger.info("来自MyApp的信息")
    
    try:
        raise
    except:
        log.exception("捕获到异常")