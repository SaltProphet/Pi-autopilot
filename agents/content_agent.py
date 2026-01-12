import os
from services.llm_client import LLMClient
from services.sanitizer import InputSanitizer


def generate_content(spec_data: dict, llm_client: LLMClient) -> str:
    sanitizer = InputSanitizer()
    
    prompt_path = os.path.join(os.path.dirname(__file__), "..", "prompts", "product_content.txt")
    try:
        with open(prompt_path, 'r', encoding='utf-8') as f:
            prompt_template = f.read()
    except OSError as e:
        raise RuntimeError(f"Failed to read product content prompt file at {prompt_path}: {e}") from e
    
    # Safely get values with defaults to prevent placeholder issues
    system_prompt = prompt_template
    system_prompt = system_prompt.replace('<<TYPE>>', spec_data.get('product_type', 'digital product'))
    system_prompt = system_prompt.replace('<<BUYER>>', spec_data.get('target_buyer', 'buyers'))
    system_prompt = system_prompt.replace('<<JOB>>', spec_data.get('job_to_be_done', 'solve a problem'))
    system_prompt = system_prompt.replace('<<DELIVERABLES>>', ', '.join(spec_data.get('deliverables', ['content'])))
    system_prompt = system_prompt.replace('<<FAILURE_REASON>>', spec_data.get('why_existing_products_fail', 'not specified'))
    
    content = llm_client.call_text(system_prompt, "", max_tokens=3000)
    
    # Sanitize generated content before returning
    content = sanitizer.sanitize_gumroad_content(content)
    
    return content
