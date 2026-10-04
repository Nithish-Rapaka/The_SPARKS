from unittest.mock import Mock, patch
import uuid
from pathlib import Path
from tempfile import TemporaryDirectory

from django.test import TestCase


class DemoSessionAuthTest(TestCase):
    def test_login_session_and_logout(self):
        login_response = self.client.post(
            "/api/auth/login/",
            {"username": "admin", "password": "admin"},
            content_type="application/json",
        )
        self.assertEqual(login_response.status_code, 200)

        session_response = self.client.get("/api/auth/session/")
        self.assertTrue(session_response.data["authenticated"])

        logout_response = self.client.post("/api/auth/logout/")
        self.assertEqual(logout_response.status_code, 200)
        self.assertFalse(
            self.client.get("/api/auth/session/").data["authenticated"]
        )


class LinkedInOnlyAPITest(TestCase):
    def setUp(self):
        self.client.post(
            "/api/auth/login/",
            {"username": "admin", "password": "admin"},
            content_type="application/json",
        )

    def test_linkedin_preview_requires_session(self):
        self.client.post("/api/auth/logout/")
        response = self.client.post(
            "/api/linkedin/preview/",
            {"prompt": "A post about software testing"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 401)

    @patch("automation.linkedin_views.generate_linkedin_post")
    def test_preview_generates_post_text(self, generate_post):
        generate_post.return_value = "A polished LinkedIn post. #Testing"
        response = self.client.post(
            "/api/linkedin/preview/",
            {"prompt": "A post about software testing"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["text"], generate_post.return_value)

    @patch("automation.linkedin_views.get_linkedin_token", return_value="test-token")
    @patch("automation.linkedin_views.post_linkedin")
    def test_publish_uses_reviewed_text(self, post_linkedin, _get_token):
        post_linkedin.return_value = "LinkedIn post published successfully 🚀"
        response = self.client.post(
            "/api/linkedin/publish/",
            {"text": "Reviewed LinkedIn post"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        post_linkedin.assert_called_once_with(
            {"generated_text": "Reviewed LinkedIn post"}
        )

    @patch("automation.linkedin_views.get_linkedin_token", return_value="test-token")
    @patch("automation.linkedin_views.post_linkedin")
    def test_publish_forwards_uploaded_image(self, post_linkedin, _get_token):
        from django.conf import settings

        image_path = (
            settings.MEDIA_ROOT
            / "uploaded_images"
            / f"linkedin_test_{uuid.uuid4().hex}.png"
        )
        image_path.parent.mkdir(parents=True, exist_ok=True)
        image_path.write_bytes(b"image data")
        self.addCleanup(image_path.unlink, missing_ok=True)

        post_linkedin.return_value = "LinkedIn post published successfully 🚀"
        response = self.client.post(
            "/api/linkedin/publish/",
            {
                "text": "Reviewed LinkedIn post",
                "image_url": f"/media/uploaded_images/{image_path.name}",
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        post_linkedin.assert_called_once_with(
            {
                "generated_text": "Reviewed LinkedIn post",
                "image_path": str(image_path),
            }
        )

    @patch("automation.linkedin_views.get_linkedin_token", return_value="test-token")
    def test_publish_rejects_image_not_uploaded_by_app(self, _get_token):
        response = self.client.post(
            "/api/linkedin/publish/",
            {
                "text": "Reviewed LinkedIn post",
                "image_url": "https://example.com/image.png",
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_generic_task_routes_are_removed(self):
        self.assertEqual(self.client.post("/preview/").status_code, 404)
        self.assertEqual(self.client.post("/execute/").status_code, 404)


class LinkedInImagePublishingTest(TestCase):
    @patch("automation.services.linkedin_service.get_person_urn", return_value="urn:li:person:123")
    @patch("automation.services.linkedin_service.get_linkedin_token", return_value="test-token")
    @patch("automation.services.linkedin_service.requests.put")
    @patch("automation.services.linkedin_service.requests.post")
    def test_publish_uploads_image_and_includes_it_with_reviewed_text(
        self,
        post_request,
        put_request,
        _get_token,
        _get_person_urn,
    ):
        from automation.services.linkedin_service import post_linkedin

        registration_response = Mock(status_code=201)
        registration_response.json.return_value = {
            "value": {
                "asset": "urn:li:digitalmediaAsset:asset123",
                "uploadMechanism": {
                    "com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest": {
                        "uploadUrl": "https://upload.example/image",
                    }
                },
            }
        }
        published_response = Mock(status_code=201, headers={})
        post_request.side_effect = [registration_response, published_response]
        put_request.return_value = Mock(status_code=201)

        with TemporaryDirectory() as temp_dir:
            image_path = Path(temp_dir) / "upload.png"
            image_path.write_bytes(b"image bytes")
            result = post_linkedin(
                {
                    "generated_text": "Reviewed copy",
                    "image_path": str(image_path),
                }
            )

        self.assertEqual(result, "LinkedIn post published successfully 🚀")
        put_request.assert_called_once()
        publish_payload = post_request.call_args_list[1].kwargs["json"]
        share_content = publish_payload["specificContent"]["com.linkedin.ugc.ShareContent"]
        self.assertEqual(share_content["shareCommentary"]["text"], "Reviewed copy")
        self.assertEqual(share_content["shareMediaCategory"], "IMAGE")
        self.assertEqual(
            share_content["media"][0]["media"],
            "urn:li:digitalmediaAsset:asset123",
        )
