from unittest.mock import patch

from django.test import TestCase


class DemoSessionAuthTest(TestCase):
    def test_login_session_and_logout(self):
        login_response = self.client.post(
            "/api/auth/login/",
            {"username": "linkedin", "password": "LinkedIn#2026!"},
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
            {"username": "linkedin", "password": "LinkedIn#2026!"},
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

    def test_generic_task_routes_are_removed(self):
        self.assertEqual(self.client.post("/preview/").status_code, 404)
        self.assertEqual(self.client.post("/execute/").status_code, 404)
