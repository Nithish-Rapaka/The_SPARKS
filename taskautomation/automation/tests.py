from unittest.mock import Mock, patch
import uuid
from pathlib import Path
from tempfile import TemporaryDirectory
from bson import ObjectId
import requests

from django.test import TestCase
from pymongo.errors import PyMongoError
from automation.services.linkedin_service import LinkedInPublishOutcomeUnknown


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


class MongoDBHistoryConfigurationTest(TestCase):
    @patch("automation.services.linkedin_history.MongoClient")
    def test_uses_configured_database_name(self, mongo_client):
        from automation.services.linkedin_history import _posts_collection

        with patch.dict(
            "os.environ",
            {
                "MONGODB_URI": "mongodb://example.invalid/",
                "MONGODB_DATABASE": "configured_database",
            },
        ):
            client, collection = _posts_collection()

        mongo_client.assert_called_once_with(
            "mongodb://example.invalid/",
            serverSelectionTimeoutMS=10000,
            tz_aware=True,
        )
        client.__getitem__.assert_called_once_with("configured_database")
        client.__getitem__.return_value.__getitem__.assert_called_once_with(
            "linkedin_posts"
        )
        self.assertEqual(
            collection,
            client.__getitem__.return_value.__getitem__.return_value,
        )

    @patch("automation.services.linkedin_history._posts_collection")
    def test_delete_selected_posts_uses_object_ids(self, get_collection):
        from automation.services.linkedin_history import delete_linkedin_posts

        client = Mock()
        collection = Mock()
        collection.delete_many.return_value.deleted_count = 2
        get_collection.return_value = (client, collection)
        post_ids = [str(ObjectId()), str(ObjectId())]

        deleted_count = delete_linkedin_posts(post_ids)

        self.assertEqual(deleted_count, 2)
        collection.delete_many.assert_called_once_with(
            {"_id": {"$in": [ObjectId(post_id) for post_id in post_ids]}}
        )
        client.close.assert_called_once_with()

    @patch("automation.services.linkedin_history._posts_collection")
    def test_delete_all_posts_uses_empty_selector(self, get_collection):
        from automation.services.linkedin_history import delete_linkedin_posts

        client = Mock()
        collection = Mock()
        collection.delete_many.return_value.deleted_count = 5
        get_collection.return_value = (client, collection)

        deleted_count = delete_linkedin_posts()

        self.assertEqual(deleted_count, 5)
        collection.delete_many.assert_called_once_with({})
        client.close.assert_called_once_with()


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
    @patch("automation.linkedin_views.save_linkedin_post")
    def test_publish_uses_reviewed_text(
        self, save_post, post_linkedin, _get_token
    ):
        post_linkedin.return_value = "LinkedIn post published successfully 🚀"
        save_post.return_value = {"id": "post-1"}
        response = self.client.post(
            "/api/linkedin/publish/",
            {
                "prompt": "A post about software testing",
                "text": "Reviewed LinkedIn post",
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        post_linkedin.assert_called_once_with(
            {"generated_text": "Reviewed LinkedIn post"}
        )
        save_post.assert_called_once_with(
            prompt="A post about software testing",
            text="Reviewed LinkedIn post",
            image_url=None,
        )

    @patch("automation.linkedin_views.get_linkedin_token", return_value="test-token")
    @patch("automation.linkedin_views.post_linkedin")
    @patch(
        "automation.linkedin_views.save_linkedin_post",
        side_effect=PyMongoError("TLS handshake failed"),
    )
    def test_mongodb_failure_does_not_report_published_post_as_failed(
        self, _save_post, post_linkedin, _get_token
    ):
        post_linkedin.return_value = "LinkedIn post published successfully 🚀"

        response = self.client.post(
            "/api/linkedin/publish/",
            {"text": "Reviewed LinkedIn post"},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["published"])
        self.assertFalse(response.json()["history_saved"])
        self.assertEqual(
            response.json()["result"],
            "LinkedIn post published successfully 🚀",
        )
        self.assertIn("history_warning", response.json())

    @patch("automation.linkedin_views.get_linkedin_token", return_value="test-token")
    @patch(
        "automation.linkedin_views.post_linkedin",
        side_effect=LinkedInPublishOutcomeUnknown(),
    )
    def test_unconfirmed_linkedin_response_is_not_reported_as_publish_failure(
        self, _post_linkedin, _get_token
    ):
        response = self.client.post(
            "/api/linkedin/publish/",
            {"text": "Reviewed LinkedIn post"},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json()["published"])
        self.assertIn("Check your LinkedIn profile", response.json()["result"])

    @patch(
        "automation.linkedin_views.get_linkedin_posts",
        return_value=[{"id": "post-1", "text": "Saved post"}],
    )
    def test_post_history_returns_saved_posts(self, get_posts):
        response = self.client.get("/api/linkedin/posts/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["posts"], get_posts.return_value)

    def test_post_history_requires_session(self):
        self.client.post("/api/auth/logout/")
        response = self.client.get("/api/linkedin/posts/")
        self.assertEqual(response.status_code, 401)

    @patch("automation.linkedin_views.delete_linkedin_posts", return_value=2)
    def test_delete_selected_post_history(self, delete_posts):
        post_ids = [str(ObjectId()), str(ObjectId())]
        response = self.client.delete(
            "/api/linkedin/posts/",
            {"ids": post_ids},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["deleted_count"], 2)
        delete_posts.assert_called_once_with(post_ids)

    @patch("automation.linkedin_views.delete_linkedin_posts", return_value=5)
    def test_clear_all_post_history(self, delete_posts):
        response = self.client.delete(
            "/api/linkedin/posts/",
            {"all": True},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["deleted_count"], 5)
        delete_posts.assert_called_once_with(None)

    def test_delete_rejects_invalid_post_ids(self):
        response = self.client.delete(
            "/api/linkedin/posts/",
            {"ids": ["not-an-object-id"]},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_delete_rejects_non_object_payload(self):
        response = self.client.delete(
            "/api/linkedin/posts/",
            ["not", "an", "object"],
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_delete_requires_exactly_one_selection_mode(self):
        response = self.client.delete(
            "/api/linkedin/posts/",
            {},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_delete_post_history_requires_session(self):
        self.client.post("/api/auth/logout/")
        response = self.client.delete(
            "/api/linkedin/posts/",
            {"all": True},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 401)

    @patch(
        "automation.linkedin_views.get_linkedin_posts",
        side_effect=PyMongoError("TLS handshake failed"),
    )
    def test_post_history_error_explains_mongodb_network_checks(
        self, _get_posts
    ):
        response = self.client.get("/api/linkedin/posts/")
        self.assertEqual(response.status_code, 503)
        self.assertIn("MONGODB_URI", response.json()["detail"])
        self.assertIn("Django terminal", response.json()["detail"])

    @patch("automation.linkedin_views.get_linkedin_token", return_value="test-token")
    @patch("automation.linkedin_views.post_linkedin")
    @patch("automation.linkedin_views.save_linkedin_post")
    def test_publish_forwards_uploaded_image(
        self, _save_post, post_linkedin, _get_token
    ):
        _save_post.return_value = {"id": "post-1"}
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


class LinkedInPublishOutcomeTest(TestCase):
    @patch(
        "automation.services.linkedin_service.requests.post",
        side_effect=requests.exceptions.ReadTimeout("response timed out"),
    )
    @patch(
        "automation.services.linkedin_service.get_person_urn",
        return_value="urn:li:person:123",
    )
    @patch(
        "automation.services.linkedin_service.get_linkedin_token",
        return_value="test-token",
    )
    def test_publish_timeout_is_reported_as_unknown(
        self, _get_token, _get_person_urn, _post_request
    ):
        from automation.services.linkedin_service import (
            LinkedInPublishOutcomeUnknown,
            post_linkedin,
        )

        with self.assertRaises(LinkedInPublishOutcomeUnknown):
            post_linkedin({"generated_text": "Reviewed copy"})
