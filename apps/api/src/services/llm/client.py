"""
Anthropic API client — Claude.
Set ANTHROPIC_API_KEY in .env  (console.anthropic.com → API Keys → Create Key)
Default model: claude-3-haiku-20240307 (fast, cheap, works on new accounts)
Upgrade to: claude-3-5-sonnet-20241022 for best quality
"""
import anthropic
from src.config import get_settings

settings = get_settings()


def call_llm(
    system_prompt: str,
    user_message: str,
    max_tokens: int = 2048,
    temperature: float = 0.1,
) -> dict:
    if not settings.anthropic_api_key:
        raise ValueError(
            "ANTHROPIC_API_KEY is not set. Add it to your .env file. "
            "Get a key at console.anthropic.com → API Keys → Create Key"
        )

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    model = settings.llm_model_id or "claude-3-haiku-20240307"

    message = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system_prompt,
        messages=[{"role": "user", "content": user_message}],
    )

    text = message.content[0].text
    input_tokens = message.usage.input_tokens
    output_tokens = message.usage.output_tokens

    # Haiku pricing: $0.25/MTok in, $1.25/MTok out
    # Sonnet pricing: $3/MTok in, $15/MTok out
    if "haiku" in model:
        cost = (input_tokens * 0.25 + output_tokens * 1.25) / 1_000_000
    else:
        cost = (input_tokens * 3 + output_tokens * 15) / 1_000_000

    return {
        "text": text,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cost_usd": cost,
        "model_id": model,
    }
