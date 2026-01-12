import json
import os
from services.llm_client import LLMClient
from models.product_spec import ProductSpec


def generate_spec(problem_data: dict, llm_client: LLMClient) -> dict:
    prompt_path = os.path.join(os.path.dirname(__file__), "..", "prompts", "product_spec.txt")
    with open(prompt_path, 'r') as f:
        prompt_template = f.read()

    problem_json = json.dumps(problem_data, indent=2)
    system_prompt = prompt_template.replace('<<PROBLEM_JSON>>', problem_json)

    result = llm_client.call_structured(system_prompt, "", max_tokens=1500)

    spec = ProductSpec(
        build=result.get("build", False),
        product_type=result.get("product_type", ""),
        working_title=result.get("working_title", ""),
        target_buyer=result.get("target_buyer", ""),
        job_to_be_done=result.get("job_to_be_done", ""),
        why_existing_products_fail=result.get("why_existing_products_fail", ""),
        deliverables=result.get("deliverables", []),
        price_recommendation=float(result.get("price_recommendation", 0)),
        confidence=int(result.get("confidence", 0))
    )

    return spec.to_dict()
