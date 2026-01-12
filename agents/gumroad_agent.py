import os
from services.llm_client import LLMClient
from services.gumroad_client import GumroadClient


def create_listing(spec_data: dict, content: str, llm_client: LLMClient) -> str:
    prompt_path = os.path.join(os.path.dirname(__file__), "..", "prompts", "gumroad_listing.txt")
    try:
        with open(prompt_path, 'r', encoding='utf-8') as f:
            prompt_template = f.read()
    except OSError as e:
        raise RuntimeError(f"Failed to read Gumroad listing prompt file at {prompt_path}: {e}") from e
    
    product_summary = f"""
Product: {spec_data.get('working_title', '')}
Type: {spec_data.get('product_type', '')}
Target Buyer: {spec_data.get('target_buyer', '')}
Job to be Done: {spec_data.get('job_to_be_done', '')}
Why Existing Products Fail: {spec_data.get('why_existing_products_fail', '')}
Deliverables: {', '.join(spec_data.get('deliverables', []))}
Content Preview: {content[:500]}
"""
    
    system_prompt = prompt_template.replace('<<PRODUCT_SUMMARY + CONTENT>>', product_summary)
    
    listing_text = llm_client.call_text(system_prompt, "", max_tokens=1500)
    
    return listing_text


def upload_to_gumroad(spec_data: dict, listing_text: str, content_file_path: str) -> dict:
    gumroad_client = GumroadClient()
    
    # Parse listing with validation
    title = _extract_field(listing_text, 'Title:', spec_data.get('working_title', 'Product'))
    description = _extract_description(listing_text)
    
    # Validate essential fields
    if not title or len(title.strip()) < 3:
        raise ValueError(f"Invalid title extracted from listing: '{title}'")
    
    if not description or len(description.strip()) < 10:
        raise ValueError(f"Invalid description extracted from listing (length: {len(description)})")
    
    price_cents = int(spec_data.get('price_recommendation', 10) * 100)
    
    product = gumroad_client.create_product(
        name=title[:100],
        description=description,
        price_cents=price_cents
    )
    
    return {
        "product_id": product.get("id") if product else None,
        "product_url": product.get("short_url") if product else None,
        "success": product is not None
    }


def _extract_field(text: str, marker: str, default: str) -> str:
    """Extract a single-line field from listing text."""
    lines = [line for line in text.split('\n') if line.startswith(marker)]
    if lines:
        return lines[0].replace(marker, '').strip()
    return default


def _extract_description(text: str) -> str:
    """Extract description section from listing text."""
    description_start = text.find('Description:')
    if description_start == -1:
        # Fallback: use entire text if no marker found
        return text.strip()
    
    # Try to find end marker
    end_markers = ['What You Get:', 'Who This Is NOT For:', 'FAQ']
    description_end = len(text)
    
    for marker in end_markers:
        pos = text.find(marker, description_start)
        if pos != -1:
            description_end = min(description_end, pos)
    
    description = text[description_start:description_end].replace('Description:', '').strip()
    return description if description else text.strip()
