import os
from services.llm_client import LLMClient
from services.gumroad_client import GumroadClient


def create_listing(spec_data: dict, content: str, llm_client: LLMClient) -> str:
    prompt_path = os.path.join(os.path.dirname(__file__), "..", "prompts", "gumroad_listing.txt")
    with open(prompt_path, 'r') as f:
        prompt_template = f.read()

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

    title_line = [line for line in listing_text.split('\n') if line.startswith('Title:')]
    title = title_line[0].replace('Title:', '').strip() if title_line else spec_data.get('working_title', 'Product')

    description_start = listing_text.find('Description:')
    description_end = listing_text.find('What You Get:')
    description = listing_text[description_start:description_end].replace('Description:', '').strip() if description_start != -1 else listing_text

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
