import os

import requests


OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENAI_MODEL = "gpt-4o-mini"
OPENROUTER_MODEL = "openai/gpt-4o-mini"
SYSTEM_PROMPT = (
    "Write one polished LinkedIn post based on the user's idea. "
    "Keep the meaning accurate, use clear paragraphs, and add a few relevant "
    "hashtags. Return only the post text, with no preamble or quotation marks."
)


def _get_completion(prompt, system_prompt, temperature, max_tokens=900):
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OpenAI API key is not configured")

    uses_openrouter = api_key.startswith("sk-or-")
    headers = {"Authorization": f"Bearer {api_key}"}
    if uses_openrouter:
        headers["HTTP-Referer"] = "http://localhost:5173"
        headers["X-Title"] = "TaskBot"

    response = requests.post(
        OPENROUTER_API_URL if uses_openrouter else OPENAI_API_URL,
        headers=headers,
        json={
            "model": OPENROUTER_MODEL if uses_openrouter else OPENAI_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        },
        timeout=30,
    )
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]


def generate_linkedin_post(prompt):
    return _get_completion(prompt, SYSTEM_PROMPT, temperature=0.7)