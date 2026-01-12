import json
from openai import OpenAI
from config import settings
from services.cost_governor import CostGovernor


class LLMClient:
    def __init__(self, cost_governor: CostGovernor):
        self.client = OpenAI(api_key=settings.openai_api_key)
        self.model = settings.openai_model
        self.cost_governor = cost_governor

    def call_structured(self, system_prompt: str, user_content: str, max_tokens: int = 2000) -> dict:
        combined_input = system_prompt + user_content
        estimated_input_tokens = self.cost_governor.estimate_tokens(combined_input)
        estimated_output_tokens = max_tokens

        self.cost_governor.check_limits_before_call(estimated_input_tokens, estimated_output_tokens)

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ],
            temperature=0.7,
            max_tokens=max_tokens,
            response_format={"type": "json_object"}
        )

        actual_input_tokens = response.usage.prompt_tokens
        actual_output_tokens = response.usage.completion_tokens

        self.cost_governor.record_usage(actual_input_tokens, actual_output_tokens)

        return json.loads(response.choices[0].message.content)

    def call_text(self, system_prompt: str, user_content: str, max_tokens: int = 3000) -> str:
        combined_input = system_prompt + user_content
        estimated_input_tokens = self.cost_governor.estimate_tokens(combined_input)
        estimated_output_tokens = max_tokens

        self.cost_governor.check_limits_before_call(estimated_input_tokens, estimated_output_tokens)

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ],
            temperature=0.7,
            max_tokens=max_tokens
        )

        actual_input_tokens = response.usage.prompt_tokens
        actual_output_tokens = response.usage.completion_tokens

        self.cost_governor.record_usage(actual_input_tokens, actual_output_tokens)

        return response.choices[0].message.content
