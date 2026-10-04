import os
import json
import mimetypes
from pathlib import Path

import requests


# ---------------------------------------------------------
# LinkedIn token file
# ---------------------------------------------------------

# Project structure:
#
# taskautomation/
#   automation/
#       services/
#           linkedin_service.py
#       linkedin_tokens.json
#

BASE_DIR = Path(__file__).resolve().parent.parent
TOKEN_FILE = BASE_DIR / "linkedin_tokens.json"


# Cache for person URN
_PERSON_URN_CACHE = None


class LinkedInPublishOutcomeUnknown(Exception):
    """The publish request failed before its result could be confirmed."""


# ---------------------------------------------------------
# LinkedIn token
# ---------------------------------------------------------


def get_linkedin_token():
    """
    Read the latest LinkedIn access token from linkedin_tokens.json.
    """

    if not TOKEN_FILE.exists():
        print(f"ERROR: LinkedIn token file not found: {TOKEN_FILE}")
        return None

    try:
        with open(TOKEN_FILE, "r", encoding="utf-8") as f:
            token_data = json.load(f)

        token = token_data.get("access_token")

        if not token:
            print("ERROR: access_token not found in linkedin_tokens.json")
            return None

        print("DEBUG: LinkedIn access token loaded successfully")

        return token

    except Exception as e:
        print(f"ERROR reading LinkedIn token: {e}")
        return None


# ---------------------------------------------------------
# Get LinkedIn Person URN
# ---------------------------------------------------------


def get_person_urn(token=None):
    """
    Get the authenticated LinkedIn member's Person URN.

    Uses LinkedIn OpenID Connect userinfo endpoint.
    """

    global _PERSON_URN_CACHE

    if _PERSON_URN_CACHE:
        return _PERSON_URN_CACHE

    if token is None:
        token = get_linkedin_token()

    if not token:
        print("ERROR: LinkedIn access token not available")
        return None

    try:
        url = "https://api.linkedin.com/v2/userinfo"

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        print("DEBUG: Fetching LinkedIn user information...")

        response = requests.get(
            url,
            headers=headers,
            timeout=10,
        )

        print(
            f"DEBUG: LinkedIn userinfo status: "
            f"{response.status_code}"
        )

        if response.status_code != 200:
            print(
                f"ERROR: LinkedIn userinfo response: "
                f"{response.text}"
            )
            return None

        data = response.json()

        print("DEBUG: LinkedIn userinfo received")

        member_id = data.get("sub")

        if not member_id:
            print("ERROR: LinkedIn userinfo did not contain 'sub'")
            return None

        person_urn = f"urn:li:person:{member_id}"

        _PERSON_URN_CACHE = person_urn

        print(f"DEBUG: LinkedIn Person URN: {person_urn}")

        return person_urn

    except requests.RequestException as e:
        print(f"ERROR contacting LinkedIn userinfo: {e}")
        return None

    except Exception as e:
        print(f"ERROR getting LinkedIn Person URN: {e}")
        return None


# ---------------------------------------------------------
# Upload LinkedIn image
# ---------------------------------------------------------


def _upload_linkedin_image(image_path, token, person_urn):
    """
    Upload an image to LinkedIn and return the LinkedIn asset URN.

    Returns:
        (asset_urn, None) on success
        (None, error_message) on failure
    """

    register_url = (
        "https://api.linkedin.com/v2/assets?action=registerUpload"
    )

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "X-Restli-Protocol-Version": "2.0.0",
    }

    registration = {
        "registerUploadRequest": {
            "recipes": [
                "urn:li:digitalmediaRecipe:feedshare-image"
            ],
            "owner": person_urn,
            "serviceRelationships": [
                {
                    "relationshipType": "OWNER",
                    "identifier": "urn:li:userGeneratedContent",
                }
            ],
        }
    }

    try:
        print("DEBUG: Registering LinkedIn image upload...")

        response = requests.post(
            register_url,
            headers=headers,
            json=registration,
            timeout=30,
        )

        print(
            "DEBUG: LinkedIn image registration status: "
            f"{response.status_code}"
        )

        if response.status_code not in range(200, 300):
            return (
                None,
                "LinkedIn image registration failed: "
                f"{response.text}",
            )

        response_data = response.json()

        if not isinstance(response_data, dict):
            return (
                None,
                "LinkedIn returned an invalid image upload response.",
            )

        value = response_data.get("value", {})

        asset = value.get("asset")

        upload_request = value.get(
            "uploadMechanism", {}
        ).get(
            "com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest",
            {},
        )

        upload_url = upload_request.get("uploadUrl")

        if not asset or not upload_url:
            return (
                None,
                "LinkedIn did not return an image upload URL.",
            )

        content_type = (
            mimetypes.guess_type(image_path.name)[0]
            or "application/octet-stream"
        )

        print(
            f"DEBUG: Uploading image with content type: "
            f"{content_type}"
        )

        with image_path.open("rb") as image_file:
            upload_response = requests.put(
                upload_url,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": content_type,
                },
                data=image_file,
                timeout=60,
            )

        print(
            "DEBUG: LinkedIn image upload status: "
            f"{upload_response.status_code}"
        )

        if upload_response.status_code not in range(200, 300):
            return (
                None,
                "LinkedIn image upload failed: "
                f"{upload_response.text}",
            )

        print(f"DEBUG: LinkedIn image asset: {asset}")

        return asset, None

    except (OSError, ValueError, requests.RequestException) as error:
        return None, f"LinkedIn image upload failed: {error}"


# ---------------------------------------------------------
# Publish LinkedIn post
# ---------------------------------------------------------


def post_linkedin(details):
    """
    Publish a text post, optionally with an image,
    to the authenticated LinkedIn profile.

    Returns the exact success string expected by
    linkedin_views.py when LinkedIn accepts the post.
    """

    # -----------------------------------------------------
    # Validate details
    # -----------------------------------------------------

    if not isinstance(details, dict):
        return "LinkedIn post details are invalid."

    # -----------------------------------------------------
    # Get post text
    # -----------------------------------------------------

    raw_text = (
        details.get("generated_text")
        or details.get("message")
        or details.get("text")
        or details.get("content")
        or details.get("prompt")
    )

    if not raw_text:
        print(
            "ERROR: No text found in details keys: "
            f"{list(details.keys())}"
        )

        return (
            "LinkedIn post text missing. "
            f"Received keys: {list(details.keys())}"
        )

    # Always convert to string so the request body is safe.
    text = str(raw_text).strip()

    if not text:
        return "LinkedIn post text is empty."

    # -----------------------------------------------------
    # Get latest LinkedIn token
    # -----------------------------------------------------

    token = get_linkedin_token()

    if not token:
        return (
            "LinkedIn token missing. "
            "Please connect LinkedIn again."
        )

    # -----------------------------------------------------
    # Get authenticated LinkedIn member
    # -----------------------------------------------------

    person_urn = get_person_urn(token)

    if not person_urn:
        return (
            "Could not determine your LinkedIn profile. "
            "Your LinkedIn access token may be expired. "
            "Please connect LinkedIn again."
        )

    # -----------------------------------------------------
    # Generate final post text
    # -----------------------------------------------------

    if details.get("generated_text"):
        # Use the text that the user already reviewed.
        text = str(details["generated_text"]).strip()
    else:
        text = str(raw_text).strip()

    if not text:
        return "LinkedIn post text is empty."

    # LinkedIn UGC posts have a 3000-character text limit.
    if len(text) > 3000:
        print(
            "DEBUG: Post text exceeds 3000 characters. "
            "Truncating."
        )

        text = text[:3000]

    # -----------------------------------------------------
    # Optional image upload
    # -----------------------------------------------------

    image_asset = None

    image_path_value = details.get("image_path")

    if image_path_value:
        image_path = Path(image_path_value)

        if not image_path.exists():
            return (
                "LinkedIn image file was not found: "
                f"{image_path}"
            )

        if not image_path.is_file():
            return (
                "LinkedIn image path is not a file: "
                f"{image_path}"
            )

        image_asset, upload_error = _upload_linkedin_image(
            image_path,
            token,
            person_urn,
        )

        if upload_error:
            print(f"ERROR: {upload_error}")
            return upload_error

    # -----------------------------------------------------
    # LinkedIn UGC Posts API
    # -----------------------------------------------------

    post_url = "https://api.linkedin.com/v2/ugcPosts"

    post_headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "X-Restli-Protocol-Version": "2.0.0",
    }

    share_content = {
        "shareCommentary": {
            "text": text
        },
        "shareMediaCategory": (
            "IMAGE" if image_asset else "NONE"
        ),
    }

    if image_asset:
        share_content["media"] = [
            {
                "status": "READY",
                "media": image_asset,
                "title": {
                    "text": "Post image"
                },
            }
        ]

    payload = {
        "author": person_urn,
        "lifecycleState": "PUBLISHED",
        "specificContent": {
            "com.linkedin.ugc.ShareContent": share_content
        },
        "visibility": {
            "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
        },
    }

    print("DEBUG: Publishing LinkedIn post...")
    print(f"DEBUG: Author: {person_urn}")
    print(
        "DEBUG: Image included: "
        f"{bool(image_asset)}"
    )

    try:
        response = requests.post(
            post_url,
            headers=post_headers,
            json=payload,
            timeout=30,
        )

        print(
            "DEBUG: LinkedIn post status: "
            f"{response.status_code}"
        )

        # -------------------------------------------------
        # SUCCESS
        # -------------------------------------------------
        #
        # IMPORTANT:
        # Do not restrict this to only 200/201.
        #
        # If LinkedIn returns ANY 2xx response, the request
        # was accepted successfully. This prevents the
        # frontend from showing "Could not publish the post"
        # when LinkedIn has actually accepted the post.
        # -------------------------------------------------

        if 200 <= response.status_code < 300:
            post_id = response.headers.get("X-RestLi-Id")

            if post_id:
                print(
                    f"DEBUG: LinkedIn post ID: {post_id}"
                )
            else:
                print(
                    "DEBUG: LinkedIn did not return "
                    "X-RestLi-Id."
                )

            print(
                "DEBUG: LinkedIn post published "
                "successfully."
            )

            # This exact string is intentionally preserved
            # because linkedin_views.py checks for it.
            return "LinkedIn post published successfully 🚀"

        # -------------------------------------------------
        # Expired token / authentication failure
        # -------------------------------------------------

        if response.status_code == 401:

            try:
                error_data = response.json()
            except Exception:
                error_data = {}

            error_code = error_data.get("code")

            if error_code == "EXPIRED_ACCESS_TOKEN":

                # Clear cached URN because we will need to
                # authenticate again.
                global _PERSON_URN_CACHE
                _PERSON_URN_CACHE = None

                return (
                    "LinkedIn access token has expired. "
                    "Please connect LinkedIn again to "
                    "generate a new access token."
                )

            return (
                "LinkedIn authentication failed. "
                f"Response: {response.text}"
            )

        # -------------------------------------------------
        # Other LinkedIn error
        # -------------------------------------------------

        print(
            "ERROR: LinkedIn publish failed. "
            f"Status={response.status_code}, "
            f"Response={response.text}"
        )

        return (
            f"LinkedIn ERROR ({response.status_code}): "
            f"{response.text}"
        )

    except requests.RequestException as e:

        print(
            f"LinkedIn request exception: {e}"
        )

        raise LinkedInPublishOutcomeUnknown(
            "LinkedIn did not return a response for the publish request."
        ) from e