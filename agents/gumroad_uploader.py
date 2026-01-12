"""
Gumroad uploader module.
Creates and updates products on Gumroad via REST API.
"""
import os
import requests
from typing import Dict, Any, Optional

from agents.db import get_product_spec, update_product_spec_status

# Load environment variables
GUMROAD_ACCESS_TOKEN = os.getenv("GUMROAD_ACCESS_TOKEN")
GUMROAD_API_URL = "https://api.gumroad.com/v2"


class GumroadUploader:
    """Handles Gumroad product creation and updates via REST API."""
    
    def __init__(self):
        """Initialize Gumroad API client."""
        if not GUMROAD_ACCESS_TOKEN:
            raise ValueError("Gumroad access token not found in environment variables")
        
        self.access_token = GUMROAD_ACCESS_TOKEN
        self.base_url = GUMROAD_API_URL
        print("Gumroad uploader initialized")
    
    def create_product(self, product_spec_id: int) -> Optional[Dict[str, Any]]:
        """
        Create a new product on Gumroad from a product spec.
        
        Args:
            product_spec_id: ID of the product spec in database
        
        Returns:
            Dict with Gumroad product data or None on error
        """
        try:
            # Fetch the product spec from database
            spec = get_product_spec(product_spec_id)
            if not spec:
                print(f"Product spec {product_spec_id} not found")
                return None
            
            json_spec = spec["json_spec"]
            
            # Prepare product data for Gumroad
            product_data = self._prepare_product_data(json_spec)
            
            print(f"Creating product on Gumroad: {product_data['name']}")
            
            # Make API request to create product
            response = requests.post(
                f"{self.base_url}/products",
                data={
                    "access_token": self.access_token,
                    **product_data
                }
            )
            
            response.raise_for_status()
            result = response.json()
            
            if result.get("success"):
                product = result.get("product", {})
                gumroad_product_id = product.get("id")
                
                print(f"Product created successfully: {gumroad_product_id}")
                print(f"Product URL: {product.get('short_url', product.get('url'))}")
                
                # Update product spec status in database
                update_product_spec_status(
                    spec_id=product_spec_id,
                    status="completed",
                    gumroad_product_id=gumroad_product_id
                )
                
                return {
                    "success": True,
                    "gumroad_product_id": gumroad_product_id,
                    "product_url": product.get("short_url", product.get("url")),
                    "product_name": product.get("name"),
                    "product": product
                }
            else:
                error_msg = result.get("message", "Unknown error")
                print(f"Failed to create product: {error_msg}")
                update_product_spec_status(product_spec_id, "failed")
                return None
                
        except requests.exceptions.RequestException as e:
            error_msg = f"API request error: {str(e)}"
            print(error_msg)
            update_product_spec_status(product_spec_id, "failed")
            return None
        except Exception as e:
            error_msg = f"Error creating product: {str(e)}"
            print(error_msg)
            update_product_spec_status(product_spec_id, "failed")
            return None
    
    def update_product(self, gumroad_product_id: str, 
                       updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Update an existing product on Gumroad.
        
        Args:
            gumroad_product_id: Gumroad product ID
            updates: Dict of fields to update
        
        Returns:
            Dict with updated product data or None on error
        """
        try:
            print(f"Updating product {gumroad_product_id} on Gumroad...")
            
            response = requests.put(
                f"{self.base_url}/products/{gumroad_product_id}",
                data={
                    "access_token": self.access_token,
                    **updates
                }
            )
            
            response.raise_for_status()
            result = response.json()
            
            if result.get("success"):
                product = result.get("product", {})
                print(f"Product updated successfully")
                return {
                    "success": True,
                    "product": product
                }
            else:
                error_msg = result.get("message", "Unknown error")
                print(f"Failed to update product: {error_msg}")
                return None
                
        except Exception as e:
            error_msg = f"Error updating product: {str(e)}"
            print(error_msg)
            return None
    
    def get_product(self, gumroad_product_id: str) -> Optional[Dict[str, Any]]:
        """
        Get product details from Gumroad.
        
        Args:
            gumroad_product_id: Gumroad product ID
        
        Returns:
            Dict with product data or None on error
        """
        try:
            response = requests.get(
                f"{self.base_url}/products/{gumroad_product_id}",
                params={"access_token": self.access_token}
            )
            
            response.raise_for_status()
            result = response.json()
            
            if result.get("success"):
                return result.get("product")
            return None
            
        except Exception as e:
            print(f"Error getting product: {e}")
            return None
    
    def list_products(self) -> Optional[list]:
        """
        List all products in the Gumroad account.
        
        Returns:
            List of products or None on error
        """
        try:
            response = requests.get(
                f"{self.base_url}/products",
                params={"access_token": self.access_token}
            )
            
            response.raise_for_status()
            result = response.json()
            
            if result.get("success"):
                return result.get("products", [])
            return None
            
        except Exception as e:
            print(f"Error listing products: {e}")
            return None
    
    def _prepare_product_data(self, json_spec: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert product spec JSON to Gumroad API format.
        
        Args:
            json_spec: Product specification from database
        
        Returns:
            Dict formatted for Gumroad API
        """
        # Extract data from spec with defaults
        name = json_spec.get("product_name", "Untitled Product")
        description = json_spec.get("description", "")
        price = json_spec.get("price", 0)
        
        # Convert price to cents (Gumroad expects integer cents)
        if isinstance(price, str):
            price = float(price.replace("$", "").replace(",", ""))
        price_cents = int(float(price) * 100)
        
        # Build description with additional details
        full_description = description
        
        if json_spec.get("value_proposition"):
            full_description += f"\n\n**Value Proposition:**\n{json_spec['value_proposition']}"
        
        if json_spec.get("key_features"):
            full_description += "\n\n**Key Features:**\n"
            for feature in json_spec["key_features"]:
                full_description += f"- {feature}\n"
        
        if json_spec.get("content_outline"):
            full_description += "\n\n**What's Included:**\n"
            for item in json_spec["content_outline"]:
                full_description += f"- {item}\n"
        
        # Prepare Gumroad product data
        product_data = {
            "name": name[:100],  # Gumroad has name length limit
            "description": full_description,
            "price": price_cents,
        }
        
        # Add custom permalink if product type is available
        if json_spec.get("product_type"):
            # Create URL-friendly permalink
            permalink = json_spec["product_type"].lower().replace(" ", "-")
            product_data["custom_permalink"] = permalink[:30]
        
        return product_data


def push_product_to_gumroad(product_spec_id: int) -> Optional[Dict[str, Any]]:
    """
    Convenience function to push a product spec to Gumroad.
    Creates uploader instance and returns result.
    """
    try:
        uploader = GumroadUploader()
        return uploader.create_product(product_spec_id)
    except Exception as e:
        print(f"Error in push_product_to_gumroad: {e}")
        return None
