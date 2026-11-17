# Copyright 2026 Ross Golder
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

from odoo import _, fields, models
from odoo.exceptions import AccessError


class FsStorage(models.Model):
    _inherit = "fs.storage"

    orphan_ids = fields.One2many("fs.storage.orphan", "storage_id", readonly=True)
    last_orphan_scan = fields.Datetime(readonly=True, copy=False)
    attachment_count = fields.Integer(compute="_compute_storage_stats")
    bytes_used = fields.Float(
        compute="_compute_storage_stats",
        help="Sum of file sizes of attachments stored in this storage",
    )
    missing_attachment_count = fields.Integer(
        string="Missing Attachments", compute="_compute_storage_stats"
    )
    orphan_count = fields.Integer(
        string="Unassigned Objects", compute="_compute_storage_stats"
    )

    def _compute_storage_stats(self):
        Attachment = self.env["ir.attachment"].sudo()
        Orphan = self.env["fs.storage.orphan"].sudo()
        for storage in self:
            domain = [("store_fname", "=like", f"{storage.code}://%")]
            attachments = Attachment.search(domain)
            prefix = f"{storage.code}://"
            attachments = attachments.filtered(
                lambda a, p=prefix: a.store_fname.startswith(p)
            )
            storage.attachment_count = len(attachments)
            storage.bytes_used = sum(attachments.mapped("file_size"))
            storage.missing_attachment_count = len(attachments.filtered("is_missing"))
            storage.orphan_count = Orphan.search_count(
                [("storage_id", "=", storage.id), ("state", "=", "new")]
            )

    def action_scan_orphans(self):
        """Queue a background scan of this storage's bucket."""
        self.ensure_one()
        if not self.env.user.has_group("base.group_system"):
            raise AccessError(_("Only administrators can scan a storage."))
        self.with_delay(
            description=_("Scan %s for orphaned objects") % self.name
        ).run_orphan_scan()
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Scan queued"),
                "message": _("The orphan scan of %s has been queued.") % self.name,
                "type": "info",
            },
        }

    def run_orphan_scan(self):
        """Background job: reconcile the bucket listing with ir.attachment."""
        self.ensure_one()
        self.env["fs.storage.orphan"]._reconcile(self, self.sudo().fs)
        self.last_orphan_scan = fields.Datetime.now()

    def action_view_orphans(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Unassigned Objects"),
            "res_model": "fs.storage.orphan",
            "view_mode": "tree,form",
            "domain": [("storage_id", "=", self.id)],
            "context": {"default_storage_id": self.id},
        }
