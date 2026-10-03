import os
import json
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

        print(f"DEBUG: LinkedIn userinfo status: {response.status_code}")

        if response.status_code != 200:
            print(f"ERROR: LinkedIn userinfo response: {response.text}")
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
# Publish LinkedIn post
# ---------------------------------------------------------

def post_linkedin(details):
    """
    Publish a text post to the authenticated LinkedIn member's profile.
    """

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
            f"ERROR: No text found in details keys: "
            f"{list(details.keys())}"
        )

        return (
            "LinkedIn post text missing. "
            f"Received keys: {list(details.keys())}"
        )

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
        # Use the text that the user already reviewed
        text = details["generated_text"]

    else:
        text = raw_text

    # LinkedIn UGC posts have a 3000-character text limit.
    if len(text) > 3000:
        text = text[:3000]

    # -----------------------------------------------------
    # LinkedIn UGC Posts API
    # -----------------------------------------------------

    post_url = "https://api.linkedin.com/v2/ugcPosts"

    post_headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "X-Restli-Protocol-Version": "2.0.0",
    }

    payload = {
        "author": person_urn,
        "lifecycleState": "PUBLISHED",
        "specificContent": {
            "com.linkedin.ugc.ShareContent": {
                "shareCommentary": {
                    "text": text
                },
                "shareMediaCategory": "NONE",
            }
        },
        "visibility": {
            "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
        },
    }

    print("DEBUG: Publishing LinkedIn post...")
    print(f"DEBUG: Author: {person_urn}")

    try:

        response = requests.post(
            post_url,
            headers=post_headers,
            json=payload,
            timeout=30,
        )

        print(
            f"DEBUG: LinkedIn post status: "
            f"{response.status_code}"
        )

        # -------------------------------------------------
        # Success
        # -------------------------------------------------

        if response.status_code in (200, 201):

            post_id = response.headers.get("X-RestLi-Id")

            if post_id:
                print(f"DEBUG: LinkedIn post ID: {post_id}")

            return "LinkedIn post published successfully 🚀"

        # -------------------------------------------------
        # Expired token
        # -------------------------------------------------

        if response.status_code == 401:

            try:
                error_data = response.json()
            except Exception:
                error_data = {}

            error_code = error_data.get("code")

            if error_code == "EXPIRED_ACCESS_TOKEN":

                # Clear cached URN because we'll need to
                # authenticate again.
                global _PERSON_URN_CACHE
                _PERSON_URN_CACHE = None

                return (
                    "LinkedIn access token has expired. "
                    "Please connect LinkedIn again to generate "
                    "a new access token."
                )

            return (
                "LinkedIn authentication failed. "
                f"Response: {response.text}"
            )

        # -------------------------------------------------
        # Other LinkedIn error
        # -------------------------------------------------

        return f"LinkedIn ERROR: {response.text}"

    except requests.RequestException as e:

        print(f"LinkedIn request exception: {e}")

        return f"LinkedIn connection error: {e}"