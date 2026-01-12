import os
from services.llm_client import LLMClient
from models.problem import Problem


def extract_problem(post_data: dict, llm_client: LLMClient) -> dict:
    prompt_path = os.path.join(os.path.dirname(__file__), "..", "prompts", "problem_extraction.txt")
    with open(prompt_path, 'r') as f:
        prompt_template = f.read()

    reddit_text = f"""
Title: {post_data['title']}
Subreddit: r/{post_data['subreddit']}
Author: {post_data['author']}
Score: {post_data['score']}
Content: {post_data['body'][:2000]}
"""

    system_prompt = prompt_template.replace('<<REDDIT_POSTS_AND_COMMENTS>>', reddit_text)

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
