import os
import uuid
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types


load_dotenv()


GEMINI_IMAGE_MODEL = "gemini-3.1-flash-image"


def generate_image(user_requirement, linkedin_post):
    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is not configured in the .env file"
        )

    prompt = f"""
Create a professional image for a LinkedIn post.

USER'S IMAGE REQUIREMENT:
{user_requirement}

LINKEDIN POST:
{linkedin_post}

IMAGE REQUIREMENTS:
- Professional and suitable for LinkedIn
- Modern and visually appealing
- Clearly communicate the main idea of the LinkedIn post
- Follow the user's image requirement carefully
- Clean professional composition
- Appropriate lighting and visual hierarchy
- Suitable for a professional LinkedIn audience
- Avoid unnecessary text inside the image
- Do not add watermarks
- Do not add random logos or brands
"""

    try:
        client = genai.Client(api_key=api_key)

        response = client.models.generate_content(
            model=GEMINI_IMAGE_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_modalities=["TEXT", "IMAGE"],
            ),
        )

        candidates = response.candidates

        if not candidates:
            raise RuntimeError(
                "Gemini returned no candidates."
            )

        candidate = candidates[0]

        if candidate.content is None:
            raise RuntimeError(
                "Gemini returned no content."
            )

        parts = candidate.content.parts

        if not parts:
            raise RuntimeError(
                "Gemini returned no content parts."
            )

        for part in parts:
            if part.inline_data is not None:
                image_bytes = part.inline_data.data

                if not image_bytes:
                    raise RuntimeError(
                        "Gemini returned empty image data."
                    )

                media_directory = (
                    Path(__file__).resolve().parent.parent.parent
                    / "media"
                    / "generated_images"
                )

                media_directory.mkdir(
                    parents=True,
                    exist_ok=True,
                )

                filename = (
                    f"linkedin_{uuid.uuid4().hex}.png"
                )

                image_path = media_directory / filename

                with open(image_path, "wb") as image_file:
                    image_file.write(image_bytes)

                return str(image_path)

        raise RuntimeError(
            "Gemini did not return an image."
        )

    except Exception as e:
        raise RuntimeError(
            f"Gemini image generation failed: {str(e)}"
        ) from e