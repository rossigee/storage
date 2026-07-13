# Copyright 2025 Ross Golder
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

import io
import logging
from datetime import timedelta

import fsspec
import urllib3
from fsspec.spec import AbstractFileSystem
from fsspec.utils import infer_storage_options

_logger = logging.getLogger(__name__)

try:
    from minio import Minio
    from minio.commonconfig import CopySource
    from minio.error import S3Error

except ImportError as err:  # pragma: no cover
    _logger.debug(err)


class MinioFile(io.BytesIO):
    """A file-like object for MinIO storage.

    Handles read and write operations with buffering.
    For writes, data is buffered and flushed to MinIO on close.
    For reads, data is fetched from MinIO into the buffer.
    """

    def __init__(
        self, minio_fs, path, mode="rb", block_size=None, autocommit=True, **kwargs
    ):
        super().__init__()
        self.path = path
        self.mode = mode
        self.minio_fs = minio_fs
        self.autocommit = autocommit
        self.kwargs = kwargs

        if "r" in mode:
            self._fetch_from_minio()
        self.seek(0)

    def _fetch_from_minio(self):
        """Fetch the file content from MinIO into the buffer."""
        bucket, key = self.minio_fs._split_path(self.path)
        try:
            response = self.minio_fs.client.get_object(bucket, key)
            self.write(response.read())
            response.close()
            response.release_conn()
        except S3Error as e:
            if e.code == "NoSuchKey":
                pass  # File doesn't exist yet, that's OK
            else:
                raise

    def close(self):
        """Flush data to MinIO on close if in write mode."""
        if "w" in self.mode or "a" in self.mode:
            self._flush_to_minio()
        super().close()

    def _flush_to_minio(self):
        """Flush buffered data to MinIO."""
        bucket, key = self.minio_fs._split_path(self.path)
        data = self.getvalue()

        extra_args = {}
        if "content_type" in self.kwargs:
            extra_args["content_type"] = self.kwargs["content_type"]

        try:
            self.minio_fs.client.put_object(
                bucket,
                key,
                io.BytesIO(data),
                length=len(data),
                metadata=extra_args,
            )
        except S3Error as e:
            _logger.exception(f"Error writing file {self.path} to MinIO")
            raise


class MinioFileSystem(AbstractFileSystem):
    """A MinIO filesystem backed by the official minio Python SDK.

    This filesystem provides access to MinIO (S3-compatible) object storage
    through fsspec's standard interface.

    Parameters:
    -----------
    endpoint : str
        MinIO server endpoint (host:port), e.g., "localhost:9000"
    access_key : str, optional
        Access key for authentication
    secret_key : str, optional
        Secret key for authentication
    secure : bool, default True
        Whether to use HTTPS for connection
    region : str, optional
        AWS region name (default: "us-east-1")
    session_token : str, optional
        Session token for temporary credentials
    **kwargs
        Additional arguments passed to AbstractFileSystem
    """

    def __init__(
        self,
        endpoint,
        access_key=None,
        secret_key=None,
        secure=True,
        region=None,
        session_token=None,
        **kwargs
    ):
        super().__init__(**kwargs)
        self.endpoint = endpoint
        self.access_key = access_key
        self.secret_key = secret_key
        self.secure = secure
        self.region = region or "us-east-1"
        self.session_token = session_token

        try:
            http_client = urllib3.PoolManager(cert_reqs='CERT_NONE')
            self.client = Minio(
                endpoint,
                access_key=access_key,
                secret_key=secret_key,
                session_token=session_token,
                secure=secure,
                region=self.region,
                http_client=http_client,
            )
        except Exception as e:
            _logger.exception("Error initializing MinIO client")
            raise

    @staticmethod
    def _split_path(path):
        """Split a path into bucket and key.

        Path format: /bucket/path/to/key or bucket/path/to/key
        Returns (bucket, key) tuple.
        """
        path = path.lstrip("/")
        parts = path.split("/", 1)
        if len(parts) == 1:
            return parts[0], ""
        return parts[0], parts[1]

    @staticmethod
    def _make_path(bucket, key):
        """Combine bucket and key into a path."""
        if key:
            return f"{bucket}/{key}"
        return bucket

    def _open(self, path, mode="rb", block_size=None, autocommit=True, **kwargs):
        """Open a file-like object for reading or writing."""
        return MinioFile(
            self,
            path,
            mode=mode,
            block_size=block_size,
            autocommit=autocommit,
            **kwargs,
        )

    def ls(self, path, detail=True, refresh=False, versions=False):
        """List objects in a path (bucket or prefix)."""
        bucket, key_prefix = self._split_path(path)

        try:
            objects = self.client.list_objects(
                bucket, prefix=key_prefix, recursive=False
            )
            result = []
            for obj in objects:
                item = {
                    "name": obj.object_name,
                    "size": obj.size,
                    "type": "directory" if obj.object_name.endswith("/") else "file",
                    "time_modified": obj.last_modified,
                }
                if detail:
                    result.append(item)
                else:
                    result.append(item["name"])
            return result
        except S3Error as e:
            if e.code == "NoSuchBucket":
                return [] if not detail else []
            raise

    def info(self, path, **kwargs):
        """Get information about a path (object or bucket)."""
        bucket, key = self._split_path(path)

        try:
            if not key:
                # It's a bucket
                exists = self.client.bucket_exists(bucket)
                if exists:
                    return {
                        "name": bucket,
                        "size": 0,
                        "type": "directory",
                        "time_modified": None,
                    }
                else:
                    raise FileNotFoundError(f"Bucket {bucket} not found")

            stat = self.client.stat_object(bucket, key)
            return {
                "name": key,
                "size": stat.size,
                "type": "file",
                "time_modified": stat.last_modified,
            }
        except S3Error as e:
            if e.code == "NoSuchKey":
                raise FileNotFoundError(f"{path} not found")
            elif e.code == "NoSuchBucket":
                raise FileNotFoundError(f"Bucket {bucket} not found")
            raise

    def exists(self, path, **kwargs):
        """Check if a path exists."""
        try:
            self.info(path)
            return True
        except FileNotFoundError:
            return False

    def rm_file(self, path):
        """Delete a file."""
        bucket, key = self._split_path(path)
        try:
            self.client.remove_object(bucket, key)
        except S3Error as e:
            if e.code != "NoSuchKey":
                raise

    def rm(self, path, recursive=False, maxdepth=None):
        """Delete a file or directory recursively."""
        bucket, key = self._split_path(path)

        if not key:
            # Trying to delete a bucket
            if recursive:
                try:
                    objects = self.client.list_objects(bucket, recursive=True)
                    for obj in objects:
                        self.client.remove_object(bucket, obj.object_name)
                except S3Error as e:
                    if e.code != "NoSuchBucket":
                        raise
            try:
                self.client.remove_bucket(bucket)
            except S3Error as e:
                if e.code != "NoSuchBucket":
                    raise
        else:
            # Delete object or prefix
            if recursive or "/" in key:
                try:
                    objects = self.client.list_objects(
                        bucket, prefix=key, recursive=True
                    )
                    for obj in objects:
                        self.client.remove_object(bucket, obj.object_name)
                except S3Error as e:
                    if e.code != "NoSuchKey":
                        raise
            else:
                self.rm_file(path)

    def mkdir(self, path, create_parents=True, **kwargs):
        """Create a bucket (MinIO has no real directories)."""
        bucket, key = self._split_path(path)
        if key:
            # In object storage, creating a "directory" is a no-op
            return
        try:
            if not self.client.bucket_exists(bucket):
                self.client.make_bucket(bucket)
        except S3Error as e:
            if e.code != "BucketAlreadyOwnedByYou":
                raise

    def makedirs(self, path, exist_ok=False):
        """Create buckets and ensure path exists."""
        bucket, key = self._split_path(path)
        try:
            if not self.client.bucket_exists(bucket):
                self.client.make_bucket(bucket)
        except S3Error as e:
            if e.code == "BucketAlreadyOwnedByYou":
                if not exist_ok:
                    raise
            else:
                raise

    def touch(self, path, truncate=True, **kwargs):
        """Create an empty file."""
        bucket, key = self._split_path(path)
        if not key:
            # Can't touch a bucket
            return
        try:
            self.client.put_object(bucket, key, io.BytesIO(b""), length=0)
        except S3Error as e:
            raise

    def mv(self, path1, path2, **kwargs):
        """Move/rename a file (copy + delete)."""
        bucket1, key1 = self._split_path(path1)
        bucket2, key2 = self._split_path(path2)

        try:
            copy_source = CopySource(bucket1, key1)
            self.client.copy_object(bucket2, key2, copy_source)
            self.client.remove_object(bucket1, key1)
        except S3Error as e:
            _logger.exception(f"Error moving {path1} to {path2}")
            raise

    def rename(self, path1, path2, **kwargs):
        """Alias for mv."""
        return self.mv(path1, path2, **kwargs)

    def checksum(self, path):
        """Get the checksum (ETag) of a file."""
        bucket, key = self._split_path(path)
        try:
            stat = self.client.stat_object(bucket, key)
            return stat.etag
        except S3Error as e:
            if e.code == "NoSuchKey":
                raise FileNotFoundError(f"{path} not found")
            raise

    def size(self, path):
        """Get the size of a file in bytes."""
        bucket, key = self._split_path(path)
        try:
            stat = self.client.stat_object(bucket, key)
            return stat.size
        except S3Error as e:
            if e.code == "NoSuchKey":
                raise FileNotFoundError(f"{path} not found")
            raise


fsspec.register_implementation("minio", MinioFileSystem)
