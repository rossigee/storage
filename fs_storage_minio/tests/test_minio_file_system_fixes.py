# Copyright 2025 Ross Golder
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

"""Unit tests for MinioFileSystem fixes, run without a MinIO server.

Run with ``python3 -m unittest`` from the module's parent directory, in an image
that has the ``minio`` and ``fsspec`` packages installed.
"""

import io
import unittest
from unittest import mock

from minio.error import S3Error

from fs_storage_minio.minio_file_system import (
    MinioFile,
    MinioFileSystem,
    MinioReadFile,
)


def _s3_error(code):
    return S3Error(mock.Mock(), code, "msg", "resource", "req", "host")


def _fake_fs(data=None):
    """A stand-in filesystem whose client serves ``data`` as a single object."""
    fs = mock.Mock()
    fs._split_path = MinioFileSystem._split_path
    if data is not None:
        fs.client.stat_object.return_value = mock.Mock(size=len(data))

        def get_object(bucket, key, offset=0, length=0, **kwargs):
            body = data[offset : offset + length] if length else data[offset:]
            response = io.BytesIO(body)
            response.release_conn = mock.Mock()
            return response

        fs.client.get_object.side_effect = get_object
    return fs


class TestTls(unittest.TestCase):
    @mock.patch("fs_storage_minio.minio_file_system.Minio")
    def test_default_client_uses_sdk_verification(self, minio_cls):
        MinioFileSystem(
            "minio.example:9000",
            access_key="a",
            secret_key="s",
            skip_instance_cache=True,
        )
        self.assertNotIn("http_client", minio_cls.call_args.kwargs)

    @mock.patch("fs_storage_minio.minio_file_system.Minio")
    @mock.patch("fs_storage_minio.minio_file_system.urllib3.PoolManager")
    def test_ca_bundle_still_requires_verification(self, pool, minio_cls):
        MinioFileSystem(
            "minio.example:9000",
            ca_certs="/etc/ssl/ca.pem",
            skip_instance_cache=True,
        )
        pool.assert_called_once_with(
            cert_reqs="CERT_REQUIRED", ca_certs="/etc/ssl/ca.pem"
        )


class TestMissingKey(unittest.TestCase):
    def test_reading_a_missing_object_raises(self):
        fs = _fake_fs()
        fs.client.stat_object.side_effect = _s3_error("NoSuchKey")
        with self.assertRaises(FileNotFoundError):
            MinioReadFile(fs, "bucket/missing.pdf")

    def test_other_errors_still_propagate(self):
        fs = _fake_fs()
        fs.client.stat_object.side_effect = _s3_error("AccessDenied")
        with self.assertRaises(S3Error):
            MinioReadFile(fs, "bucket/key.pdf")


class TestStreamingRead(unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.data = bytes(range(256)) * 1000  # 256000 bytes

    def test_reads_the_whole_object_in_pieces(self):
        fs = _fake_fs(self.data)
        f = MinioReadFile(fs, "bucket/big.bin")
        out = b""
        while True:
            chunk = f.read(10000)
            if not chunk:
                break
            out += chunk
        self.assertEqual(out, self.data)

    def test_each_range_request_is_bounded_by_what_was_asked(self):
        fs = _fake_fs(self.data)
        f = MinioReadFile(fs, "bucket/big.bin")
        f.read(4096)
        self.assertEqual(
            fs.client.get_object.call_args.kwargs["length"],
            4096,
        )
        self.assertEqual(fs.client.get_object.call_args.kwargs["offset"], 0)

    def test_seek_then_read_returns_the_right_bytes(self):
        fs = _fake_fs(self.data)
        f = MinioReadFile(fs, "bucket/big.bin")
        f.seek(100000)
        self.assertEqual(f.read(5), self.data[100000:100005])
        f.seek(-10, io.SEEK_END)
        self.assertEqual(f.read(), self.data[-10:])

    def test_reading_past_the_end_returns_empty(self):
        fs = _fake_fs(self.data)
        f = MinioReadFile(fs, "bucket/big.bin")
        f.seek(0, io.SEEK_END)
        self.assertEqual(f.read(10), b"")


class TestOpen(unittest.TestCase):
    @mock.patch("fs_storage_minio.minio_file_system.Minio")
    def test_open_read_streams_through_fsspec(self, minio_cls):
        data = b"hello world" * 100
        client = minio_cls.return_value
        client.stat_object.return_value = mock.Mock(size=len(data))

        def get_object(bucket, key, offset=0, length=0, **kwargs):
            response = io.BytesIO(data[offset : offset + length])
            response.release_conn = mock.Mock()
            return response

        client.get_object.side_effect = get_object
        fs = MinioFileSystem("minio.example:9000", skip_instance_cache=True)
        with fs.open("bucket/doc.txt", "rb") as f:
            self.assertEqual(f.read(), data)

    @mock.patch("fs_storage_minio.minio_file_system.Minio")
    def test_open_missing_object_raises_through_fsspec(self, minio_cls):
        minio_cls.return_value.stat_object.side_effect = _s3_error("NoSuchKey")
        fs = MinioFileSystem("minio.example:9000", skip_instance_cache=True)
        with self.assertRaises(FileNotFoundError):
            fs.open("bucket/missing.txt", "rb")


class TestRmPrefix(unittest.TestCase):
    def setUp(self):
        super().setUp()
        with mock.patch("fs_storage_minio.minio_file_system.Minio"):
            self.fs = MinioFileSystem("minio.example:9000", skip_instance_cache=True)
        self.client = self.fs.client

    def test_non_recursive_delete_removes_only_that_object(self):
        self.fs.rm("bucket/a/b.pdf")
        self.client.remove_object.assert_called_once_with("bucket", "a/b.pdf")
        self.client.list_objects.assert_not_called()

    def test_recursive_delete_lists_only_under_the_directory(self):
        self.client.list_objects.return_value = []
        self.fs.rm("bucket/a/b", recursive=True)
        self.client.list_objects.assert_called_once_with(
            "bucket", prefix="a/b/", recursive=True
        )


class TestWrite(unittest.TestCase):
    def test_content_type_is_a_put_object_argument(self):
        fs = _fake_fs()
        f = MinioFile(fs, "bucket/doc.pdf", content_type="application/pdf")
        f.write(b"%PDF")
        f.close()
        kwargs = fs.client.put_object.call_args.kwargs
        self.assertEqual(kwargs["content_type"], "application/pdf")
        self.assertEqual(kwargs["length"], 4)
        self.assertNotIn("metadata", kwargs)

    def test_default_content_type(self):
        fs = _fake_fs()
        f = MinioFile(fs, "bucket/blob")
        f.write(b"x")
        f.close()
        self.assertEqual(
            fs.client.put_object.call_args.kwargs["content_type"],
            "application/octet-stream",
        )

    def test_large_write_uploads_with_its_full_length(self):
        fs = _fake_fs()
        uploaded = {}

        def put_object(bucket, key, data, length, **kwargs):
            uploaded["body"] = data.read()
            uploaded["length"] = length

        fs.client.put_object.side_effect = put_object
        payload = b"a" * (9 * 1024 * 1024)  # above the in-memory spool threshold
        f = MinioFile(fs, "bucket/large.bin")
        f.write(payload)
        f.close()
        self.assertEqual(uploaded["length"], len(payload))
        self.assertEqual(uploaded["body"], payload)


if __name__ == "__main__":
    unittest.main()
