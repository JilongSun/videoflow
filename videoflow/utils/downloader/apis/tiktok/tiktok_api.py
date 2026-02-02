import re
import httpx
from downloader.apis.api_client import MainAPIClient
from datetime import datetime


class TikTokAPI:
    """TikTokAPI API module"""

    def __init__(self, main_client: MainAPIClient):
        """Initialize TikTokAPI using MainAPIClient instance"""

        # 继承 MainAPIClient 实例的方法
        self.main_client = main_client

        # 设置日志记录器
        self.logger = self.main_client.logger

        self.platform = "tiktok"

    # 根据分享链接获取单个作品数据 App接口/Get single video data by sharing link App API
    def fetch_one_video_by_share_url_app(self, share_url: str) -> dict:
        """Fetch single video data by sharing link"""
        url = f"{self.main_client.base_url}/api/v1/tiktok/app/v3/fetch_one_video_by_share_url"
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

    # 获取指定用户的信息 App接口/Get information of specified user App API
    def handler_user_profile_app(self, sec_user_id: str) -> dict:
        """Handle user profile information"""
        url = f"{self.main_client.base_url}/api/v1/tiktok/app/v3/handler_user_profile"
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
        url = f"{self.main_client.base_url}/api/v1/tiktok/app/v3/fetch_user_post_videos"
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
        url = f"{self.main_client.base_url}/api/v1/tiktok/app/v3/fetch_user_like_videos"
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
        url = f"{self.main_client.base_url}/api/v1/tiktok/web/get_sec_user_id"
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
            print(f"video_info: {video_info}")
            # First, make sure we're accessing the correct nested structure
            aweme_details = video_info.get("data", {}).get("aweme_details", [])

            if not aweme_details:
                raise ValueError("No aweme details found")

            # Use the first aweme detail (assuming single video)
            video = aweme_details[0].get("video", {})

            # Try to get 265 or H264 play addresses
            play_address_keys = [
                "play_addr_bytevc1",  # equivalent to 265
                "play_addr_h264",
                "play_addr"
            ]

            for key in play_address_keys:
                if key in video:
                    url_list = video[key].get("url_list", [])
                    if url_list:
                        return url_list[0]

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
            "/api/v1/tiktok/app/v3/fetch_one_video_by_share_url": "app"
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
            pass
        else:
            # $.data.aweme_detail.video.play_addr.url_list[0]
            video_urls = [video_info.get("video", {}).get("play_addr", {}).get("url_list", [""])[0]]
            # $.data.aweme_details[0].video.play_addr.data_size
            data_size_bytes = video_info.get("video", {}).get("play_addr", {}).get("data_size", 0)
            data_size = f"{data_size_bytes / (1024 * 1024):.2f} MB"
            # $.data.aweme_detail.video.play_addr.height
            height = video_info.get("video", {}).get("play_addr", {}).get("height", 0)
            # $.data.aweme_detail.video.play_addr.width
            width = video_info.get("video", {}).get("play_addr", {}).get("width", 0)

        # $.data.aweme_details[0].image_post_info.images[0].display_image.url_list[0]
        image_urls = [
            (image.get("display_image", {}).get("url_list") or [""])[0]
            for image in video_info.get("image_post_info", {}).get("images", [])
        ]

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

        # $.data.aweme_details[0].video.duration
        duration = video_info.get("video", {}).get("duration", 0)

        resolution = f"{width}x{height}"

        tags = [tag.get("hashtag_name", "") for tag in video_info.get("text_extra", [])]

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
        self.logger.info(f"Cleaned video data: {result}")
        return result


if "__main__" == __name__:
    from downloader.apis.api_client import MainAPIClient

    api_key = "x"
    main_client = MainAPIClient(api_key=api_key)
    tiktok_api = TikTokAPI(main_client)
    share_url = "https://www.tiktok.com/@taylorswift/video/7158465002649750827"
    video_info = tiktok_api.fetch_one_video_by_share_url_app(share_url)
    video_info = tiktok_api.clean_one_video_data(video_info)
    print(video_info)
