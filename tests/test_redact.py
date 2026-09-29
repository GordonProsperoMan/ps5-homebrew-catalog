import unittest

from catalog.redact import summarize

LOG = """\
⛅️ wrangler 4.143.0
Getting User settings...
👋 You are logged in with an API Token, associated with the email dev@example.com.
┌──────────────┬──────────────────────────────────┐
│ Account Name │ Account ID                       │
│ Secret Corp  │ 0123456789abcdef0123456789abcdef │
✘ [ERROR] A request to the Cloudflare API (/accounts/0123456789abcdef0123456789abcdef/pages/projects/x) failed.
  Project not found. The specified project name does not match any of your existing projects. [code: 8000007]
✘ [ERROR] Authentication error for "Secret Corp" at https://dash.cloudflare.com/0123456789abcdef [code: 10000]
"""


class RedactTests(unittest.TestCase):
    def test_keeps_error_codes_and_hides_account_details(self):
        output = "\n".join(summarize(LOG))
        self.assertIn("[code: 8000007]", output)
        self.assertIn("[code: 10000]", output)
        self.assertIn("Project not found", output)
        for secret in ("dev@example.com", "0123456789abcdef", "Secret Corp", "dash.cloudflare.com"):
            self.assertNotIn(secret, output)

    def test_ignores_non_error_lines(self):
        self.assertEqual(summarize("Uploaded 12 files\nDeployment complete!"), [])


if __name__ == "__main__":
    unittest.main()
