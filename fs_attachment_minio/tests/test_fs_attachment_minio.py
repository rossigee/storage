# Copyright 2025 Ross Golder
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from .common import TestFSAttachmentMinioCommon


class TestFSAttachmentMinio(TestFSAttachmentMinioCommon):
    def test_get_x_sendfile_path_minio_unsigned(self):
        """Test the X-Accel-Redirect path generation for unsigned URLs."""
        url = self.fake_attachment_minio._get_x_sendfile_path()
        self.assertEqual(
            url,
            "/fs_x_sendfile/http/localhost:9000/test-bucket/dir/sub/fake_minio_file.txt",
            f"The X-Accel-Redirect path should match the expected format. ({url})",
        )

    def test_get_x_sendfile_path_minio_signed(self):
        """Test the X-Accel-Redirect path generation for signed URLs."""
        self.minio_backend.write(
            {
                "minio_uses_signed_url_for_x_sendfile": True,
                "minio_signed_url_expiration": 60,
            }
        )

        url = self.fake_attachment_minio._get_x_sendfile_path()
        # Presigned URL should start with /fs_x_sendfile/http/localhost:9000/
        # and include query parameters
        self.assertTrue(
            url.startswith(
                "/fs_x_sendfile/http/localhost:9000/"
                "test-bucket/dir/sub/fake_minio_file.txt?"
            ),
            "The presigned URL should contain the path and query parameters. "
            f"({url})",
        )

    def test_get_x_sendfile_path_minio_signed_with_prefix(self):
        """Test the path generation when the directory path has a prefix."""
        self.minio_backend.write(
            {
                "minio_uses_signed_url_for_x_sendfile": True,
                "minio_signed_url_expiration": 60,
                "directory_path": "test-bucket/test-prefix",
            }
        )

        url = self.fake_attachment_minio._get_x_sendfile_path()
        self.assertTrue(
            url.startswith(
                "/fs_x_sendfile/http/localhost:9000/"
                "test-bucket/test-prefix/dir/sub/fake_minio_file.txt?"
            ),
            "The presigned URL should include the directory prefix. "
            f"({url})",
        )

    def test_is_minio_storage(self):
        """Test the is_minio_storage property."""
        self.assertTrue(
            self.minio_backend.fs_storage_id.is_minio_storage,
            "Storage should be identified as MinIO storage when protocol='minio'",
        )
