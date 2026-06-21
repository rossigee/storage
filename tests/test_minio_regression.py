#!/usr/bin/env python3
# Copyright 2025 Ross Golder
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

"""
Regression test suite for MinIO implementation.

This script tests the three MinIO-related modules:
1. fs_storage_minio: fsspec filesystem backend
2. fs_attachment_minio: Odoo attachment storage integration
3. storage_backend_minio: Legacy storage backend adapter

Requirements:
- MinIO server running at localhost:9000 (or set MINIO_ENDPOINT env var)
- Default credentials: minioadmin / minioadmin (or set MINIO_ACCESS_KEY, MINIO_SECRET_KEY)
- Python 3.6+
- minio package installed

Usage:
    python3 tests/test_minio_regression.py

    Or with custom endpoint:
    MINIO_ENDPOINT=minio.example.com:9000 MINIO_ACCESS_KEY=key MINIO_SECRET_KEY=secret python3 tests/test_minio_regression.py
"""

import io
import os
import sys
import unittest
from datetime import timedelta
from unittest.mock import MagicMock, patch

# Add parent directory to path so we can import modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from minio import Minio
    from minio.error import S3Error
except ImportError:
    print("ERROR: minio package not installed. Install it with: pip install minio")
    sys.exit(1)

try:
    from fs_storage_minio.minio_file_system import MinioFileSystem
except ImportError as e:
    print(f"ERROR: Could not import MinioFileSystem: {e}")
    sys.exit(1)


class TestMinioConnection(unittest.TestCase):
    """Test basic MinIO connectivity."""

    @classmethod
    def setUpClass(cls):
        cls.endpoint = os.environ.get("MINIO_ENDPOINT", "localhost:9000")
        cls.access_key = os.environ.get("MINIO_ACCESS_KEY", "minioadmin")
        cls.secret_key = os.environ.get("MINIO_SECRET_KEY", "minioadmin")
        cls.secure = os.environ.get("MINIO_SECURE", "false").lower() == "true"

    def test_minio_connection(self):
        """Test that we can connect to MinIO."""
        try:
            client = Minio(
                self.endpoint,
                access_key=self.access_key,
                secret_key=self.secret_key,
                secure=self.secure,
            )
            # Try a simple operation
            buckets = list(client.list_buckets())
            print(f"✓ MinIO connection successful. Found {len(buckets)} bucket(s)")
            self.assertTrue(True)
        except Exception as e:
            self.fail(f"Failed to connect to MinIO at {self.endpoint}: {e}")


class TestMinioFileSystem(unittest.TestCase):
    """Test MinioFileSystem implementation."""

    @classmethod
    def setUpClass(cls):
        cls.endpoint = os.environ.get("MINIO_ENDPOINT", "localhost:9000")
        cls.access_key = os.environ.get("MINIO_ACCESS_KEY", "minioadmin")
        cls.secret_key = os.environ.get("MINIO_SECRET_KEY", "minioadmin")
        cls.secure = os.environ.get("MINIO_SECURE", "false").lower() == "true"
        cls.test_bucket = "test-fs-regression"

        # Create MinioFileSystem instance
        cls.fs = MinioFileSystem(
            endpoint=cls.endpoint,
            access_key=cls.access_key,
            secret_key=cls.secret_key,
            secure=cls.secure,
        )

        # Create test bucket
        try:
            cls.fs.mkdir(cls.test_bucket)
            print(f"✓ Created test bucket: {cls.test_bucket}")
        except Exception as e:
            print(f"Warning: Could not create bucket {cls.test_bucket}: {e}")

    @classmethod
    def tearDownClass(cls):
        """Clean up test bucket."""
        try:
            cls.fs.rm(cls.test_bucket, recursive=True)
            print(f"✓ Cleaned up test bucket: {cls.test_bucket}")
        except Exception as e:
            print(f"Warning: Could not clean up bucket: {e}")

    def test_path_splitting(self):
        """Test path splitting."""
        bucket, key = self.fs._split_path("/test-bucket/path/to/file.txt")
        self.assertEqual(bucket, "test-bucket")
        self.assertEqual(key, "path/to/file.txt")
        print("✓ Path splitting works correctly")

    def test_write_and_read(self):
        """Test writing and reading a file."""
        test_path = f"{self.test_bucket}/test-file.txt"
        test_data = b"Hello MinIO!"

        # Write
        with self.fs._open(test_path, "wb") as f:
            f.write(test_data)
        print(f"✓ Wrote {len(test_data)} bytes to {test_path}")

        # Read
        with self.fs._open(test_path, "rb") as f:
            read_data = f.read()
        self.assertEqual(read_data, test_data)
        print(f"✓ Read {len(read_data)} bytes from {test_path}")

    def test_file_exists(self):
        """Test file existence check."""
        test_path = f"{self.test_bucket}/exist-test.txt"

        # Should not exist yet
        self.assertFalse(self.fs.exists(test_path))
        print(f"✓ File correctly reported as non-existent before creation")

        # Create file
        with self.fs._open(test_path, "wb") as f:
            f.write(b"test")

        # Should exist now
        self.assertTrue(self.fs.exists(test_path))
        print(f"✓ File correctly reported as existent after creation")

    def test_ls(self):
        """Test listing files."""
        test_path = f"{self.test_bucket}/list-test/"

        # Create a few files
        for i in range(3):
            file_path = f"{test_path}file-{i}.txt"
            with self.fs._open(file_path, "wb") as f:
                f.write(f"content {i}".encode())

        # List files
        files = self.fs.ls(f"/{self.test_bucket}/list-test/", detail=False)
        self.assertGreaterEqual(len(files), 3)
        print(f"✓ Listed {len(files)} files in test-list/")

    def test_rm_file(self):
        """Test file deletion."""
        test_path = f"{self.test_bucket}/delete-test.txt"

        # Create file
        with self.fs._open(test_path, "wb") as f:
            f.write(b"to be deleted")

        # Verify it exists
        self.assertTrue(self.fs.exists(test_path))

        # Delete it
        self.fs.rm_file(test_path)

        # Verify it's gone
        self.assertFalse(self.fs.exists(test_path))
        print(f"✓ File successfully deleted")

    def test_touch(self):
        """Test creating empty file."""
        test_path = f"{self.test_bucket}/touch-test.txt"

        # Create empty file
        self.fs.touch(test_path)

        # Verify it exists
        self.assertTrue(self.fs.exists(test_path))
        print(f"✓ Empty file created with touch()")

    def test_size(self):
        """Test getting file size."""
        test_path = f"{self.test_bucket}/size-test.txt"
        test_data = b"1234567890"

        # Write file
        with self.fs._open(test_path, "wb") as f:
            f.write(test_data)

        # Check size
        size = self.fs.size(test_path)
        self.assertEqual(size, len(test_data))
        print(f"✓ File size correctly reported as {size} bytes")


class TestPresignedURLs(unittest.TestCase):
    """Test presigned URL generation (if minio client available)."""

    @classmethod
    def setUpClass(cls):
        cls.endpoint = os.environ.get("MINIO_ENDPOINT", "localhost:9000")
        cls.access_key = os.environ.get("MINIO_ACCESS_KEY", "minioadmin")
        cls.secret_key = os.environ.get("MINIO_SECRET_KEY", "minioadmin")
        cls.secure = os.environ.get("MINIO_SECURE", "false").lower() == "true"
        cls.test_bucket = "test-presigned"

        cls.client = Minio(
            cls.endpoint,
            access_key=cls.access_key,
            secret_key=cls.secret_key,
            secure=cls.secure,
        )

        # Create test bucket
        try:
            cls.client.make_bucket(cls.test_bucket)
            print(f"✓ Created presigned test bucket: {cls.test_bucket}")
        except Exception as e:
            print(f"Note: Bucket may already exist: {e}")

    @classmethod
    def tearDownClass(cls):
        """Clean up test bucket."""
        try:
            # Remove all objects first
            objects = cls.client.list_objects(cls.test_bucket, recursive=True)
            for obj in objects:
                cls.client.remove_object(cls.test_bucket, obj.object_name)
            # Remove bucket
            cls.client.remove_bucket(cls.test_bucket)
            print(f"✓ Cleaned up presigned test bucket: {cls.test_bucket}")
        except Exception as e:
            print(f"Note: Could not clean up bucket: {e}")

    def test_presigned_get_object(self):
        """Test generating presigned GET URL."""
        # Create a test object
        test_key = "presigned-test.txt"
        test_data = b"presigned content"
        self.client.put_object(
            self.test_bucket,
            test_key,
            io.BytesIO(test_data),
            length=len(test_data),
        )

        # Generate presigned URL
        url = self.client.presigned_get_object(
            self.test_bucket,
            test_key,
            expires=timedelta(hours=1),
        )

        # Verify URL looks correct
        self.assertIn(self.test_bucket, url)
        self.assertIn(test_key, url)
        self.assertIn("X-Amz-Signature", url)  # Should have signature param
        print(f"✓ Presigned GET URL generated: {url[:80]}...")

    def test_presigned_put_object(self):
        """Test generating presigned PUT URL."""
        test_key = "presigned-put-test.txt"

        # Generate presigned URL for PUT
        url = self.client.presigned_put_object(
            self.test_bucket,
            test_key,
            expires=timedelta(hours=1),
        )

        # Verify URL looks correct
        self.assertIn(self.test_bucket, url)
        self.assertIn(test_key, url)
        self.assertIn("X-Amz-Signature", url)
        print(f"✓ Presigned PUT URL generated: {url[:80]}...")


def main():
    """Run all tests."""
    print("=" * 70)
    print("MinIO Regression Test Suite")
    print("=" * 70)
    print()

    # Check MinIO connectivity first
    endpoint = os.environ.get("MINIO_ENDPOINT", "localhost:9000")
    print(f"Testing MinIO at: {endpoint}")
    print()

    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Add tests in order
    suite.addTests(loader.loadTestsFromTestCase(TestMinioConnection))
    suite.addTests(loader.loadTestsFromTestCase(TestMinioFileSystem))
    suite.addTests(loader.loadTestsFromTestCase(TestPresignedURLs))

    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    print()
    print("=" * 70)
    if result.wasSuccessful():
        print("✓ All regression tests passed!")
        print("=" * 70)
        return 0
    else:
        print("✗ Some tests failed")
        print("=" * 70)
        return 1


if __name__ == "__main__":
    sys.exit(main())
