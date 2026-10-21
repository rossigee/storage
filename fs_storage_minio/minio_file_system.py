# Copyright 2025 Ross Golder
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

import io
import logging
import tempfile

import urllib3
from fsspec.registry import register_implementation
from fsspec.spec import AbstractFileSystem

_logger = logging.getLogger(__name__)

try:
    from minio import Minio
    from minio.commonconfig import CopySource
    from minio.error import S3Error

except ImportError as err:  # pragma: no cover
    _logger.debug(err)


# Writes up to this size stay in memory; larger ones spill to a temporary file
WRITE_SPOOL_BYTES = 8 * 1024 * 1024
# Read-ahead buffer wrapped around the streaming reader
READ_BUFFER_BYTES = 1024 * 1024


class MinioReadFile(io.RawIOBase):
    """Read-only file that fetches byte ranges from MinIO as they are read.

    Memory use depends on what the caller reads, not on the object's size.
    """

    def __init__(self, minio_fs, path):
        bucket, key = minio_fs._split_path(path)
        try:
            self._size = minio_fs.client.stat_object(bucket, key).size
        except S3Error as e:
            if e.code == "NoSuchKey":
                # Reading a missing object must fail, never return empty content
                raise FileNotFoundError(f"{path} not found") from e
            raise
        self._client = minio_fs.client
        self._bucket = bucket
        self._key = key
        self._pos = 0

    def readable(self):
        return True

    def seekable(self):
        return True

    def tell(self):
        return self._pos

    def seek(self, offset, whence=io.SEEK_SET):
        if whence == io.SEEK_SET:
            pos = offset
        elif whence == io.SEEK_CUR:
            pos = self._pos + offset
        elif whence == io.SEEK_END:
            pos = self._size + offset
        else:
            raise ValueError(f"invalid whence: {whence}")
        if pos < 0:
            raise ValueError("negative seek position")
        self._pos = pos
        return pos

    def readinto(self, buffer):
        view = memoryview(buffer).cast("B")
        wanted = min(len(view), max(self._size - self._pos, 0))
        if wanted == 0:
            return 0
        response = self._client.get_object(
            self._bucket, self._key, offset=self._pos, length=wanted
        )
        try:
            data = response.read()
        finally:
            response.close()
            response.release_conn()
        view[: len(data)] = data
        self._pos += len(data)
        return len(data)


class MinioFile(tempfile.SpooledTemporaryFile):
    """Write-only file. Content is spooled locally, then uploaded on close.

    The upload is a single put_object with the known length, so the SDK can
    split large objects into parts itself.
    """

    def __init__(self, minio_fs, path, content_type=None):
        super().__init__(max_size=WRITE_SPOOL_BYTES, mode="w+b")
        self._minio_fs = minio_fs
        self._path = path
        self._content_type = content_type or "application/octet-stream"

    def close(self):
        if self.closed:
            return
        try:
            bucket, key = self._minio_fs._split_path(self._path)
            length = self.tell()
            self.seek(0)
            # content_type is a put_object argument, not user metadata
            self._minio_fs.client.put_object(
                bucket,
                key,
                self,
                length=length,
                content_type=self._content_type,
            )
        except S3Error:
            _logger.exception(f"Error writing file {self._path} to MinIO")
            raise
        finally:
            super().close()


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
        ca_certs=None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.endpoint = endpoint
        self.access_key = access_key
        self.secret_key = secret_key
        self.secure = secure
        self.region = region or "us-east-1"
        self.session_token = session_token

        # TLS certificates are always verified. ``ca_certs`` only adds a CA bundle
        # to trust (e.g. an internal CA); it never disables verification.
        client_options = {}
        if ca_certs:
            client_options["http_client"] = urllib3.PoolManager(
                cert_reqs="CERT_REQUIRED", ca_certs=ca_certs
            )
        try:
            self.client = Minio(
                endpoint,
                access_key=access_key,
                secret_key=secret_key,
                session_token=session_token,
                secure=secure,
                region=self.region,
                **client_options,
            )
        except Exception:
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
        """Open a streaming reader, or a spooled writer that uploads on close."""
        if "r" in mode:
            raw = MinioReadFile(self, path)
            return io.BufferedReader(raw, buffer_size=READ_BUFFER_BYTES)
        return MinioFile(self, path, content_type=kwargs.get("content_type"))

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
                    "name": self._make_path(bucket, obj.object_name),
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
                "name": self._make_path(bucket, key),
                "size": stat.size,
                "type": "file",
                "time_modified": stat.last_modified,
            }
        except S3Error as e:
            if e.code == "NoSuchKey":
                raise FileNotFoundError(f"{path} not found") from e
            elif e.code == "NoSuchBucket":
                raise FileNotFoundError(f"Bucket {bucket} not found") from e
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
            # Delete the object itself. A directory is only ever the objects under
            # "key/"; a plain prefix match would also delete "key.pdf", "key2", etc.
            if recursive:
                self.rm_file(path)
                try:
                    objects = self.client.list_objects(
                        bucket, prefix=f"{key.rstrip('/')}/", recursive=True
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
        except S3Error:
            raise

    def mv(self, path1, path2, **kwargs):
        """Move/rename a file (copy + delete)."""
        bucket1, key1 = self._split_path(path1)
        bucket2, key2 = self._split_path(path2)

        try:
            copy_source = CopySource(bucket1, key1)
            self.client.copy_object(bucket2, key2, copy_source)
            self.client.remove_object(bucket1, key1)
        except S3Error:
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
                raise FileNotFoundError(f"{path} not found") from e
            raise

    def size(self, path):
        """Get the size of a file in bytes."""
        bucket, key = self._split_path(path)
        try:
            stat = self.client.stat_object(bucket, key)
            return stat.size
        except S3Error as e:
            if e.code == "NoSuchKey":
                raise FileNotFoundError(f"{path} not found") from e
            raise


register_implementation("minio", MinioFileSystem)
