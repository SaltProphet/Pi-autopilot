"""Sales feedback service for analyzing product performance and guiding future decisions."""
import time
from typing import Dict, List
from services.storage import Storage
from services.gumroad_client import GumroadClient
from config import settings


class SalesFeedback:
    """Analyze sales data and generate feedback for product selection."""
    
    def __init__(self, storage: Storage = None, gumroad_client: GumroadClient = None):
        """Initialize sales feedback service.
        
        Args:
            storage: Storage instance (creates new one if not provided)
            gumroad_client: GumroadClient instance (creates new one if not provided)
        """
        self.storage = storage or Storage()
        self.gumroad_client = gumroad_client or GumroadClient()
    
    def ingest_sales_data(self) -> Dict:
        """Fetch sales data from Gumroad and persist to database.
        
        Returns:
            Dictionary with ingestion results:
            - success: Whether ingestion succeeded
            - products_ingested: Number of products processed
            - timestamp: When data was fetched
        """
        sales_data = self.gumroad_client.fetch_sales_data()
        
        if not sales_data:
            return {
                "success": False,
                "products_ingested": 0,
                "timestamp": int(time.time())
            }
        
        fetched_at = int(time.time())
        
        for product in sales_data:
            self.storage.save_sales_metrics(
                product_id=product["product_id"],
                product_name=product["product_name"],
                sales_count=product["sales_count"],
                revenue_cents=product["revenue_cents"],
                views=product["views"],
                refunds=product["refunds"],
                fetched_at=fetched_at
            )
        
        return {
            "success": True,
            "products_ingested": len(sales_data),
            "timestamp": fetched_at
        }
    
    def generate_feedback_summary(self, lookback_days: int = None) -> Dict:
        """Generate performance summary for the specified time period.
        
        Args:
            lookback_days: Number of days to look back (uses config default if not provided)
        
        Returns:
            Dictionary with performance metrics:
            - products_published: Number of products published in period
            - products_sold: Number of products with at least one sale
            - zero_sale_products: Number of products with no sales
            - avg_price_cents: Average product price
            - revenue_per_product_cents: Average revenue per product
            - total_revenue_cents: Total revenue
            - total_sales: Total number of sales
            - refund_rate: Refund rate (refunds / sales)
        """
        if lookback_days is None:
            lookback_days = settings.sales_lookback_days
        
        # Get sales metrics from the period
        sales_metrics = self.storage.get_sales_metrics_since(lookback_days)
        
        # Get uploaded products from the period
        uploaded_products = self.storage.get_recent_uploaded_products(limit=1000)
        
        # Filter uploaded products to the lookback period
        cutoff_timestamp = int(time.time() - (lookback_days * 86400))
        recent_uploads = [p for p in uploaded_products if p['created_at'] >= cutoff_timestamp]
        
        if not sales_metrics:
            return {
                "products_published": len(recent_uploads),
                "products_sold": 0,
                "zero_sale_products": len(recent_uploads),
                "avg_price_cents": 0,
                "revenue_per_product_cents": 0,
                "total_revenue_cents": 0,
                "total_sales": 0,
                "refund_rate": 0.0
            }
        
        # Calculate metrics
        products_with_sales = [p for p in sales_metrics if p["sales_count"] > 0]
        products_without_sales = [p for p in sales_metrics if p["sales_count"] == 0]
        
        total_sales = sum(p["sales_count"] for p in sales_metrics)
        total_refunds = sum(p["refunds"] for p in sales_metrics)
        total_revenue = sum(p["revenue_cents"] for p in sales_metrics)
        
        # Calculate average price (revenue / sales, avoiding division by zero)
        avg_price = int(total_revenue / total_sales) if total_sales > 0 else 0
        
        # Revenue per product
        revenue_per_product = int(total_revenue / len(sales_metrics)) if sales_metrics else 0
        
        # Refund rate
        refund_rate = total_refunds / total_sales if total_sales > 0 else 0.0
        
        return {
            "products_published": len(recent_uploads),
            "products_sold": len(products_with_sales),
            "zero_sale_products": len(products_without_sales),
            "avg_price_cents": avg_price,
            "revenue_per_product_cents": revenue_per_product,
            "total_revenue_cents": total_revenue,
            "total_sales": total_sales,
            "refund_rate": refund_rate
        }
    
    def get_top_performing_categories(self, lookback_days: int = None, limit: int = 5) -> List[str]:
        """Get categories/topics from best-selling products.
        
        Args:
            lookback_days: Number of days to look back
            limit: Maximum number of categories to return
        
        Returns:
            List of product names/categories that sold well
        """
        if lookback_days is None:
            lookback_days = settings.sales_lookback_days
        
        sales_metrics = self.storage.get_sales_metrics_since(lookback_days)
        
        # Sort by sales count and take top performers
        sorted_products = sorted(sales_metrics, key=lambda x: x["sales_count"], reverse=True)
        top_products = sorted_products[:limit]
        
        return [p["product_name"] for p in top_products if p["sales_count"] > 0]
    
    def get_zero_sale_categories(self, lookback_days: int = None, limit: int = 5) -> List[str]:
        """Get categories/topics from products with zero sales.
        
        Args:
            lookback_days: Number of days to look back
            limit: Maximum number of categories to return
        
        Returns:
            List of product names/categories that didn't sell
        """
        if lookback_days is None:
            lookback_days = settings.sales_lookback_days
        
        sales_metrics = self.storage.get_sales_metrics_since(lookback_days)
        
        # Get products with zero sales
        zero_sale_products = [p for p in sales_metrics if p["sales_count"] == 0]
        
        return [p["product_name"] for p in zero_sale_products[:limit]]
    
    def should_suppress_publishing(self) -> Dict:
        """Determine if publishing should be suppressed based on recent performance.
        
        Returns:
            Dictionary with:
            - suppress: Boolean indicating if publishing should be suppressed
            - reason: String explaining why publishing should be suppressed (if applicable)
        """
        # Get recent sales data
        sales_metrics = self.storage.get_sales_metrics_since(settings.sales_lookback_days)
        
        # Get recent uploaded products to check consecutive zero-sale products
        recent_uploads = self.storage.get_recent_uploaded_products(limit=settings.zero_sales_suppression_count)
        
        if not recent_uploads:
            # No products yet, don't suppress
            return {"suppress": False, "reason": ""}
        
        # Check if last N products had zero sales
        recent_product_ids = [p['post_id'] for p in recent_uploads[:settings.zero_sales_suppression_count]]
        
        # Match recent products with sales data
        zero_sales_count = 0
        for product_id in recent_product_ids:
            # Check if this product has any sales
            has_sales = any(
                product_id in s.get("product_id", "") 
                for s in sales_metrics 
                if s["sales_count"] > 0
            )
            if not has_sales:
                zero_sales_count += 1
        
        if zero_sales_count >= settings.zero_sales_suppression_count:
            return {
                "suppress": True,
                "reason": f"Last {zero_sales_count} products had zero sales"
            }
        
        # Check refund rate
        if sales_metrics:
            total_sales = sum(p["sales_count"] for p in sales_metrics)
            total_refunds = sum(p["refunds"] for p in sales_metrics)
            
            if total_sales > 0:
                refund_rate = total_refunds / total_sales
                
                if refund_rate > settings.refund_rate_max:
                    return {
                        "suppress": True,
                        "reason": f"Refund rate {refund_rate:.2%} exceeds threshold {settings.refund_rate_max:.2%}"
                    }
        
        return {"suppress": False, "reason": ""}
