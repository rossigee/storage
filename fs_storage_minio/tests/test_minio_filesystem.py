# Copyright 2025 Ross Golder
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

import unittest
from unittest.mock import MagicMock, patch

from fs_storage_minio.minio_file_system import MinioFileSystem


class TestMinioFileSystem(unittest.TestCase):
    """Test MinioFileSystem basic functionality."""

    @patch("fs_storage_minio.minio_file_system.Minio")
    def test_init(self, mock_minio_class):
        """Test MinioFileSystem initialization."""
        mock_client = MagicMock()
        mock_minio_class.return_value = mock_client

        fs = MinioFileSystem(
            endpoint="localhost:9000",
            access_key="key",
            secret_key="secret",
            secure=False,
            region="us-east-1",
        )

        self.assertEqual(fs.endpoint, "localhost:9000")
        self.assertEqual(fs.access_key, "key")
        self.assertEqual(fs.secret_key, "secret")
        self.assertFalse(fs.secure)
        self.assertEqual(fs.region, "us-east-1")
        self.assertEqual(fs.client, mock_client)
        mock_minio_class.assert_called_once_with(
            "localhost:9000",
            access_key="key",
            secret_key="secret",
            session_token=None,
            secure=False,
            region="us-east-1",
        )

    @patch("fs_storage_minio.minio_file_system.Minio")
    def test_split_path(self, mock_minio_class):
        """Test path splitting into bucket and key."""
        mock_minio_class.return_value = MagicMock()
        fs = MinioFileSystem(endpoint="localhost:9000")

        # Test with bucket only
        bucket, key = fs._split_path("/mybucket")
        self.assertEqual(bucket, "mybucket")
        self.assertEqual(key, "")

        # Test with bucket and key
        bucket, key = fs._split_path("/mybucket/path/to/key")
        self.assertEqual(bucket, "mybucket")
        self.assertEqual(key, "path/to/key")

        # Test without leading slash
        bucket, key = fs._split_path("mybucket/path/to/key")
        self.assertEqual(bucket, "mybucket")
        self.assertEqual(key, "path/to/key")

    @patch("fs_storage_minio.minio_file_system.Minio")
    def test_make_path(self, mock_minio_class):
        """Test path construction from bucket and key."""
        mock_minio_class.return_value = MagicMock()
        fs = MinioFileSystem(endpoint="localhost:9000")

        # Test with key
        path = fs._make_path("mybucket", "path/to/key")
        self.assertEqual(path, "mybucket/path/to/key")

        # Test without key
        path = fs._make_path("mybucket", "")
        self.assertEqual(path, "mybucket")

    @patch("fs_storage_minio.minio_file_system.Minio")
    def test_exists(self, mock_minio_class):
        """Test exists method."""
        mock_client = MagicMock()
        mock_minio_class.return_value = mock_client

        # Mock stat_object to return successfully
        mock_client.stat_object.return_value = MagicMock()

        fs = MinioFileSystem(endpoint="localhost:9000")

        # Should return True when object exists
        result = fs.exists("/bucket/path/to/file")
        self.assertTrue(result)
        mock_client.stat_object.assert_called_with("bucket", "path/to/file")

    @patch("fs_storage_minio.minio_file_system.Minio")
    def test_rm_file(self, mock_minio_class):
        """Test rm_file method."""
        mock_client = MagicMock()
        mock_minio_class.return_value = mock_client

        fs = MinioFileSystem(endpoint="localhost:9000")
        fs.rm_file("/bucket/path/to/file")

        mock_client.remove_object.assert_called_once_with("bucket", "path/to/file")
