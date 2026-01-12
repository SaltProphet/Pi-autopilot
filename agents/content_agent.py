import os
from services.llm_client import LLMClient


def generate_content(spec_data: dict, llm_client: LLMClient) -> str:
    prompt_path = os.path.join(os.path.dirname(__file__), "..", "prompts", "product_content.txt")
    with open(prompt_path, 'r') as f:
        prompt_template = f.read()
    
    system_prompt = prompt_template
    system_prompt = system_prompt.replace('<<TYPE>>', spec_data.get('product_type', ''))
    system_prompt = system_prompt.replace('<<BUYER>>', spec_data.get('target_buyer', ''))
    system_prompt = system_prompt.replace('<<JOB>>', spec_data.get('job_to_be_done', ''))
    system_prompt = system_prompt.replace('<<DELIVERABLES>>', ', '.join(spec_data.get('deliverables', [])))
    system_prompt = system_prompt.replace('<<FAILURE_REASON>>', spec_data.get('why_existing_products_fail', ''))
    
    content = llm_client.call_text(system_prompt, "", max_tokens=3000)
    
    return content
