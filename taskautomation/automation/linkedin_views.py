import logging
from django.http import JsonResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
import os
import uuid
from pathlib import Path
from django.conf import settings
from automation.ai.openai_provider import generate_linkedin_post
from automation.ai.image_provider import generate_image
from automation.services.linkedin_service import (
    get_linkedin_token,
    post_linkedin,
)

@api_view(["POST"])
@permission_classes([AllowAny])
def linkedin_upload_image(request):
    unauthorized = _unauthorized(request)

    if unauthorized:
        return unauthorized

    uploaded_file = request.FILES.get("image")

    if not uploaded_file:
        return JsonResponse(
            {
                "success": False,
                "detail": "Please select an image."
            },
            status=400,
        )

    allowed_extensions = {
        ".jpg",
        ".jpeg",
        ".png",
        ".webp",
    }

    original_name = uploaded_file.name or ""
    extension = Path(original_name).suffix.lower()

    if extension not in allowed_extensions:
        return JsonResponse(
            {
                "success": False,
                "detail": (
                    "Unsupported image format. "
                    "Use JPG, JPEG, PNG, or WEBP."
                ),
            },
            status=400,
        )

    max_size = 10 * 1024 * 1024

    if uploaded_file.size > max_size:
        return JsonResponse(
            {
                "success": False,
                "detail": "Image must be smaller than 10 MB.",
            },
            status=400,
        )

    upload_directory = (
        Path(settings.MEDIA_ROOT)
        / "uploaded_images"
    )

    upload_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    filename = (
        f"linkedin_{uuid.uuid4().hex}{extension}"
    )

    image_path = upload_directory / filename

    with open(image_path, "wb+") as destination:
        for chunk in uploaded_file.chunks():
            destination.write(chunk)

    image_url = (
        f"{settings.MEDIA_URL}"
        f"uploaded_images/"
        f"{filename}"
    )
    return JsonResponse(
        {
            "success": True,
            "image_url": image_url,
            "filename": filename,
        }
    )

logger = logging.getLogger(__name__)
def _unauthorized(request):
    if request.session.get("demo_authenticated"):
        return None
    return JsonResponse({"detail": "Authentication required"}, status=401)


@api_view(["GET"])
@permission_classes([AllowAny])
def linkedin_status(request):
    unauthorized = _unauthorized(request)
    if unauthorized:
        return unauthorized
    return JsonResponse({"connected": bool(get_linkedin_token())})


@api_view(["POST"])
@permission_classes([AllowAny])
def linkedin_preview(request):
    unauthorized = _unauthorized(request)
    if unauthorized:
        return unauthorized

    prompt = str(request.data.get("prompt", "")).strip()
    if not prompt:
        return JsonResponse({"detail": "Describe the post you want to create."}, status=400)

    try:
        text = generate_linkedin_post(prompt).strip()
    except Exception:
        logger.exception("LinkedIn post generation failed")
        return JsonResponse(
            {"detail": "Could not generate a post. Check the OpenAI API key and account access."},
            status=502,
        )

    if not text:
        return JsonResponse({"detail": "The AI returned an empty post."}, status=502)

    return JsonResponse({"text": text[:3000], "characters": min(len(text), 3000)})

@api_view(["POST"])
@permission_classes([AllowAny])
def linkedin_generate_image(request):
    unauthorized = _unauthorized(request)
    if unauthorized:
        return unauthorized

    image_requirement = str(
        request.data.get("image_requirement", "")
    ).strip()

    linkedin_post = str(
        request.data.get("linkedin_post", "")
    ).strip()

    if not image_requirement:
        return JsonResponse(
            {"detail": "Please describe what image you want."},
            status=400,
        )

    if not linkedin_post:
        return JsonResponse(
            {"detail": "LinkedIn post is required."},
            status=400,
        )

    try:
        image_path = generate_image(
            user_requirement=image_requirement,
            linkedin_post=linkedin_post,
        )

        # Convert filesystem path to a browser-accessible URL
        image_url = "/" + image_path.replace("\\", "/")

        return JsonResponse(
            {
                "success": True,
                "image_url": image_url,
            }
        )

    except Exception as e:
        logger.exception("LinkedIn image generation failed")

        return JsonResponse(
            {
                "success": False,
                "detail": str(e),
            },
            status=502,
        )


@api_view(["POST"])
@permission_classes([AllowAny])
def linkedin_publish_post(request):
    unauthorized = _unauthorized(request)
    if unauthorized:
        return unauthorized

    text = str(request.data.get("text", "")).strip()
    if not text:
        return JsonResponse({"detail": "There is no post to publish."}, status=400)
    if len(text) > 3000:
        return JsonResponse({"detail": "LinkedIn posts are limited to 3,000 characters."}, status=400)
    if not get_linkedin_token():
        return JsonResponse({"detail": "Connect your LinkedIn account before publishing."}, status=400)

    details = {"generated_text": text}
    image_url = str(request.data.get("image_url", "")).strip()
    if image_url:
        image_prefix = f"{settings.MEDIA_URL}uploaded_images/"
        image_filename = image_url[len(image_prefix):] if image_url.startswith(image_prefix) else ""
        if not image_filename or Path(image_filename).name != image_filename:
            return JsonResponse({"detail": "Choose a valid uploaded image."}, status=400)

        image_path = Path(settings.MEDIA_ROOT) / "uploaded_images" / image_filename
        if not image_path.is_file():
            return JsonResponse({"detail": "The uploaded image could not be found. Please upload it again."}, status=400)
        details["image_path"] = str(image_path)

    result = post_linkedin(details)
    if result != "LinkedIn post published successfully 🚀":
        return JsonResponse({"detail": result}, status=502)
    return JsonResponse({"result": result})