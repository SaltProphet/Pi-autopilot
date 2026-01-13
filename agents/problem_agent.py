import os
from services.llm_client import LLMClient
from services.sanitizer import InputSanitizer
from models.problem import Problem


def _truncate_preserving_boundary(text: str, max_length: int) -> str:
    """
    Truncate text to at most max_length characters, preferring to cut at
    paragraph, line, or sentence boundaries rather than mid-sentence.
    """
    if not text or len(text) <= max_length:
        return text

    # Start with a hard cap, then look backwards for a nicer break point.
    candidate = text[:max_length]

    # Prefer paragraph or line breaks.
    break_positions = [
        candidate.rfind("\n\n"),
        candidate.rfind("\n"),
        candidate.rfind(". "),
        candidate.rfind("! "),
        candidate.rfind("? "),
    ]
    best_pos = max(break_positions)

    if best_pos == -1:
        # No natural boundary found; fall back to hard truncation.
        return candidate

    # Include the boundary character(s) in the result.
    return candidate[: best_pos + 1]


def extract_problem(post_data: dict, llm_client: LLMClient, sales_feedback_text: str = None) -> dict:
    sanitizer = InputSanitizer()
    
    prompt_path = os.path.join(os.path.dirname(__file__), "..", "prompts", "problem_extraction.txt")
    try:
        with open(prompt_path, 'r', encoding='utf-8') as f:
            prompt_template = f.read()
    except OSError as e:
        raise RuntimeError(f"Failed to read problem extraction prompt file at {prompt_path}: {e}") from e
    
    body_text = post_data.get('body', '')
    # Sanitize Reddit content before processing
    body_text = sanitizer.sanitize_reddit_content(body_text)
    truncated_body = _truncate_preserving_boundary(body_text, 2000)
    
    reddit_text = f"""
Title: {post_data['title']}
Subreddit: r/{post_data['subreddit']}
Author: {post_data['author']}
Score: {post_data['score']}
Content: {truncated_body}
"""
    
    system_prompt = prompt_template.replace('<<REDDIT_POSTS_AND_COMMENTS>>', reddit_text)
    
    # Inject sales feedback if provided
    if sales_feedback_text:
        system_prompt = system_prompt + f"\n\nSALES FEEDBACK:\n{sales_feedback_text}\n\nConsider recent sales performance when evaluating this problem. Favor topics similar to products that sold well. Be cautious about topics similar to products with zero sales."
    
    result = llm_client.call_structured(system_prompt, "", max_tokens=1500)
    
    problem = Problem(
        discard=result.get("discard", True),
        problem_summary=result.get("problem_summary", ""),
        who_has_it=result.get("who_has_it", ""),
        why_it_matters=result.get("why_it_matters", ""),
        current_bad_solutions=result.get("current_bad_solutions", []),
        urgency_score=result.get("urgency_score", 0),
        evidence_quotes=result.get("evidence_quotes", [])
    )
    
    return problem.to_dict()
