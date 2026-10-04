import logging
import os
import uuid
from pathlib import Path

from bson import ObjectId
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from pymongo.errors import PyMongoError
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny

from automation.ai.image_provider import generate_image
from automation.ai.openai_provider import generate_linkedin_post
from automation.services.linkedin_history import (
    MongoHistoryConfigurationError,
    delete_linkedin_posts,
    get_linkedin_posts,
    save_linkedin_post,
)
from automation.services.linkedin_service import (
    LinkedInPublishOutcomeUnknown,
    get_linkedin_token,
    post_linkedin,
)


logger = logging.getLogger(__name__)


def _unauthorized(request):
    """
    Check the demo authentication session.
    """
    if request.session.get("demo_authenticated"):
        return None

    return JsonResponse(
        {
            "detail": "Authentication required",
        },
        status=401,
    )


# ============================================================
# IMAGE UPLOAD
# ============================================================

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
                "detail": "Please select an image.",
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


# ============================================================
# LINKEDIN STATUS
# ============================================================

@api_view(["GET"])
@permission_classes([AllowAny])
def linkedin_status(request):
    unauthorized = _unauthorized(request)

    if unauthorized:
        return unauthorized

    try:
        connected = bool(get_linkedin_token())
    except Exception:
        logger.exception("Could not check LinkedIn connection")
        connected = False

    return JsonResponse(
        {
            "connected": connected,
        }
    )


# ============================================================
# LINKEDIN POST HISTORY
# ============================================================

@api_view(["GET", "DELETE"])
@permission_classes([AllowAny])
def linkedin_posts(request):
    unauthorized = _unauthorized(request)

    if unauthorized:
        return unauthorized

    # --------------------------------------------------------
    # DELETE HISTORY
    # --------------------------------------------------------

    if request.method == "DELETE":
        if not hasattr(request.data, "get"):
            return JsonResponse(
                {
                    "detail": (
                        "Provide a JSON object to delete post history."
                    )
                },
                status=400,
            )

        clear_all = request.data.get("all") is True
        post_ids = request.data.get("ids")

        if clear_all == (post_ids is not None):
            return JsonResponse(
                {
                    "detail": (
                        "Choose either all posts or a list "
                        "of post IDs."
                    )
                },
                status=400,
            )

        if post_ids is not None and (
            not isinstance(post_ids, list)
            or not post_ids
            or len(post_ids) > 50
            or any(
                not isinstance(post_id, str)
                or not ObjectId.is_valid(post_id)
                for post_id in post_ids
            )
        ):
            return JsonResponse(
                {
                    "detail": (
                        "Select between 1 and 50 valid post IDs."
                    )
                },
                status=400,
            )

        try:
            deleted_count = delete_linkedin_posts(
                None if clear_all else post_ids
            )

        except (
            MongoHistoryConfigurationError,
            PyMongoError,
        ):
            logger.exception(
                "Could not delete LinkedIn post history"
            )

            return JsonResponse(
                {
                    "detail": (
                        "Could not delete post history. "
                        "Check MongoDB connectivity and "
                        "the Django terminal."
                    )
                },
                status=503,
            )

        return JsonResponse(
            {
                "deleted_count": deleted_count,
            }
        )

    # --------------------------------------------------------
    # GET HISTORY
    # --------------------------------------------------------

    try:
        posts = get_linkedin_posts()

    except (
        MongoHistoryConfigurationError,
        PyMongoError,
    ):
        logger.exception(
            "Could not retrieve LinkedIn post history"
        )

        return JsonResponse(
            {
                "detail": (
                    "Could not load post history. "
                    "Verify MONGODB_URI and MONGODB_DATABASE, "
                    "and check the Django terminal for the "
                    "MongoDB connection error."
                )
            },
            status=503,
        )

    return JsonResponse(
        {
            "posts": posts,
        }
    )


# ============================================================
# GENERATE LINKEDIN POST
# ============================================================

@api_view(["POST"])
@permission_classes([AllowAny])
def linkedin_preview(request):
    unauthorized = _unauthorized(request)

    if unauthorized:
        return unauthorized

    prompt = str(
        request.data.get("prompt", "")
    ).strip()

    if not prompt:
        return JsonResponse(
            {
                "detail": (
                    "Describe the post you want to create."
                )
            },
            status=400,
        )

    try:
        text = generate_linkedin_post(prompt).strip()

    except Exception:
        logger.exception(
            "LinkedIn post generation failed"
        )

        return JsonResponse(
            {
                "detail": (
                    "Could not generate a post. "
                    "Check the OpenAI API key and account access."
                )
            },
            status=502,
        )

    if not text:
        return JsonResponse(
            {
                "detail": "The AI returned an empty post.",
            },
            status=502,
        )

    text = text[:3000]

    return JsonResponse(
        {
            "text": text,
            "characters": len(text),
        }
    )


# ============================================================
# GENERATE IMAGE
# ============================================================

@api_view(["POST"])
@permission_classes([AllowAny])
def linkedin_generate_image(request):
    unauthorized = _unauthorized(request)

    if unauthorized:
        return unauthorized

    image_requirement = str(
        request.data.get(
            "image_requirement",
            "",
        )
    ).strip()

    linkedin_post = str(
        request.data.get(
            "linkedin_post",
            "",
        )
    ).strip()

    if not image_requirement:
        return JsonResponse(
            {
                "detail": "Please describe what image you want.",
            },
            status=400,
        )

    if not linkedin_post:
        return JsonResponse(
            {
                "detail": "LinkedIn post is required.",
            },
            status=400,
        )

    try:
        image_path = generate_image(
            user_requirement=image_requirement,
            linkedin_post=linkedin_post,
        )

        image_url = "/" + image_path.replace(
            "\\",
            "/",
        )

        return JsonResponse(
            {
                "success": True,
                "image_url": image_url,
            }
        )

    except Exception as exc:
        logger.exception(
            "LinkedIn image generation failed"
        )

        return JsonResponse(
            {
                "success": False,
                "detail": str(exc),
            },
            status=502,
        )


# ============================================================
# PUBLISH LINKEDIN POST
# ============================================================

@api_view(["POST"])
@permission_classes([AllowAny])
def linkedin_publish_post(request):
    """
    Publish a LinkedIn post.

    IMPORTANT FLOW:

        1. Validate request.
        2. Publish to LinkedIn.
        3. Only after LinkedIn succeeds, save history to MongoDB.
        4. If MongoDB fails, LinkedIn is STILL considered successful.
        5. Never retry LinkedIn because MongoDB failed.
    """

    unauthorized = _unauthorized(request)

    if unauthorized:
        return unauthorized

    # --------------------------------------------------------
    # Validate post text
    # --------------------------------------------------------

    text = str(
        request.data.get("text", "")
    ).strip()

    if not text:
        return JsonResponse(
            {
                "published": False,
                "history_saved": False,
                "detail": "There is no post to publish.",
            },
            status=400,
        )

    if len(text) > 3000:
        return JsonResponse(
            {
                "published": False,
                "history_saved": False,
                "detail": (
                    "LinkedIn posts are limited to "
                    "3,000 characters."
                ),
            },
            status=400,
        )

    # --------------------------------------------------------
    # Check LinkedIn connection
    # --------------------------------------------------------

    try:
        token = get_linkedin_token()

    except Exception:
        logger.exception(
            "Could not read LinkedIn token"
        )

        return JsonResponse(
            {
                "published": False,
                "history_saved": False,
                "detail": (
                    "Could not verify the LinkedIn connection."
                ),
            },
            status=502,
        )

    if not token:
        return JsonResponse(
            {
                "published": False,
                "history_saved": False,
                "detail": (
                    "Connect your LinkedIn account "
                    "before publishing."
                ),
            },
            status=400,
        )

    # --------------------------------------------------------
    # Build LinkedIn post details
    # --------------------------------------------------------

    details = {
        "generated_text": text,
    }

    image_url = str(
        request.data.get("image_url", "")
    ).strip()

    if image_url:
        image_prefix = (
            f"{settings.MEDIA_URL}"
            "uploaded_images/"
        )

        image_filename = (
            image_url[len(image_prefix):]
            if image_url.startswith(image_prefix)
            else ""
        )

        # Prevent path traversal.
        if (
            not image_filename
            or Path(image_filename).name
            != image_filename
        ):
            return JsonResponse(
                {
                    "published": False,
                    "history_saved": False,
                    "detail": (
                        "Choose a valid uploaded image."
                    ),
                },
                status=400,
            )

        image_path = (
            Path(settings.MEDIA_ROOT)
            / "uploaded_images"
            / image_filename
        )

        if not image_path.is_file():
            return JsonResponse(
                {
                    "published": False,
                    "history_saved": False,
                    "detail": (
                        "The uploaded image could not "
                        "be found. Please upload it again."
                    ),
                },
                status=400,
            )

        details["image_path"] = str(image_path)

    # --------------------------------------------------------
    # STEP 1
    # PUBLISH TO LINKEDIN
    # --------------------------------------------------------

    try:
        linkedin_result = post_linkedin(details)

    except LinkedInPublishOutcomeUnknown:
        logger.exception(
            "LinkedIn publish response was not received; outcome is unknown"
        )
        return JsonResponse(
            {
                "published": None,
                "history_saved": False,
                "result": (
                    "LinkedIn did not confirm the result. Check your "
                    "LinkedIn profile before trying again to avoid a duplicate."
                ),
            },
            status=200,
        )

    except Exception as exc:
        logger.exception(
            "LinkedIn publication failed"
        )

        return JsonResponse(
            {
                "published": False,
                "history_saved": False,
                "detail": (
                    f"LinkedIn publication failed: {exc}"
                ),
            },
            status=502,
        )

    # --------------------------------------------------------
    # Verify the LinkedIn service result
    # --------------------------------------------------------

    if linkedin_result != (
        "LinkedIn post published successfully 🚀"
    ):
        logger.error(
            "LinkedIn service returned unsuccessful result: %r",
            linkedin_result,
        )

        return JsonResponse(
            {
                "published": False,
                "history_saved": False,
                "detail": str(linkedin_result),
            },
            status=502,
        )

    # --------------------------------------------------------
    # IMPORTANT:
    #
    # At this point LinkedIn has already published the post.
    #
    # From here onward, NO MongoDB error should make this
    # endpoint return published=False.
    # --------------------------------------------------------

    prompt = str(
        request.data.get("prompt", "")
    ).strip()

    # --------------------------------------------------------
    # STEP 2
    # SAVE HISTORY TO MONGODB
    # --------------------------------------------------------

    try:
        saved_post = save_linkedin_post(
            prompt=prompt,
            text=text,
            image_url=image_url or None,
        )

    except (
        MongoHistoryConfigurationError,
        PyMongoError,
    ) as exc:
        logger.exception(
            "LinkedIn post was published, "
            "but MongoDB history save failed"
        )

        return JsonResponse(
            {
                "published": True,
                "history_saved": False,
                "result": (
                    "LinkedIn post published successfully 🚀"
                ),
                "history_warning": (
                    "The post is live on LinkedIn, "
                    "but could not be saved to post history. "
                    "Check MongoDB connectivity."
                ),
            },
            status=200,
        )

    except Exception as exc:
        # Catch unexpected Mongo/history errors too.
        #
        # LinkedIn is already successful, therefore this
        # MUST NOT become a publication failure.
        logger.exception(
            "Unexpected error while saving "
            "LinkedIn post history"
        )

        return JsonResponse(
            {
                "published": True,
                "history_saved": False,
                "result": (
                    "LinkedIn post published successfully 🚀"
                ),
                "history_warning": (
                    "The post is live on LinkedIn, "
                    "but could not be saved to post history."
                ),
            },
            status=200,
        )

    # --------------------------------------------------------
    # STEP 3
    # BOTH LINKEDIN AND MONGODB SUCCEEDED
    # --------------------------------------------------------

    return JsonResponse(
        {
            "published": True,
            "history_saved": True,
            "result": (
                "LinkedIn post published successfully 🚀"
            ),
            "post": saved_post,
        },
        status=200,
    )