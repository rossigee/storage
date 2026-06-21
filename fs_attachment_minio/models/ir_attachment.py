# Copyright 2025 Ross Golder <ross@golder.org>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from datetime import timedelta
from urllib.parse import urlparse

from odoo import models


class IrAttachment(models.Model):

    _inherit = "ir.attachment"

    def _get_x_sendfile_path(self):
        self.ensure_one()
        storage = self.fs_storage_id
        if storage.is_minio_storage:
            return self._get_minio_x_sendfile_path()
        return super()._get_x_sendfile_path()

    def _fs_use_x_sendfile(self):
        self.ensure_one()
        storage = self.fs_storage_id
        if storage.is_minio_storage:
            return storage.use_x_sendfile_to_serve_internal_url
        return super()._fs_use_x_sendfile()

    def _get_minio_x_sendfile_path(self):
        """Generate the X-Accel-Redirect path for MinIO storage.

        This method constructs a presigned URL (or unsigned URL) for MinIO storage
        when using X-Accel-Redirect, using the official minio Python SDK.
        """
        fs, storage_code, file_path = self._get_fs_parts()
        storage = self.env["fs.storage"].sudo().get_by_code(storage_code)
        root_fs = storage._get_root_filesystem(fs)

        # root_fs is a MinioFileSystem instance; client is the minio.Minio client
        client = root_fs.client
        bucket_name, *prefix_parts = storage.get_directory_path().strip("/").split("/")
        minio_key = "/".join(prefix_parts + [file_path.lstrip("/")])

        if storage.minio_uses_signed_url_for_x_sendfile:
            # Generate a presigned URL using the minio SDK (synchronous)
            file_url = client.presigned_get_object(
                bucket_name,
                minio_key,
                expires=timedelta(seconds=storage.minio_signed_url_expiration),
            )
        else:
            # Build an unsigned URL from the endpoint configuration
            scheme = "https" if root_fs.secure else "http"
            endpoint = root_fs.endpoint.rstrip("/")
            file_url = f"{scheme}://{endpoint}/{bucket_name}/{minio_key.lstrip('/')}"

        parsed_url = urlparse(file_url)
        path = parsed_url.path.strip("/")
        query = parsed_url.query
        redirect_path = f"/fs_x_sendfile/{parsed_url.scheme}/{parsed_url.netloc}/{path}"
        if query:
            redirect_path += f"?{query}"
        return redirect_path