import requests
from config import settings


class GumroadClient:
    def __init__(self):
        self.access_token = settings.gumroad_access_token
        self.base_url = "https://api.gumroad.com/v2"

    def create_product(self, name: str, description: str, price_cents: int, custom_permalink: str = None):
        data = {
            "access_token": self.access_token,
            "name": name,
            "description": description,
            "price": price_cents
        }

        if custom_permalink:
            data["custom_permalink"] = custom_permalink

        response = requests.post(
            f"{self.base_url}/products",
            data=data
        )
        response.raise_for_status()
        result = response.json()

        if result.get("success"):
            return result.get("product")
        return None
