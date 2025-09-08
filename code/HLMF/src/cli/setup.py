"""
Module that sets up CLI functions
"""
#这是一个模块级别的文档字符串，说明该模块的功能是设置 CLI（命令行界面）相关的功能。
#设置 Python 的日志记录（logging）系统，以便在程序运行时记录信息、警告或错误。
import os
import sys
import logging
from typing import Optional

def setup_logging(log_level: int = logging.INFO, log_file: Optional[str] = None) -> None:
    """
    Set up logging

    Args:
        log_level: Logging level
        log_file: Path to the log file (optional)#日志文件的路径（可选），如果未提供，则不会将日志写入文件。
    """
    # Create logs directory if needed
    if log_file:
        log_dir = os.path.dirname(log_file)
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)

    # Log format
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    date_format = '%Y-%m-%d %H:%M:%S'

    # Configure logging#配置日志
    logging.basicConfig(
        level=log_level,
        format=log_format,
        datefmt=date_format,
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(log_file) if log_file else logging.NullHandler()
        ]
    )
    #初始化日志记录器
    logger = logging.getLogger('setup')
    logger.info(f"Logging initialized with level {logging.getLevelName(log_level)}")

    # Suppress unnecessary logs from third-party libraries#抑制第三方库的日志
    #将 urllib3 和 requests 库的日志级别设置为 WARNING，以减少不必要的日志输出（默认情况下，这些库可能会输出大量 INFO 级别的日志）。
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('requests').setLevel(logging.WARNING)
