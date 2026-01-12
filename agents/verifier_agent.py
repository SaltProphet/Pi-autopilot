import os
from services.llm_client import LLMClient
from models.verdict import Verdict


def verify_content(content: str, llm_client: LLMClient) -> dict:
    prompt_path = os.path.join(os.path.dirname(__file__), "..", "prompts", "verifier.txt")
    try:
        with open(prompt_path, 'r', encoding='utf-8') as f:
            prompt_template = f.read()
    except OSError as e:
        raise RuntimeError(f"Failed to read verifier prompt file at {prompt_path}: {e}") from e
    
    system_prompt = prompt_template
    
    result = llm_client.call_structured(system_prompt, content, max_tokens=1000)
    
    verdict = Verdict(
        pass_=result.get("pass", False),
        reasons=result.get("reasons", []),
        missing_elements=result.get("missing_elements", []),
        generic_language_detected=result.get("generic_language_detected", False),
        example_quality_score=int(result.get("example_quality_score", 0))
    )
    
    verdict_dict = verdict.to_dict()
    
    if verdict.example_quality_score < 7 or verdict.generic_language_detected or len(verdict.missing_elements) > 0:
        verdict_dict["pass"] = False
    
    return verdict_dict
