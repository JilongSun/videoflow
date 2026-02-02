"""
Main API client for TikHub.io using httpx for synchronous requests
"""

from downloader.constants import HTTP_CLIENT_USER_AGENT
from videoflow.utils.logger_config import log
from urllib import parse
from urllib.parse import urlparse, parse_qs, urlunparse, urlencode
import re, urllib, datetime, os, platform, subprocess





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
        return datetime.datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")
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
        r"(?:(?:https?:\/\/|www\.)?"  # 可选的协议和 www
        + r"(?:[-a-zA-Z0-9@:%._+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b)"  # 域名
        + r"(?:\/[-a-zA-Z0-9()@:%_+.~#?&\/=]*)?)",  # 可选的路径和查询参数
        re.IGNORECASE,
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
    if url.startswith("www."):
        url = f"http://{url}"

    try:
        # 使用 urllib 解析和验证 URL
        parsed_url = parse.urlparse(url)

        # 验证必要的 URL 组件
        if not parsed_url.scheme:
            return ""

        if not parsed_url.netloc:
            return ""

        # 检查域名是否包含至少一个点，且域名顶级后缀长度合理
        domain_parts = parsed_url.netloc.split(".")
        if len(domain_parts) < 2 or len(domain_parts[-1]) < 2:
            return ""

        # 重建 URL 并规范化
        normalized_url = parse.urlunparse(
            (
                parsed_url.scheme,
                parsed_url.netloc.lower(),
                parsed_url.path,
                parsed_url.params,
                parsed_url.query,
                "",  # 移除片段标识符
            )
        ).rstrip("/")

        return normalized_url

    except Exception:
        return ""


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
        url_pattern = r"https?://[^\s)]+"
        urls = re.findall(url_pattern, text)

        if not urls:
            return text  # 没有找到 URL，返回原始文本

        # 只处理第一个匹配到的 URL
        url = urls[0]

        # 解析 URL
        parsed_url = urlparse(url)

        # 解析查询参数，并去掉不必要的追踪参数
        query_params = parse_qs(parsed_url.query)
        cleaned_params = {
            k: v
            for k, v in query_params.items()
            if not re.match(r"utm_|fbclid|gclid|ref", k)
        }

        # 重新构造 URL
        cleaned_query = urlencode(cleaned_params, doseq=True)
        clean_url = urlunparse(
            (
                parsed_url.scheme,
                parsed_url.netloc,
                parsed_url.path,
                parsed_url.params,
                cleaned_query,
                parsed_url.fragment,
            )
        )

        return clean_url
    except Exception:
        return text  # 如果解析失败，返回原始文本


class MainAPIClient:
    """Synchronous API client"""

    def __init__(
        self,
        api_key=None,
        base_url=None,
        headers=None,
        proxy=None,
    ):
        """Initialize the API client

        Args:
            api_key: The API key for TikHub.io
            base_url: The base URL for the API
        """

        # Set the logger
        self.logger = log

        # Set the API key
        self.api_key = api_key

        # Set the base URL
        self.base_url = base_url or "https://api.tikhub.io"

        # Set the headers
        self.headers = headers or self.get_headers()

        # Set the proxy
        self.proxy = proxy or None

        # Set up the API clients (Use lazy loading to avoid circular imports)
        from downloader.apis.tikhub.tikhub_api import TikHubAPI

        self.tikhub_api = TikHubAPI(self)

        # Check if the client is properly configured
        self.is_configured = self._check_configuration()

        # Douyin API
        from downloader.apis.douyin.douyin_api import DouyinAPI

        self.douyin_api = DouyinAPI(self)

        # Keep add more...
        # from downloader.apis.tiktok.tiktok_api import TikTokAPI
        # self.tiktok_api = TikTokAPI(self)

    def _check_configuration(self):
        """
        Check if the client is properly configured

        Returns:
            bool: True if API key is valid, False otherwise
        """
        # Check if API key is None, empty, or a default placeholder
        if not self.api_key or self.api_key in [
            "",
            "your_private_api_key",
            "YOUR_API_KEY",
            "API_KEY_HERE",
            "API_KEY",
        ]:
            return False
        else:
            # Test the API key with a simple request
            user_info = self.tikhub_api.get_tikhub_user_info(self.api_key)
            return user_info.get("code") == 200

    def update_api_key(self, api_key):
        """Update the API key

        Args:
            api_key: The new API key

        Returns:
            dict: Response from the API
        """
        # Test the API key with a simple request
        user_info = self.tikhub_api.get_tikhub_user_info(api_key)

        # If successful, update the API key
        if user_info.get("code") == 200:
            self.api_key = api_key
            self.is_configured = True

        return user_info

    def get_headers(self, api_key=None):
        """Get the HTTP headers for API requests

        Args:
            api_key: Optional API key to use instead of the stored one

        Returns:
            dict: HTTP headers
        """
        key = api_key or self.api_key
        return {
            "User-Agent": HTTP_CLIENT_USER_AGENT,
            "Authorization": f"Bearer {key}",
            "Accept": "*/*",
            "Connection": "keep-alive",
        }

    def get_data(self, url: str, clean_data: bool = True):
        """Get the post data from a share URL

        Args:
            url: The share URL of the post
            clean_data: Whether to clean the data, return raw data if False

        Returns:
            dict: The post data or raw data, or None if client is not configured
        """
        if not self.is_configured:
            return None

        # Clean the URL to improve compatibility
        clean_url = extract_and_clean_url(url)

        try:
            # If the URL is from Douyin, use the Douyin API
            if "douyin" in clean_url:
                # Fetch video info (raw data)
                video_info = self.douyin_api.fetch_one_video_by_share_url_app(clean_url)

                # Clean the data if needed
                if clean_data:
                    video_info = self.douyin_api.clean_one_video_data(video_info)
            else:
                # # Fetch video info
                # video_info = self.tiktok_api.fetch_one_video_by_share_url_app(clean_url)

                # # Clean the data if needed
                # if clean_data:
                #     video_info = self.tiktok_api.clean_one_video_data(video_info)
                raise ValueError(f"Unsupported platform for URL: {clean_url}")

            return video_info
        except Exception as e:
            self.logger.error(f"Error getting video info: {e}")
            return None, None

    def get_user_info_and_videos(self, user_url, max_videos=20):
        """Get user information and videos

        Args:
            user_url: The user profile URL
            max_videos: Maximum number of videos to fetch

        Returns:
            tuple: (user_profile, user_videos)
        """
        if not self.is_configured:
            return None, []

        try:
            # Clean the URL
            clean_url = extract_and_clean_url(user_url)

            # If the URL is from Douyin, use the Douyin API
            if "douyin" in clean_url:
                # Determine the platform
                platform = "douyin"

                # Get user sec_user_id
                sec_user_id = self.douyin_api.get_sec_user_id(clean_url)
                if not sec_user_id:
                    return None, []

                # Get user profile
                user_info = self.douyin_api.handler_user_profile_app(sec_user_id)
                if (
                    not user_info
                    or "data" not in user_info
                    or "user" not in user_info["data"]
                ):
                    return None, []

                # Fetch user videos with pagination
                all_videos = self.douyin_api.fetch_user_videos(sec_user_id, max_videos)

                # If the URL is from TikTok, use the TikTok API
                # elif "tiktok" in clean_url:
                # # Determine the platform
                # platform = "tiktok"

                # # Get user sec_user_id
                # sec_user_id = self.tiktok_api.get_sec_user_id(clean_url)
                # if not sec_user_id:
                #     return None, []

                # # Get user profile
                # user_info = self.tiktok_api.handler_user_profile_app(sec_user_id)
                # if not user_info or 'data' not in user_info or 'user' not in user_info['data']:
                #     return None, []

                # # Fetch user videos with pagination
                # all_videos = self.tiktok_api.fetch_user_videos(sec_user_id, max_videos)
                raise ValueError(f"Unsupported platform for URL: {clean_url}")

            else:
                self.logger.error("Unsupported platform")
                return None, [], "unsupported"

            return user_info["data"], all_videos, platform

        except Exception as e:
            self.logger.error(f"Error getting user info: {e}")
            return None, []
