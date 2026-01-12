"""
Product generator module using OpenAI API.
Generates structured product specifications from Reddit posts.
"""
import os
import json
from typing import Dict, Any, Optional
from openai import OpenAI

from agents.db import get_reddit_post, save_product_spec

# Load environment variables
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")


class ProductGenerator:
    """Handles product specification generation using OpenAI."""
    
    def __init__(self):
        """Initialize OpenAI client."""
        if not OPENAI_API_KEY:
            raise ValueError("OpenAI API key not found in environment variables")
        
        self.client = OpenAI(api_key=OPENAI_API_KEY)
        print("OpenAI client initialized")
    
    def generate_product_spec(self, post_id: str) -> Optional[Dict[str, Any]]:
        """
        Generate a product specification from a Reddit post.
        
        Args:
            post_id: ID of the Reddit post to generate from
        
        Returns:
            Dict with generated product spec or None on error
        """
        try:
            # Fetch the Reddit post from database
            post = get_reddit_post(post_id)
            if not post:
                print(f"Post {post_id} not found in database")
                return None
            
            # Prepare the prompt for OpenAI
            prompt = self._build_prompt(post)
            
            print(f"Generating product spec for post {post_id}...")
            
            # Call OpenAI API with structured output
            response = self.client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a digital product strategist. "
                            "Generate detailed product specifications for digital products "
                            "based on Reddit discussions. Output must be valid JSON."
                        )
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.7,
                max_tokens=2000,
                response_format={"type": "json_object"}
            )
            
            # Parse the response
            content = response.choices[0].message.content
            product_spec = json.loads(content)
            
            # Add metadata
            product_spec["source_post_id"] = post_id
            product_spec["model_used"] = response.model
            product_spec["generated_at"] = response.created
            
            # Save to database
            spec_id = save_product_spec(
                source_post_id=post_id,
                json_spec=product_spec,
                status="generated"
            )
            
            if spec_id:
                product_spec["id"] = spec_id
                print(f"Product spec generated and saved with ID: {spec_id}")
                return product_spec
            else:
                print("Failed to save product spec to database")
                return None
                
        except Exception as e:
            error_msg = f"Error generating product spec for {post_id}: {str(e)}"
            print(error_msg)
            # Save failed spec to database for tracking
            save_product_spec(
                source_post_id=post_id,
                json_spec={"error": error_msg},
                status="failed"
            )
            return None
    
    def _build_prompt(self, post: Dict[str, Any]) -> str:
        """
        Build a detailed prompt for product generation.
        
        Args:
            post: Dict containing Reddit post data
        
        Returns:
            Formatted prompt string
        """
        title = post.get("title", "")
        body = post.get("body", "")
        subreddit = post.get("subreddit", "")
        
        prompt = f"""Based on the following Reddit post, generate a digital product specification.

Subreddit: r/{subreddit}
Title: {title}
Content: {body[:2000]}  

Generate a JSON response with the following structure:
{{
    "product_name": "Clear, catchy product name",
    "product_type": "Type of digital product (e-book, course, template, guide, etc.)",
    "description": "Detailed product description (2-3 paragraphs)",
    "price": "Suggested price in USD (number only)",
    "target_audience": "Who this product is for",
    "key_features": ["Feature 1", "Feature 2", "Feature 3"],
    "value_proposition": "Why someone should buy this",
    "content_outline": ["Chapter/Section 1", "Chapter/Section 2", "Chapter/Section 3"],
    "tags": ["tag1", "tag2", "tag3"]
}}

Make the product practical, valuable, and directly related to the post's topic.
"""
        return prompt
    
    def generate_batch(self, limit: int = 5) -> Dict[str, Any]:
        """
        Generate product specs for multiple posts that don't have specs yet.
        
        Args:
            limit: Maximum number of specs to generate
        
        Returns:
            Dict with generation results
        """
        from agents.db import get_posts_without_specs
        
        posts = get_posts_without_specs()
        
        if not posts:
            print("No posts without specs found")
            return {
                "processed": 0,
                "generated": 0,
                "failed": 0,
                "specs": []
            }
        
        # Limit the number of posts to process
        posts_to_process = posts[:limit]
        
        results = {
            "processed": 0,
            "generated": 0,
            "failed": 0,
            "specs": []
        }
        
        for post in posts_to_process:
            results["processed"] += 1
            spec = self.generate_product_spec(post["id"])
            
            if spec:
                results["generated"] += 1
                results["specs"].append(spec)
            else:
                results["failed"] += 1
        
        print(f"Batch generation complete: {results['generated']} generated, {results['failed']} failed")
        return results


def generate_product_spec(post_id: str) -> Optional[Dict[str, Any]]:
    """
    Convenience function to generate a product spec for a single post.
    Creates generator instance and returns spec.
    """
    try:
        generator = ProductGenerator()
        return generator.generate_product_spec(post_id)
    except Exception as e:
        print(f"Error in generate_product_spec: {e}")
        return None
