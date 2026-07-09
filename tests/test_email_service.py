import unittest
from unittest.mock import Mock
from unittest.mock import patch

from services.email_service import format_email_body
from services.email_service import format_email_subject
from services.email_service import send_email_digest


class EmailServiceTest(unittest.TestCase):
    def test_email_formatting_groups_jobs_by_company(self):
        jobs = [
            self.build_job("Qualcomm", "ASIC Design Engineer", "https://qcom.test/1"),
            self.build_job("Apple", "Physical Design Engineer", "https://apple.test/2"),
        ]

        body = format_email_body(jobs)

        self.assertEqual(format_email_subject(jobs), "Career Radar — 2 new jobs")
        self.assertIn("Apple\n-----", body)
        self.assertIn("Qualcomm\n--------", body)
        self.assertIn("Title: Physical Design Engineer", body)
        self.assertIn("Location: Israel", body)
        self.assertIn("Matched keyword: ASIC", body)
        self.assertIn("URL: https://qcom.test/1", body)

    def test_email_disabled_mode_does_not_send(self):
        sent = send_email_digest(
            [self.build_job("Apple", "Physical Design Engineer", "https://apple.test/1")],
            env={"CAREER_RADAR_EMAIL_ENABLED": "false"},
        )

        self.assertFalse(sent)

    def test_email_enabled_without_new_jobs_does_not_send(self):
        sent = send_email_digest(
            [],
            env={"CAREER_RADAR_EMAIL_ENABLED": "true"},
        )

        self.assertFalse(sent)

    def test_email_enabled_sends_when_configured(self):
        smtp = Mock()
        smtp_context = Mock()
        smtp_context.__enter__ = Mock(return_value=smtp)
        smtp_context.__exit__ = Mock(return_value=False)

        env = {
            "CAREER_RADAR_EMAIL_ENABLED": "true",
            "CAREER_RADAR_SMTP_HOST": "smtp.example.com",
            "CAREER_RADAR_SMTP_PORT": "2525",
            "CAREER_RADAR_SMTP_USER": "user",
            "CAREER_RADAR_SMTP_PASSWORD": "password",
            "CAREER_RADAR_EMAIL_FROM": "from@example.com",
            "CAREER_RADAR_EMAIL_TO": "to@example.com",
        }

        with patch("services.email_service.smtplib.SMTP", return_value=smtp_context):
            sent = send_email_digest(
                [self.build_job("Apple", "Physical Design Engineer", "https://apple.test/1")],
                env=env,
            )

        self.assertTrue(sent)
        smtp.starttls.assert_called_once_with()
        smtp.login.assert_called_once_with("user", "password")
        smtp.send_message.assert_called_once()

    def build_job(self, company, title, url):
        return {
            "company": company,
            "title": title,
            "url": url,
            "matched_keyword": "ASIC",
            "matched_location": "Israel",
        }


if __name__ == "__main__":
    unittest.main()
