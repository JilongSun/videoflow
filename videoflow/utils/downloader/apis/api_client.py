"""
Main API client for TikHub.io using httpx for synchronous requests
"""

from downloader.constants import HTTP_CLIENT_USER_AGENT
from downloader.utils.logger import logger_instance
from downloader.utils.utils import extract_and_clean_url


class MainAPIClient:
    """Synchronous API client"""

    def __init__(self,
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
        self.logger = logger_instance

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
        from downloader.apis.tiktok.tiktok_api import TikTokAPI
        self.tiktok_api = TikTokAPI(self)


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
            "API_KEY"
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
            'User-Agent': HTTP_CLIENT_USER_AGENT,
            'Authorization': f'Bearer {key}',
            'Accept': '*/*',
            'Connection': 'keep-alive'
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
                # Fetch video info
                video_info = self.tiktok_api.fetch_one_video_by_share_url_app(clean_url)

                # Clean the data if needed
                if clean_data:
                    video_info = self.tiktok_api.clean_one_video_data(video_info)

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
                if not user_info or 'data' not in user_info or 'user' not in user_info['data']:
                    return None, []

                # Fetch user videos with pagination
                all_videos = self.douyin_api.fetch_user_videos(sec_user_id, max_videos)

            # If the URL is from TikTok, use the TikTok API
            elif "tiktok" in clean_url:
                # Determine the platform
                platform = "tiktok"

                # Get user sec_user_id
                sec_user_id = self.tiktok_api.get_sec_user_id(clean_url)
                if not sec_user_id:
                    return None, []

                # Get user profile
                user_info = self.tiktok_api.handler_user_profile_app(sec_user_id)
                if not user_info or 'data' not in user_info or 'user' not in user_info['data']:
                    return None, []

                # Fetch user videos with pagination
                all_videos = self.tiktok_api.fetch_user_videos(sec_user_id, max_videos)

            else:
                self.logger.error("Unsupported platform")
                return None, [], "unsupported"

            return user_info['data'], all_videos, platform

        except Exception as e:
            self.logger.error(f"Error getting user info: {e}")
            return None, []