"""
Utility functions for TikHub Downloader
"""

import datetime
import os
import platform
import re
import subprocess
import urllib.parse
from urllib.parse import urlparse, parse_qs, urlunparse, urlencode


def sanitize_filename(name, max_length=255):
    """Remove invalid characters from filename and limit length

    Args:
        name: The original filename
        max_length: Maximum length of the filename

    Returns:
        str: Sanitized filename
    """
    # Remove characters not allowed in filenames
    sanitized = re.sub(r'[\\/*?:"<>|]', "", name)

    # Trim whitespace
    sanitized = sanitized.strip()

    # Limit length
    if max_length and len(sanitized) > max_length:
        sanitized = sanitized[:max_length]

    return sanitized


def open_folder(path):
    """Open a folder in the system file explorer

    Args:
        path: The folder path to open

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        path = os.path.normpath(path)

        if platform.system() == "Windows":
            os.startfile(path)
        elif platform.system() == "Darwin":  # macOS
            subprocess.Popen(["open", path])
        else:  # Linux
            subprocess.Popen(["xdg-open", path])

        return True
    except Exception as e:
        print(f"Error opening folder: {e}")
        return False


def format_timestamp(timestamp):
    """Convert Unix timestamp to human-readable date

    Args:
        timestamp: Unix timestamp

    Returns:
        str: Formatted date string
    """
    try:
        return datetime.datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
    except (TypeError, ValueError):
        return "Unknown"


def format_number(number):
    """Format large numbers with commas

    Args:
        number: The number to format

    Returns:
        str: Formatted number string
    """
    try:
        return f"{int(number):,}"
    except (TypeError, ValueError):
        return "0"


def extract_urls_from_text(text):
    """
    Extract URLs from text with robust and efficient handling

    Args:
        text (str): Text containing URLs

    Returns:
        list: List of unique, validated URLs
    """
    # 快速失败和输入验证
    if not text or not isinstance(text, str):
        return []

    # 定义 URL 提取的正则表达式模式
    # 这个正则表达式被设计为尽可能准确且覆盖大多数 URL 场景
    url_pattern = re.compile(
        r'(?:(?:https?:\/\/|www\.)?' +  # 可选的协议和 www
        r'(?:[-a-zA-Z0-9@:%._+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b)' +  # 域名
        r'(?:\/[-a-zA-Z0-9()@:%_+.~#?&\/=]*)?)',  # 可选的路径和查询参数
        re.IGNORECASE
    )

    # 提取所有匹配的 URL
    urls = url_pattern.findall(text)

    # 处理和验证 URL
    validated_urls = []
    for url in urls:
        # 规范化 URL
        normalized_url = _normalize_url(url)

        # 验证 URL 并去重
        if normalized_url and normalized_url not in validated_urls:
            validated_urls.append(normalized_url)

    return validated_urls


def _normalize_url(url):
    """
    规范化 URL，确保其有效且格式正确

    Args:
        url (str): 待规范化的 URL

    Returns:
        str: 规范化后的 URL，如果无效则返回空字符串
    """
    # 去除空白
    url = url.strip()

    # 如果是 www 开头，添加 http 协议
    if url.startswith('www.'):
        url = f'http://{url}'

    try:
        # 使用 urllib 解析和验证 URL
        parsed_url = urllib.parse.urlparse(url)

        # 验证必要的 URL 组件
        if not parsed_url.scheme:
            return ''

        if not parsed_url.netloc:
            return ''

        # 检查域名是否包含至少一个点，且域名顶级后缀长度合理
        domain_parts = parsed_url.netloc.split('.')
        if len(domain_parts) < 2 or len(domain_parts[-1]) < 2:
            return ''

        # 重建 URL 并规范化
        normalized_url = urllib.parse.urlunparse((
            parsed_url.scheme,
            parsed_url.netloc.lower(),
            parsed_url.path,
            parsed_url.params,
            parsed_url.query,
            ''  # 移除片段标识符
        )).rstrip('/')

        return normalized_url

    except Exception:
        return ''


def extract_urls_from_line_text(text):
    """
    从单行文本中提取 URL

    Args:
        text (str): 单行文本

    Returns:
        list: 提取的 URL 列表
    """
    return extract_urls_from_text(text)


def extract_and_clean_url(text: str) -> str:
    """Extract and clean URLs from the input text.

    Args:
        text (str): The input text containing URLs and other content.

    Returns:
        str: The cleaned URL if found, otherwise the original text.
    """
    try:
        # 正则匹配 URL（支持 http/https）
        url_pattern = r'https?://[^\s)]+'
        urls = re.findall(url_pattern, text)

        if not urls:
            return text  # 没有找到 URL，返回原始文本

        # 只处理第一个匹配到的 URL
        url = urls[0]

        # 解析 URL
        parsed_url = urlparse(url)

        # 解析查询参数，并去掉不必要的追踪参数
        query_params = parse_qs(parsed_url.query)
        cleaned_params = {k: v for k, v in query_params.items() if not re.match(r'utm_|fbclid|gclid|ref', k)}

        # 重新构造 URL
        cleaned_query = urlencode(cleaned_params, doseq=True)
        clean_url = urlunparse((parsed_url.scheme, parsed_url.netloc, parsed_url.path, parsed_url.params, cleaned_query,
                                parsed_url.fragment))

        return clean_url
    except Exception:
        return text  # 如果解析失败，返回原始文本