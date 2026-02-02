import httpx
from downloader.apis.api_client import MainAPIClient


class TikHubAPI:
    """TikHub API module"""

    def __init__(self, main_client: MainAPIClient):
        """Initialize TikHubAPI using MainAPIClient instance"""

        # 继承 MainAPIClient 实例的方法
        self.main_client = main_client

        # 设置日志记录器
        self.logger = self.main_client.logger

    # 获取TikHub用户信息/Get TikHub user information
    def get_tikhub_user_info(self, api_key: str = None):
        """
        Get user information from the TikHub API

        Returns:
            dict: Response from the API
        """
        url = f"{self.main_client.base_url}/api/v1/tikhub/user/get_user_info"
        headers = self.main_client.get_headers(api_key)
        with httpx.Client() as client:
            response = client.get(url, headers=headers, timeout=10)
            # 打印日志
            self.logger.info(f"get_tikhub_user_info response code: {response.status_code}")
            response = response.json()
        return response

    # 获取用户每日使用情况/Get user daily usage
    def get_user_daily_usage(self, api_key: str = None):
        """
        Get daily usage information for the user

        Returns:
            dict: Response from the API
        """
        url = f"{self.main_client.base_url}/api/v1/tikhub/user/get_user_daily_usage"
        headers = self.main_client.get_headers(api_key)
        with httpx.Client() as client:
            response = client.get(url, headers=headers, timeout=10)
            # 打印日志
            self.logger.info(f"get_user_daily_usage response code: {response.status_code}")
            response = response.json()
        return response

    # 计算价格/Calculate price
    def calculate_price(self,
                        api_key: str = None,
                        endpoint: str = "/apis/v1/tiktok/app/v3/fetch_one_video",
                        request_per_day: int = 100000
                        ):
        """
        Calculate the price for downloading videos

        Args:
            api_key (str): API key for authentication
            endpoint (str): API endpoint for calculating price
            request_per_day (int): Number of requests per day

        Returns:
            dict: Response from the API
        """
        url = f"{self.main_client.base_url}/api/v1/tikhub/user/calculate_price"
        headers = self.main_client.get_headers(api_key)
        params = {
            "endpoint": endpoint,
            "request_per_day": request_per_day
        }
        with httpx.Client() as client:
            response = client.get(url, headers=headers, params=params, timeout=10)
            # 打印日志
            self.logger.info(f"calculate_price response code: {response.status_code}")
            response = response.json()
        return response

    # 获取阶梯式折扣百分比信息/Get tiered discount percentage information
    def get_tiered_discount_info(self, api_key: str = None):
        """
        Get tiered discount percentage information

        Returns:
            dict: Response from the API
        """
        url = f"{self.main_client.base_url}/api/v1/tikhub/user/get_tiered_discount_info"
        headers = self.main_client.get_headers(api_key)
        with httpx.Client() as client:
            response = client.get(url, headers=headers, timeout=10)
            # 打印日志
            self.logger.info(f"get_tiered_discount_info response code: {response.status_code}")
            response = response.json()

        return response

    # 获取一个端点的信息/Get information of an endpoint
    def get_endpoint_info(self,
                          api_key: str = None,
                          endpoint: str = "/apis/v1/tiktok/app/v3/fetch_one_video"
                          ):
        """
        Get information of an endpoint

        Args:
            api_key (str): API key for authentication
            endpoint (str): API endpoint for information

        Returns:
            dict: Response from the API
        """
        url = f"{self.main_client.base_url}/api/v1/tikhub/user/get_endpoint_info"
        headers = self.main_client.get_headers(api_key)
        params = {
            "endpoint": endpoint
        }
        with httpx.Client() as client:
            response = client.get(url, headers=headers, params=params, timeout=10)
            # 打印日志
            self.logger.info(f"get_endpoint_info response code: {response.status_code}")
            response = response.json()
        return response

    # 获取所有端点信息/Get all endpoints information
    def get_all_endpoints_info(self, api_key: str = None):
        """
        Get information of all endpoints

        Returns:
            dict: Response from the API
        """
        url = f"{self.main_client.base_url}/api/v1/tikhub/user/get_all_endpoints_info"
        headers = self.main_client.get_headers(api_key)
        with httpx.Client() as client:
            response = client.get(url, headers=headers, timeout=10)
            # 打印日志
            self.logger.info(f"get_all_endpoints_info response code: {response.status_code}")
            response = response.json()
        return response


if __name__ == "__main__":
    # Create a MainAPIClient instance
    main_client = MainAPIClient(
        # Add your API key here
        api_key="x"
    )

    # Create a TikHubAPI instance
    tikhub_api = TikHubAPI(main_client=main_client)

    # Get user information
    user_info = tikhub_api.get_tikhub_user_info()

    # Get daily usage information
    daily_usage = tikhub_api.get_user_daily_usage()

    # Calculate price
    price = tikhub_api.calculate_price()

    # Get tiered discount information
    discount_info = tikhub_api.get_tiered_discount_info()

    # Get information of an endpoint
    endpoint_info = tikhub_api.get_endpoint_info()

    # Get information of all endpoints
    all_endpoints_info = tikhub_api.get_all_endpoints_info()
