import os
import json
import secrets
from pathlib import Path
from urllib.parse import urlencode, urlparse

import requests

from django.shortcuts import redirect

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

DEMO_USERNAME = "linkedin"
DEMO_PASSWORD = "LinkedIn#2026!"


@api_view(["POST"])
@permission_classes([AllowAny])
def login(request):
    username = str(request.data.get("username", ""))
    password = str(request.data.get("password", ""))

    if not username or not password:
        return Response(
            {"detail": "Username and password are required"},
            status=status.HTTP_400_BAD_REQUEST
        )

    valid_username = secrets.compare_digest(username, DEMO_USERNAME)
    valid_password = secrets.compare_digest(password, DEMO_PASSWORD)
    if not (valid_username and valid_password):
        return Response(
            {"detail": "Invalid username or password"},
            status=status.HTTP_401_UNAUTHORIZED
        )

    request.session.cycle_key()
    request.session["demo_authenticated"] = True
    request.session["demo_username"] = DEMO_USERNAME
    request.session.set_expiry(60 * 60 * 8)
    return Response({"user": {"username": DEMO_USERNAME}})


@api_view(["GET"])
@permission_classes([AllowAny])
def session_status(request):
    authenticated = bool(request.session.get("demo_authenticated"))
    user = (
        {"username": request.session.get("demo_username", DEMO_USERNAME)}
        if authenticated
        else None
    )
    return Response({"authenticated": authenticated, "user": user})


@api_view(["POST"])
@permission_classes([AllowAny])
def logout(request):
    request.session.flush()
    return Response({"authenticated": False})


# ============================================================
# LINKEDIN CONFIGURATION
# ============================================================

LINKEDIN_CLIENT_ID = os.getenv(
    "LINKEDIN_CLIENT_ID"
)

LINKEDIN_CLIENT_SECRET = os.getenv(
    "LINKEDIN_CLIENT_SECRET"
)

LINKEDIN_REDIRECT_URI = os.getenv(
    "LINKEDIN_REDIRECT_URI",
    "http://127.0.0.1:8000/link/linkedin/callback/"
)

FRONTEND_URL = os.getenv(
    "FRONTEND_URL",
    "http://localhost:3000"
)

# automation/linkedin_tokens.json
LINKEDIN_TOKEN_FILE = (
    Path(__file__).resolve().parent / "linkedin_tokens.json"
)

# Temporary OAuth state file
LINKEDIN_STATE_FILE = (
    Path(__file__).resolve().parent / "linkedin_oauth_state.json"
)


# ============================================================
# LINKEDIN LOGIN
# ============================================================

@api_view(['GET'])
@permission_classes([AllowAny])
def linkedin_login(request):
    """
    Start LinkedIn OAuth authorization.
    """

    if not request.session.get("demo_authenticated"):
        return Response(
            {"detail": "Authentication required"},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    if not LINKEDIN_CLIENT_ID:
        return Response(
            {
                "error": "LINKEDIN_CLIENT_ID is not configured"
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

    if not LINKEDIN_CLIENT_SECRET:
        return Response(
            {
                "error": "LINKEDIN_CLIENT_SECRET is not configured"
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

    # --------------------------------------------------------
    # Generate state
    # --------------------------------------------------------

    state = secrets.token_urlsafe(32)
    frontend_origin = request.GET.get("frontend_origin", FRONTEND_URL).rstrip("/")
    parsed_origin = urlparse(frontend_origin)
    if (
        parsed_origin.scheme not in ("http", "https")
        or parsed_origin.hostname not in ("localhost", "127.0.0.1")
        or parsed_origin.port not in (3000, 3001, 5173)
    ):
        frontend_origin = FRONTEND_URL

    # Save state locally instead of relying on browser session.
    try:
        with open(
            LINKEDIN_STATE_FILE,
            "w",
            encoding="utf-8"
        ) as f:
            json.dump(
                {
                    "state": state,
                    "frontend_origin": frontend_origin,
                },
                f
            )

        print("OAuth state generated and saved.")

    except Exception as e:

        print(
            "ERROR saving OAuth state:",
            e
        )

        return Response(
            {
                "error": "Could not initialize OAuth"
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

    # --------------------------------------------------------
    # Build LinkedIn authorization URL
    # --------------------------------------------------------

    params = {
        "response_type": "code",
        "client_id": LINKEDIN_CLIENT_ID,
        "redirect_uri": LINKEDIN_REDIRECT_URI,
        "state": state,
        "scope": "openid profile w_member_social",
    }

    authorization_url = (
        "https://www.linkedin.com/oauth/v2/authorization?"
        + urlencode(params)
    )

    print("Redirecting to LinkedIn...")

    return redirect(authorization_url)


# ============================================================
# LINKEDIN CALLBACK
# ============================================================

@api_view(['GET'])
@permission_classes([AllowAny])
def linkedin_callback(request):
    """
    Handle LinkedIn OAuth callback.
    """

    print("\n========================================")
    print("LinkedIn OAuth callback received")
    print("========================================")

    # ========================================================
    # 1. Check LinkedIn errors
    # ========================================================

    error = request.GET.get("error")

    if error:

        description = request.GET.get(
            "error_description",
            "LinkedIn authorization failed"
        )

        print("LinkedIn OAuth error:", error)
        print("Description:", description)

        return redirect(
            f"{FRONTEND_URL}/?linkedin=error"
        )

    # ========================================================
    # 2. Get returned state
    # ========================================================

    returned_state = request.GET.get("state")

    if not returned_state:

        print("ERROR: LinkedIn did not return state.")

        return Response(
            {
                "error": "OAuth state missing"
            },
            status=status.HTTP_400_BAD_REQUEST
        )

    print("OAuth state received from LinkedIn.")

    # ========================================================
    # 3. Read saved state
    # ========================================================

    saved_state = None
    saved_frontend_origin = FRONTEND_URL

    try:

        if LINKEDIN_STATE_FILE.exists():

            with open(
                LINKEDIN_STATE_FILE,
                "r",
                encoding="utf-8"
            ) as f:

                state_data = json.load(f)

            saved_state = state_data.get("state")
            saved_frontend_origin = state_data.get(
                "frontend_origin",
                FRONTEND_URL,
            )

    except Exception as e:

        print(
            "ERROR reading OAuth state:",
            e
        )

    if not saved_state:

        print(
            "ERROR: Saved OAuth state not found."
        )

        return Response(
            {
                "error":
                    "OAuth state not found. "
                    "Please start LinkedIn login again."
            },
            status=status.HTTP_400_BAD_REQUEST
        )

    # ========================================================
    # 4. Validate state
    # ========================================================

    if not secrets.compare_digest(
        returned_state,
        saved_state
    ):

        print(
            "ERROR: OAuth state mismatch."
        )

        return Response(
            {
                "error": "Invalid OAuth state"
            },
            status=status.HTTP_401_UNAUTHORIZED
        )

    print("OAuth state validated successfully.")

    # State is one-time use.
    try:
        LINKEDIN_STATE_FILE.unlink()
    except Exception:
        pass

    # ========================================================
    # 5. Get authorization code
    # ========================================================

    code = request.GET.get("code")

    if not code:

        print(
            "ERROR: Authorization code missing."
        )

        return Response(
            {
                "error":
                    "LinkedIn authorization code missing"
            },
            status=status.HTTP_400_BAD_REQUEST
        )

    print(
        "Authorization code received."
    )

    # ========================================================
    # 6. Exchange code for access token
    # ========================================================

    token_url = (
        "https://www.linkedin.com/oauth/v2/accessToken"
    )

    token_data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": LINKEDIN_REDIRECT_URI,
        "client_id": LINKEDIN_CLIENT_ID,
        "client_secret": LINKEDIN_CLIENT_SECRET,
    }

    try:

        token_response = requests.post(
            token_url,
            data=token_data,
            headers={
                "Content-Type":
                    "application/x-www-form-urlencoded"
            },
            timeout=30
        )

    except requests.RequestException as e:

        print(
            "ERROR contacting LinkedIn:",
            e
        )

        return Response(
            {
                "error":
                    "Could not connect to LinkedIn"
            },
            status=status.HTTP_502_BAD_GATEWAY
        )

    print(
        "LinkedIn token response status:",
        token_response.status_code
    )

    # ========================================================
    # 7. Check token response
    # ========================================================

    if token_response.status_code != 200:

        print(
            "LinkedIn token exchange failed."
        )

        print(
            token_response.text
        )

        return Response(
            {
                "error":
                    "Failed to obtain LinkedIn access token",
                "details":
                    token_response.text
            },
            status=status.HTTP_400_BAD_REQUEST
        )

    try:

        tokens = token_response.json()

    except ValueError:

        return Response(
            {
                "error":
                    "LinkedIn returned invalid JSON"
            },
            status=status.HTTP_502_BAD_GATEWAY
        )

    # ========================================================
    # 8. Verify access token
    # ========================================================

    access_token = tokens.get(
        "access_token"
    )

    if not access_token:

        print(
            "ERROR: LinkedIn did not return access token."
        )

        return Response(
            {
                "error":
                    "LinkedIn did not return an access token"
            },
            status=status.HTTP_400_BAD_REQUEST
        )

    print(
        "LinkedIn access token received successfully."
    )

    # ========================================================
    # 9. Save token
    # ========================================================

    try:

        LINKEDIN_TOKEN_FILE.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        with open(
            LINKEDIN_TOKEN_FILE,
            "w",
            encoding="utf-8"
        ) as f:

            json.dump(
                tokens,
                f,
                indent=2
            )

        print(
            "LinkedIn token saved successfully:"
        )

        print(
            LINKEDIN_TOKEN_FILE
        )

    except Exception as e:

        print(
            "ERROR saving LinkedIn token:",
            e
        )

        return Response(
            {
                "error":
                    "Failed to save LinkedIn token"
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

    # ========================================================
    # 10. Success
    # ========================================================

    print(
        "========================================"
    )

    print(
        "LinkedIn connected successfully!"
    )

    print(
        "========================================"
    )

    return redirect(
        f"{saved_frontend_origin}/?linkedin=connected"
    )