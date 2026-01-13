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
    
    def fetch_sales_data(self):
        """Fetch sales data for all products.
        
        Returns:
            List of product sales data dictionaries with keys:
            - product_id: Gumroad product ID
            - product_name: Product name
            - sales_count: Total number of sales
            - revenue_cents: Total revenue in cents
            - views: Total views (if available)
            - refunds: Number of refunds
        """
        def make_api_call():
            response = requests.get(
                f"{self.base_url}/products",
                params={"access_token": self.access_token},
                timeout=30
            )
            response.raise_for_status()
            return response.json()
        
        try:
            result = self.retry_handler.with_retry(make_api_call, api_type='gumroad')
            
            if not result.get("success"):
                print("Gumroad sales fetch failed: API returned success=false")
                return []
            
            products = result.get("products", [])
            sales_data = []
            
            for product in products:
                sales_data.append({
                    "product_id": product.get("id", ""),
                    "product_name": product.get("name", ""),
                    "sales_count": product.get("sales_count", 0),
                    "revenue_cents": int(product.get("sales_usd_cents", 0)),
                    "views": product.get("view_count", 0),
                    "refunds": product.get("refunds_count", 0)
                })
            
            return sales_data
        
        except requests.exceptions.RequestException as e:
            print(f"Gumroad sales fetch failed: {e}")
            return []
