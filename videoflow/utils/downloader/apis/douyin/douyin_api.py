import re
import httpx
from datetime import datetime
from downloader.apis.api_client import MainAPIClient


class DouyinAPI:
    """DouyinAPI API module"""

    def __init__(self, main_client: MainAPIClient):
        """Initialize DouyinAPI using MainAPIClient instance"""

        # 继承 MainAPIClient 实例的方法
        self.main_client = main_client

        # 设置日志记录器
        self.logger = self.main_client.logger

        # 设置一个默认的平台值
        self.platform = "douyin"

    # 根据分享链接获取单个作品数据 Web接口/Get single video data by sharing link Web API
    def fetch_one_video_by_share_url_web(self, share_url: str) -> dict:
        """Fetch single video data by sharing link"""
        url = f"{self.main_client.base_url}/api/v1/douyin/web/fetch_one_video_by_share_url"
        headers = self.main_client.get_headers()
        params = {
            "share_url": share_url
        }
        with httpx.Client() as client:
            response = client.get(url, params=params, headers=headers, timeout=30)
            # 打印日志
            self.logger.info(f"fetch_one_video_by_share_url_web response code: {response.status_code}")
            response = response.json()
        return response

    # 根据分享链接获取单个作品数据 App接口/Get single video data by sharing link App API
    def fetch_one_video_by_share_url_app(self, share_url: str) -> dict:
        """Fetch single video data by sharing link"""
        url = f"{self.main_client.base_url}/api/v1/douyin/app/v3/fetch_one_video_by_share_url"
        headers = self.main_client.get_headers()
        params = {
            "share_url": share_url
        }
        with httpx.Client() as client:
            response = client.get(url, params=params, headers=headers, timeout=30)
            # 打印日志
            self.logger.info(f"fetch_one_video_by_share_url_app response code: {response.status_code}")
            response = response.json()
        return response

    # 获取指定用户的信息 Web接口/Get information of specified user Web API
    def handler_user_profile_web(self, sec_user_id: str) -> dict:
        """Handle user profile information"""
        url = f"{self.main_client.base_url}/api/v1/douyin/web/handler_user_profile"
        headers = self.main_client.get_headers()
        params = {
            "sec_user_id": sec_user_id
        }
        with httpx.Client() as client:
            response = client.get(url, params=params, headers=headers, timeout=30)
            # 打印日志
            self.logger.info(f"handler_user_profile_web response code: {response.status_code}")
            response = response.json()
        return response

    # 获取指定用户的信息 App接口/Get information of specified user App API
    def handler_user_profile_app(self, sec_user_id: str) -> dict:
        """Handle user profile information"""
        url = f"{self.main_client.base_url}/api/v1/douyin/app/v3/handler_user_profile"
        headers = self.main_client.get_headers()
        params = {
            "sec_user_id": sec_user_id
        }
        with httpx.Client() as client:
            response = client.get(url, params=params, headers=headers, timeout=30)
            # 打印日志
            self.logger.info(f"handler_user_profile_app response code: {response.status_code}")
            response = response.json()
        return response

    # 获取用户主页作品数据/Get user homepage video data
    def fetch_user_post_videos(self, sec_user_id: str, max_cursor: int = 0, count: int = 20) -> dict:
        """Fetch user homepage video data"""
        url = f"{self.main_client.base_url}/api/v1/douyin/app/v3/fetch_user_post_videos"
        headers = self.main_client.get_headers()
        params = {
            "sec_user_id": sec_user_id,
            "max_cursor": max_cursor,
            "count": count
        }
        with httpx.Client() as client:
            response = client.get(url, params=params, headers=headers, timeout=30)
            # 打印日志
            self.logger.info(f"fetch_user_post_videos response code: {response.status_code}")
            response = response.json()
        return response

    # 获取用户喜欢作品数据/Get user like video data
    def fetch_user_like_videos(self, sec_user_id: str, max_cursor: int = 0, count: int = 20) -> dict:
        """Fetch user like video data"""
        url = f"{self.main_client.base_url}/api/v1/douyin/app/v3/fetch_user_like_videos"
        headers = self.main_client.get_headers()
        params = {
            "sec_user_id": sec_user_id,
            "max_cursor": max_cursor,
            "count": count
        }
        with httpx.Client() as client:
            response = client.get(url, params=params, headers=headers, timeout=30)
            # 打印日志
            self.logger.info(f"fetch_user_like_videos response code: {response.status_code}")
            response = response.json()
        return response

    # 提取单个用户id/Extract single user id
    def get_sec_user_id(self, user_url: str) -> str:
        """Get sec_user_id from user URL"""
        url = f"{self.main_client.base_url}/api/v1/douyin/web/get_sec_user_id"
        headers = self.main_client.get_headers()
        params = {
            "url": user_url
        }
        with httpx.Client() as client:
            response = client.get(url, params=params, headers=headers, timeout=30)
            # 打印日志
            self.logger.info(f"get_sec_user_id response code: {response.status_code}")
            response = response.json()
        return response.get("data", "")

    """--------------------------------------以下为工具接口--------------------------------------"""

    def get_video_play_address(self, video_info: dict):
        """Extract video play address from video info

        Args:
            video_info: The video information

        Returns:
            str: The video play URL
        """
        try:
            # Try to get 265 format
            try:
                return video_info["data"]["aweme_detail"]["video"]["play_addr_265"]["url_list"][0]
            except (KeyError, IndexError, TypeError):
                pass

            # Try to get h264 format
            try:
                return video_info["data"]["aweme_detail"]["video"]["play_addr"]["url_list"][0]
            except (KeyError, IndexError, TypeError):
                pass

            # Try other formats
            if "data" in video_info and "aweme_detail" in video_info["data"] and "video" in video_info["data"]["aweme_detail"]:
                video = video_info["data"]["aweme_detail"]["video"]

                # Try all possible video addresses
                for key in ["play_addr_h264", "download_addr", "play_addr_lowbr"]:
                    if key in video and "url_list" in video[key] and video[key]["url_list"]:
                        return video[key]["url_list"][0]

            raise ValueError("Could not find a valid video URL")
        except Exception as e:
            self.logger.error(f"Error getting video play address: {e}")
            return None

    # Fetch user videos with pagination
    def fetch_user_videos(self, sec_user_id: str, max_videos: int = 20):
        """Fetch user videos with pagination

        Args:
            sec_user_id: The user sec_user_id
            max_videos: Maximum number of videos to fetch

        Returns:
            list: List of user videos
        """
        all_videos = []
        has_more = True
        max_cursor = 0

        while has_more and len(all_videos) < max_videos:
            try:
                # Fetch one page of videos
                response = self.fetch_user_post_videos(sec_user_id, max_cursor)
                if not response or 'data' not in response or 'aweme_list' not in response['data']:
                    break

                # Add videos to the list
                all_videos.extend(response['data']['aweme_list'])

                # Update max_cursor for pagination
                max_cursor = response['data']['max_cursor']
                has_more = response['data']['has_more']
            except Exception as e:
                self.logger.error(f"Error fetching user videos: {e}")
                break

        return all_videos[:max_videos]

    def clean_one_video_data(self, video_info):
        """
        Clean video data and return a simplified version

        Args:
            video_info: Dict, The raw video information

        Returns:
            dict: Dict, The cleaned video data
        """
        # data source
        source = {
            "/api/v1/douyin/web/fetch_one_video_by_share_url": "web",
            "/api/v1/douyin/app/v3/fetch_one_video_by_share_url": "app"
        }
        source = source.get(video_info.get("router"), "app")

        # $.params.share_url
        raw_url = video_info.get("params", {}).get("share_url", "")

        media_type_codes = {
            0: 'video',
            2: 'image',
            4: 'video',
            68: 'image',
            51: 'video',
            55: 'video',
            58: 'video',
            61: 'video',
            150: 'image'
        }
        # Extract video info
        if video_info.get('data') and video_info['data'].get('aweme_detail'):
            video_info = video_info['data']['aweme_detail']
        elif video_info.get('data') and video_info['data'].get('aweme_details'):
            video_info = video_info['data']['aweme_details'][0]

        # $.data.aweme_details[0].aweme_id
        # $.data.aweme_detail.aweme_id
        aweme_id = video_info.get("aweme_id", "")
        media_type = media_type_codes.get(video_info.get("aweme_type", 0), "video")
        desc = video_info.get("desc", "")
        create_time = datetime.fromtimestamp(video_info.get("create_time", 0)).strftime('%Y-%m-%dT%H:%M:%SZ')
        author_name = video_info.get("author", {}).get("nickname", "")
        author_id = video_info.get("author", {}).get("sec_uid", "")
        author_avatar = video_info.get("author", {}).get("avatar_larger", {}).get("url_list", [""])[0]

        if source == "web":
            # $.data.aweme_details[0].video.bit_rate[0].play_addr.url_list[0]
            video_urls = [video_info.get("video", {}).get("bit_rate", [{}])[0].get("play_addr", {}).get("url_list", [""])[0]]
            # $.data.aweme_details[0].video.bit_rate[0].play_addr.height
            height = video_info.get("video", {}).get("bit_rate", [{}])[0].get("play_addr", {}).get("height", 0)
            # $.data.aweme_details[0].video.bit_rate[0].play_addr.width
            width = video_info.get("video", {}).get("bit_rate", [{}])[0].get("play_addr", {}).get("width", 0)
            # $.data.aweme_details[0].video.bit_rate[0].play_addr.data_size
            data_size_bytes = video_info.get("video", {}).get("play_addr", {}).get("data_size", 0)
        else:
            # $.data.aweme_detail.video.play_addr.url_list[0]
            video_urls = [video_info.get("video", {}).get("play_addr", {}).get("url_list", [""])[0]]
            # $.data.aweme_detail.video.play_addr.height
            height = video_info.get("video", {}).get("play_addr", {}).get("height", 0)
            # $.data.aweme_detail.video.play_addr.width
            width = video_info.get("video", {}).get("play_addr", {}).get("width", 0)
            # $.data.aweme_detail.video.play_addr.data_size
            data_size_bytes = video_info.get("video", {}).get("play_addr", {}).get("data_size", 0)

        # data size in MB
        data_size = f"{data_size_bytes / (1024 * 1024):.2f} MB"

        # $.data.aweme_details[0].images[0].url_list[0]
        if video_info.get("images") and isinstance(video_info.get("images"), list):
            image_urls = []

            for image in video_info.get("images", []):
                image_urls.append((image.get("url_list") or [""])[0])

                # Check if the image is a live photo
                if image.get("video") and isinstance(image.get("video"), dict):
                    # $.data.aweme_detail.images[0].video.play_addr.url_list[0]
                    image_urls.append(image.get("video", {}).get("play_addr", {}).get("url_list", [""])[0])
        else:
            image_urls = []

        # $.data.aweme_details[0].music.id_str
        music_id = video_info.get("music", {}).get("id_str", "")

        # $.data.aweme_details[0].music.title
        music_title = video_info.get("music", {}).get("title", "")

        # $.data.aweme_details[0].music.owner_nickname
        music_author = video_info.get("music", {}).get("owner_nickname", "")

        # $.data.aweme_details[0].music.play_url.url_list[0]
        music_urls = [video_info.get("music", {}).get("play_url", {}).get("url_list", [""])[0]]

        # $.data.aweme_detail.statistics.digg_count
        like_count = video_info.get("statistics", {}).get("digg_count", 0)

        # $.data.aweme_details[0].statistics.comment_count
        comment_count = video_info.get("statistics", {}).get("comment_count", 0)

        # $.data.aweme_details[0].statistics.share_count
        share_count = video_info.get("statistics", {}).get("share_count", 0)

        # $.data.aweme_details[0].duration
        duration = video_info.get("duration", 0)

        resolution = f"{width}x{height}"

        # $.data.aweme_detail.caption
        tags = re.findall(r"(?<=#)\S+", video_info.get("caption", ""))

        result = {
            "id": aweme_id,
            "platform": self.platform,
            "media_type": media_type,
            "desc": desc,
            "raw_url": raw_url,
            "create_time": create_time,
            "author_name": author_name,
            "author_id": author_id,
            "author_avatar": author_avatar,
            "video_urls": video_urls,
            "image_urls": image_urls,
            "music_id": music_id,
            "music_title": music_title,
            "music_author": music_author,
            "music_urls": music_urls,
            "like_count": like_count,
            "comment_count": comment_count,
            "share_count": share_count,
            "duration": duration,
            "data_size": data_size,
            "resolution": resolution,
            "tags": tags
        }

        return result
