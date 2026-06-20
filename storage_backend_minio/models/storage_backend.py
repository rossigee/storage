# Copyright 2025 Ross Golder <ross@golder.org>
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

from odoo import fields, models


class StorageBackend(models.Model):
    _inherit = "storage.backend"

    backend_type = fields.Selection(
        selection_add=[("minio", "MinIO")],
        ondelete={"minio": "set default"},
    )
    minio_host = fields.Char(
        string="MinIO Host",
        help="MinIO server host (e.g., localhost:9000)",
    )
    minio_bucket = fields.Char(string="Bucket")
    minio_access_key = fields.Char(string="Access Key")
    minio_secret_key = fields.Char(string="Secret Key")
    minio_region = fields.Char(
        string="Region",
        help="Region name (optional, default is 'us-east-1')",
    )
    minio_cache_control = fields.Char(default="max-age=31536000, public")
    minio_file_acl = fields.Selection(
        selection=[
            ("", ""),
            ("private", "private"),
            ("public-read", "public-read"),
            ("public-read-write", "public-read-write"),
            ("authenticated-read", "authenticated-read"),
            ("bucket-owner-read", "bucket-owner-read"),
            ("bucket-owner-full-control", "bucket-owner-full-control"),
        ]
    )
    minio_secure = fields.Boolean(
        string="Use SSL/TLS",
        default=True,
        help="Use HTTPS for connection to MinIO server",
    )

    @property
    def _server_env_fields(self):
        env_fields = super()._server_env_fields
        env_fields.update(
            {
                "minio_host": {},
                "minio_bucket": {},
                "minio_access_key": {},
                "minio_secret_key": {},
                "minio_region": {},
                "minio_cache_control": {},
                "minio_file_acl": {},
                "minio_secure": {},
            }
        )
        return env_fields