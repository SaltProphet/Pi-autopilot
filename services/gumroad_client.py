import requests
from config import settings
from services.retry_handler import RetryHandler


class GumroadClient:
    def __init__(self):
        self.access_token = settings.gumroad_access_token
        self.base_url = "https://api.gumroad.com/v2"
        self.retry_handler = RetryHandler()
    
    def create_product(self, name: str, description: str, price_cents: int, custom_permalink: str = None):
        if not isinstance(price_cents, int) or price_cents <= 0:
            raise ValueError(f"price_cents must be a positive integer, got {price_cents}")
        
        data = {
            "access_token": self.access_token,
            "name": name,
            "description": description,
            "price": price_cents
        }
        
        if custom_permalink:
            data["custom_permalink"] = custom_permalink
        
        def make_api_call():
            response = requests.post(
                f"{self.base_url}/products",
                data=data,
                timeout=30
            )
            response.raise_for_status()
            return response.json()
        
        try:
            result = self.retry_handler.with_retry(make_api_call, api_type='gumroad')
            
            if result.get("success"):
                return result.get("product")
            return None
        except requests.exceptions.RequestException as e:
            print(f"Gumroad API request failed: {e}")
            return None
