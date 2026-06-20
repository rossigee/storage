# Copyright 2025 Ross Golder <ross@golder.org>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models


class FsStorage(models.Model):

    _inherit = "fs.storage"

    minio_uses_signed_url_for_x_sendfile = fields.Boolean(
        string="Use signed URL for X-Accel-Redirect",
        help="If checked, the storage will use signed URLs for attachments "
        "when using X-Accel-Redirect. This is useful for MinIO storage where the "
        "file path is not directly accessible without authentication.",
    )
    minio_signed_url_expiration = fields.Integer(
        string="Signed URL Expiration (seconds)",
        default=30,
        help="The expiration time for the signed URL in seconds. "
        "Default is 30 seconds.",
    )

    @property
    def is_minio_storage(self):
        """Check if the storage is a MinIO storage."""
        self.ensure_one()
        return self.protocol == "s3" and self.options.get("endpoint_url")