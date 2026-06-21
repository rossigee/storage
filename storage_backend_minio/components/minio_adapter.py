# Copyright 2025 Ross Golder <ross@golder.org>
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

import io
import logging

from odoo import exceptions

from odoo.addons.component.core import Component

_logger = logging.getLogger(__name__)

try:
    from minio import Minio
    from minio.error import S3Error

except ImportError as err:  # pragma: no cover
    _logger.debug(err)


class MinIOStorageAdapter(Component):
    _name = "minio.adapter"
    _inherit = "base.storage.adapter"
    _usage = "minio"

    def _get_client(self):
        endpoint = self.collection.minio_host or "localhost:9000"
        client = Minio(
            endpoint,
            access_key=self.collection.minio_access_key,
            secret_key=self.collection.minio_secret_key,
            secure=self.collection.minio_secure,
            region=self.collection.minio_region or "us-east-1",
        )
        return client

    def _get_bucket(self):
        client = self._get_client()
        bucket_name = self.collection.minio_bucket

        try:
            if not client.bucket_exists(bucket_name):
                client.make_bucket(bucket_name)
        except S3Error as error:
            _logger.exception("Error connecting to MinIO")
            raise exceptions.UserError(str(error)) from error

        return client.bucket(bucket_name)

    def add(self, relative_path, bin_data, mimetype=None, **kwargs):
        client = self._get_client()
        bucket_name = self.collection.minio_bucket
        full_path = self._fullpath(relative_path)

        extra_args = {}
        if mimetype:
            extra_args["content_type"] = mimetype
        if self.collection.minio_cache_control:
            extra_args["cache_control"] = self.collection.minio_cache_control
        if self.collection.minio_file_acl:
            extra_args["acl"] = self.collection.minio_file_acl

        try:
            data = io.BytesIO(bin_data)
            client.put_object(
                bucket_name,
                full_path,
                data,
                length=len(bin_data),
                part_size=5 * 1024 * 1024,
                metadata=extra_args,
            )
        except S3Error as error:
            _logger.exception(f"Error storing file {relative_path} to MinIO")
            raise exceptions.UserError(
                self.env._(f"The file could not be stored: {str(error)}")
            ) from error

    def get(self, relative_path):
        client = self._get_client()
        bucket_name = self.collection.minio_bucket
        full_path = self._fullpath(relative_path)

        try:
            response = client.get_object(bucket_name, full_path)
            data = response.read()
            response.close()
            response.release_conn()
            return data
        except S3Error as error:
            if error.code == "NoSuchKey":
                return None
            _logger.exception(f"Error reading file {relative_path} from MinIO")
            raise exceptions.UserError(
                self.env._(f"The file could not be read: {str(error)}")
            ) from error

    def list(self, relative_path):
        client = self._get_client()
        bucket_name = self.collection.minio_bucket
        dir_path = self.collection.directory_path or ""
        prefix = self._fullpath(dir_path)

        try:
            objects = client.list_objects(bucket_name, prefix=prefix, recursive=True)
            return [
                obj.object_name.replace(dir_path, "").lstrip("/")
                for obj in objects
            ]
        except S3Error as error:
            _logger.exception(f"Error listing files in MinIO")
            raise exceptions.UserError(
                self.env._(f"Could not list files: {str(error)}")
            ) from error

    def delete(self, relative_path):
        client = self._get_client()
        bucket_name = self.collection.minio_bucket
        full_path = self._fullpath(relative_path)

        try:
            client.remove_object(bucket_name, full_path)
            return True
        except S3Error as error:
            if error.code == "NoSuchKey":
                return False
            _logger.exception(f"Error deleting file {relative_path} from MinIO")
            raise exceptions.UserError(
                self.env._(f"The file could not be deleted: {str(error)}")
            ) from error

    def validate_config(self):
        client = self._get_client()
        bucket_name = self.collection.minio_bucket

        try:
            if not client.bucket_exists(bucket_name):
                client.make_bucket(bucket_name)
        except S3Error as error:
            raise exceptions.UserError(
                self.env._(f"Connection to MinIO failed: {str(error)}")
            ) from error
        return True