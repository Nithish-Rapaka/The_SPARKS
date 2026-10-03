import os
import requests

def ask_gemini(prompt):
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return "ERROR: Gemini API key not found"

# Use the stable versioned name for the v1 endpoint
    url = "https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent"
    headers = {
        "Content-Type": "application/json"
    }

    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt}
                ]
            }
        ]
    }

    response = requests.post(
        f"{url}?key={api_key}",
        headers=headers,
        json=payload
    )

    if response.status_code != 200:
        return f"ERROR: {response.text}"

    data = response.json()
    return data["candidates"][0]["content"]["parts"][0]["text"]
