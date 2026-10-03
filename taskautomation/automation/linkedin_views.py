import logging

from django.http import JsonResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny

from automation.ai.openai_provider import generate_linkedin_post
from automation.services.linkedin_service import get_linkedin_token, post_linkedin


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

    result = post_linkedin({"generated_text": text})
    if result != "LinkedIn post published successfully 🚀":
        return JsonResponse({"detail": result}, status=502)
    return JsonResponse({"result": result})