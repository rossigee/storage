# Copyright 2025 Ross Golder <ross@golder.org>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

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

        This method constructs the path for MinIO storage when using
        X-Accel-Redirect, similar to S3 but specifically for MinIO endpoints.
        """
        fs, storage_code, file_path = self._get_fs_parts()
        storage = self.env["fs.storage"].sudo().get_by_code(storage_code)
        root_fs = storage._get_root_filesystem(fs)

        client = root_fs.s3
        bucket_name, *prefix_parts = storage.get_directory_path().strip("/").split("/")
        minio_key = "/".join(prefix_parts + [file_path.lstrip("/")])

        if storage.minio_uses_signed_url_for_x_sendfile:
            import fsspec.asyn

            file_url = fsspec.asyn.sync(
                fsspec.asyn.get_loop(),
                client.generate_presigned_url,
                "get_object",
                Params={"Bucket": bucket_name, "Key": minio_key},
                ExpiresIn=storage.minio_signed_url_expiration,
            )
        else:
            endpoint = client.meta.endpoint_url.rstrip("/")
            file_url = f"{endpoint}/{bucket_name}/{minio_key.lstrip('/')}"

        from urllib.parse import urlparse

        parsed_url = urlparse(file_url)
        path = parsed_url.path.strip("/")
        query = parsed_url.query
        redirect_path = f"/fs_x_sendfile/{parsed_url.scheme}/{parsed_url.netloc}/{path}"
        if query:
            redirect_path += f"?{query}"
        return redirect_path