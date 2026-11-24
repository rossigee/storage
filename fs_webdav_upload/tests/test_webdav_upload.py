from odoo.tests.common import HttpCase, tagged


@tagged("post_install", "-at_install")
class TestWebDAVUpload(HttpCase):
    def setUp(self):
        super().setUp()
        self.api_user = self.env["res.users"].create(
            {
                "name": "WebDAV Upload User",
                "login": "webdav_upload_user",
                "email": "webdav_upload@example.com",
            }
        )
        # res.users.apikeys stores only the hash; _generate returns the raw key.
        # The upload route validates with scope="dav".
        self.api_key = (
            self.env["res.users.apikeys"]
            .with_user(self.api_user)
            ._generate("dav", "WebDAV Upload Key")
        )

    def _url(self, path):
        return f"{self.base_url()}/upload/dav/{path}"

    def _put(self, path, body=b"statement", headers=None):
        hdrs = {"Content-Type": "application/octet-stream"}
        hdrs.update(headers or {})
        # url_open sends GET/POST only; the route is PUT/PROPFIND/MKCOL/OPTIONS,
        # so drive the session directly.
        return self.opener.put(self._url(path), data=body, headers=hdrs, timeout=12)

    def test_options_needs_no_auth(self):
        """Clients must be able to probe capabilities before holding a key."""
        response = self.opener.options(self._url("anything"), timeout=12)
        self.assertEqual(response.status_code, 200)
        self.assertIn("PROPFIND", response.headers.get("Allow", ""))

    def test_put_without_auth_is_rejected(self):
        response = self._put("statement.csv")
        self.assertEqual(response.status_code, 401)

    def test_put_with_bad_auth_is_rejected(self):
        response = self._put(
            "statement.csv", headers={"Authorization": "Bearer not-a-real-key"}
        )
        self.assertEqual(response.status_code, 401)

    def test_put_with_malformed_auth_is_rejected(self):
        response = self._put("statement.csv", headers={"Authorization": "Token abc"})
        self.assertEqual(response.status_code, 401)

    def test_put_with_valid_auth_creates_attachment(self):
        response = self._put(
            "statement.csv",
            body=b"date,amount\n2026-01-01,100.00\n",
            headers={"Authorization": f"Bearer {self.api_key}"},
        )
        self.assertEqual(response.status_code, 201)
        self.assertIn("/attachment/", response.headers.get("Location", ""))

        attachment = self.env["ir.attachment"].search(
            [("name", "=", "statement.csv")], limit=1
        )
        self.assertTrue(attachment.exists())
        self.assertFalse(attachment.public)

    def test_empty_body_is_rejected(self):
        response = self._put(
            "empty.csv", body=b"", headers={"Authorization": f"Bearer {self.api_key}"}
        )
        self.assertEqual(response.status_code, 400)

    def test_traversal_segment_is_rejected(self):
        response = self._put(
            "../escape.csv", headers={"Authorization": f"Bearer {self.api_key}"}
        )
        self.assertIn(response.status_code, (400, 404))

    def test_deactivated_user_key_is_rejected(self):
        self.api_user.active = False
        response = self._put(
            "statement.csv", headers={"Authorization": f"Bearer {self.api_key}"}
        )
        self.assertEqual(response.status_code, 401)

    def _make_dms_inbox(self):
        """Create a storage + Inbox directory; return the directory.

        Returns None (and skips) when dms is not installed in the test env.
        """
        if "dms.directory" not in self.env:
            self.skipTest("dms module not installed")
        storage = self.env["dms.storage"].create(
            {"name": "DAV upload test storage", "save_type": "database"}
        )
        return self.env["dms.directory"].create(
            {"name": "Inbox", "is_root_directory": True, "storage_id": storage.id}
        )

    def test_put_with_dms_inbox_configured_creates_dms_file(self):
        directory = self._make_dms_inbox()
        self.env["ir.config_parameter"].sudo().set_param(
            "fs_webdav_upload.dms_directory_id", str(directory.id)
        )
        self.addCleanup(
            self.env["ir.config_parameter"]
            .sudo()
            .set_param,
            "fs_webdav_upload.dms_directory_id",
            False,
        )
        response = self._put(
            "statement-dms.csv",
            body=b"date,amount\n2026-01-01,100.00\n",
            headers={"Authorization": f"Bearer {self.api_key}"},
        )
        self.assertEqual(response.status_code, 201)
        self.assertIn("model=dms.file", response.headers.get("Location", ""))
        dms_file = self.env["dms.file"].search(
            [("name", "=", "statement-dms.csv")], limit=1
        )
        self.assertTrue(dms_file.exists())
        self.assertEqual(dms_file.directory_id, directory)

    def test_put_with_dms_inbox_unconfigured_uses_attachments(self):
        self.env["ir.config_parameter"].sudo().set_param(
            "fs_webdav_upload.dms_directory_id", False
        )
        response = self._put(
            "statement-plain.csv",
            body=b"date,amount\n2026-01-01,100.00\n",
            headers={"Authorization": f"Bearer {self.api_key}"},
        )
        self.assertEqual(response.status_code, 201)
        self.assertIn("/attachment/", response.headers.get("Location", ""))
