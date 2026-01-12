"""
Main FastAPI application for Pi-Autopilot.
Raspberry Pi AI-Orchestrated Reddit-to-Gumroad Digital Product Pipeline.
"""
import os
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from dotenv import load_dotenv

from agents.reddit_scraper import scrape_subreddit
from agents.product_generator import generate_product_spec
from agents.gumroad_uploader import push_product_to_gumroad
from agents.metrics import metrics, get_system_metrics
from agents.db import init_database

# Load environment variables
load_dotenv()

# Initialize database
init_database()

# Create FastAPI app
app = FastAPI(
    title="Pi-Autopilot",
    description="Reddit-to-Gumroad Digital Product Pipeline",
    version="1.0.0"
)


@app.middleware("http")
async def metrics_middleware(request, call_next):
    """Middleware to track request metrics."""
    metrics.increment_requests()
    try:
        response = await call_next(request)
        return response
    except Exception as e:
        metrics.increment_errors()
        raise


@app.get("/health")
async def health_check():
    """
    Health check endpoint.
    Returns system status and basic metrics.
    """
    try:
        system_metrics = get_system_metrics()
        return {
            "status": "healthy",
            "service": "pi-autopilot",
            "version": "1.0.0",
            "metrics": system_metrics
        }
    except Exception as e:
        metrics.increment_errors()
        return JSONResponse(
            status_code=500,
            content={
                "status": "unhealthy",
                "error": str(e)
            }
        )


@app.post("/run/scrape/{subreddit}")
async def scrape_reddit_endpoint(subreddit: str, limit: int = 10):
    """
    Scrape posts from a specified subreddit.
    
    Args:
        subreddit: Name of the subreddit to scrape (without r/)
        limit: Number of posts to fetch (default 10, max 50)
    
    Returns:
        Scrape results including number of posts saved
    """
    try:
        # Validate limit
        if limit < 1 or limit > 50:
            raise HTTPException(
                status_code=400,
                detail="Limit must be between 1 and 50"
            )
        
        print(f"API: Scraping r/{subreddit} with limit {limit}")
        metrics.increment_scrapes()
        
        # Perform scrape
        result = scrape_subreddit(subreddit, limit=limit)
        
        # Check for errors
        if "error" in result:
            metrics.increment_errors()
            raise HTTPException(
                status_code=500,
                detail=result["error"]
            )
        
        return {
            "success": True,
            "subreddit": subreddit,
            "scraped": result["scraped"],
            "saved": result["saved"],
            "skipped": result["skipped"],
            "message": f"Successfully scraped r/{subreddit}"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        metrics.increment_errors()
        print(f"Error in scrape endpoint: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to scrape subreddit: {str(e)}"
        )


@app.post("/gen/product/{post_id}")
async def generate_product_endpoint(post_id: str):
    """
    Generate a product specification from a Reddit post.
    
    Args:
        post_id: Reddit post ID
    
    Returns:
        Generated product specification
    """
    try:
        print(f"API: Generating product spec for post {post_id}")
        metrics.increment_generations()
        
        # Generate product spec
        spec = generate_product_spec(post_id)
        
        if not spec:
            metrics.increment_errors()
            raise HTTPException(
                status_code=404,
                detail=f"Failed to generate product spec for post {post_id}"
            )
        
        return {
            "success": True,
            "post_id": post_id,
            "product_spec_id": spec.get("id"),
            "product_spec": spec,
            "message": "Product specification generated successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        metrics.increment_errors()
        print(f"Error in generate endpoint: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate product: {str(e)}"
        )


@app.post("/products/push/{product_spec_id}")
async def push_product_endpoint(product_spec_id: int):
    """
    Push a product specification to Gumroad.
    
    Args:
        product_spec_id: ID of the product spec in database
    
    Returns:
        Gumroad product details
    """
    try:
        print(f"API: Pushing product spec {product_spec_id} to Gumroad")
        metrics.increment_uploads()
        
        # Push to Gumroad
        result = push_product_to_gumroad(product_spec_id)
        
        if not result or not result.get("success"):
            metrics.increment_errors()
            raise HTTPException(
                status_code=500,
                detail=f"Failed to push product to Gumroad"
            )
        
        return {
            "success": True,
            "product_spec_id": product_spec_id,
            "gumroad_product_id": result.get("gumroad_product_id"),
            "product_url": result.get("product_url"),
            "product_name": result.get("product_name"),
            "message": "Product successfully created on Gumroad"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        metrics.increment_errors()
        print(f"Error in push endpoint: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to push product: {str(e)}"
        )


@app.get("/metrics")
async def metrics_endpoint():
    """
    Get system metrics and statistics.
    
    Returns:
        Current system metrics
    """
    try:
        return get_system_metrics()
    except Exception as e:
        metrics.increment_errors()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get metrics: {str(e)}"
        )


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "service": "Pi-Autopilot",
        "description": "Reddit-to-Gumroad Digital Product Pipeline",
        "version": "1.0.0",
        "endpoints": {
            "health": "GET /health",
            "scrape": "POST /run/scrape/{subreddit}?limit=10",
            "generate": "POST /gen/product/{post_id}",
            "push": "POST /products/push/{product_spec_id}",
            "metrics": "GET /metrics"
        }
    }


if __name__ == "__main__":
    import uvicorn
    
    host = os.getenv("APP_HOST", "0.0.0.0")
    port = int(os.getenv("APP_PORT", 8000))
    
    print(f"Starting Pi-Autopilot on {host}:{port}")
    uvicorn.run(app, host=host, port=port)
