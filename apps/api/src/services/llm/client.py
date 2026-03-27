"""
Anthropic API client with configurable LLM parameters.
Supports vision (image analysis) and text.
"""
import anthropic, base64
from src.config import get_settings

settings = get_settings()


def call_llm(
    system_prompt: str,
    user_message: str,
    max_tokens: int = None,
    temperature: float = None,
    top_k: int = None,
    top_p: float = None,
    image_data: list = None,  # list of {"base64": str, "media_type": str}
) -> dict:
    """
    Call the Anthropic API.
    image_data: optional list of base64-encoded images for vision analysis.
    """
    if not settings.anthropic_api_key:
        raise ValueError("ANTHROPIC_API_KEY not set in .env")

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    model = settings.llm_model_id or "claude-haiku-4-5-20251001"

    # Use settings defaults if not overridden per-call
    max_tokens  = max_tokens  or getattr(settings, "llm_max_tokens",   2048)
    temperature = temperature if temperature is not None else getattr(settings, "llm_temperature", 0.3)
    top_k_val   = top_k       or getattr(settings, "llm_top_k",        None)
    top_p_val   = top_p       or getattr(settings, "llm_top_p",        None)

    # Build content — support text + images
    if image_data:
        content = []
        for img in image_data:
            content.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": img.get("media_type", "image/png"),
                    "data": img["base64"],
                }
            })
        content.append({"type": "text", "text": user_message})
    else:
        content = user_message

    # Build kwargs — only pass optional params if set
    kwargs = {
        "model": model,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "system": system_prompt,
        "messages": [{"role": "user", "content": content}],
    }
    if top_k_val:
        kwargs["top_k"] = top_k_val
    if top_p_val:
        kwargs["top_p"] = top_p_val

    message = client.messages.create(**kwargs)

    text_out = message.content[0].text
    input_tokens  = message.usage.input_tokens
    output_tokens = message.usage.output_tokens

    # Pricing
    if "haiku" in model:
        cost = (input_tokens * 0.80  + output_tokens * 4.0)  / 1_000_000
    elif "sonnet" in model:
        cost = (input_tokens * 3.0   + output_tokens * 15.0) / 1_000_000
    else:
        cost = (input_tokens * 15.0  + output_tokens * 75.0) / 1_000_000

    return {
        "text": text_out,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cost_usd": cost,
        "model_id": model,
    }
