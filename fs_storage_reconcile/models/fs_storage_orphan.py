# Copyright 2026 Ross Golder
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

import logging

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

_logger = logging.getLogger(__name__)


class FsStorageOrphan(models.Model):
    """An object in a storage with no ir.attachment pointing at it."""

    _name = "fs.storage.orphan"
    _description = "Storage object without an attachment"
    _inherit = ["mail.thread"]
    _order = "storage_id, path"
    _rec_name = "path"

    storage_id = fields.Many2one(
        "fs.storage", required=True, ondelete="cascade", index=True
    )
    path = fields.Char(
        required=True,
        index=True,
        help="Path inside the storage's root, as stored in ir.attachment.store_fname",
    )
    store_fname = fields.Char(compute="_compute_store_fname", store=True)
    size = fields.Integer(string="Size (bytes)")
    last_modified = fields.Datetime()
    state = fields.Selection(
        [
            ("new", "Unassigned"),
            ("assigned", "Assigned"),
            ("ignored", "Ignored"),
            ("deleted", "Deleted from bucket"),
        ],
        default="new",
        required=True,
        index=True,
        tracking=True,
    )
    attachment_id = fields.Many2one("ir.attachment", ondelete="set null", readonly=True)

    _sql_constraints = [
        (
            "storage_path_uniq",
            "unique (storage_id, path)",
            "This object is already listed for this storage.",
        ),
    ]

    @api.depends("storage_id.code", "path")
    def _compute_store_fname(self):
        for orphan in self:
            orphan.store_fname = (
                f"{orphan.storage_id.code}://{orphan.path}"
                if orphan.storage_id and orphan.path
                else False
            )

    def action_ignore(self):
        for orphan in self:
            orphan._check_state_new()
            orphan.write({"state": "ignored"})
            orphan.message_post(body=_("Marked as ignored by %s.") % self.env.user.name)

    def action_delete_from_bucket(self):
        """Remove the object from the bucket. Administrators only, never automatic."""
        if not self.env.user.has_group("base.group_system"):
            raise AccessError(
                _("Only administrators can delete objects from a bucket.")
            )
        for orphan in self:
            orphan._check_state_new()
            fs = orphan.storage_id.sudo().fs
            fs.rm_file(orphan.path)
            orphan.write({"state": "deleted"})
            orphan.message_post(
                body=_("Deleted from the bucket by %s.") % self.env.user.name
            )

    def _check_state_new(self):
        self.ensure_one()
        if self.state != "new":
            raise UserError(_("This object has already been %s.") % self.state)

    @api.model
    def _reconcile(self, storage, fs):
        """Compare the bucket listing with ir.attachment and record the differences.

        - Objects with no attachment become orphan rows (state ``new``).
        - Attachments whose object is gone are flagged ``is_missing``; flags are
          cleared when the object reappears.
        - Orphan rows whose object has gone, and that nobody has acted on, are removed.

        :param storage: the fs.storage record being reconciled
        :param fs: the fsspec filesystem rooted at the storage's directory
        """
        prefix = f"{storage.code}://"
        listed = fs.find("", detail=True)
        objects = {
            path: info
            for path, info in listed.items()
            if info.get("type", "file") == "file"
        }

        Attachment = self.env["ir.attachment"].sudo()
        attachments = Attachment.search([("store_fname", "=like", f"{prefix}%")])
        attachments = attachments.filtered(lambda a: a.store_fname.startswith(prefix))
        known_paths = {a.store_fname[len(prefix) :] for a in attachments}

        for attachment in attachments:
            path = attachment.store_fname[len(prefix) :]
            if path not in objects and not attachment.is_missing:
                attachment.write({"is_missing": True})
            elif path in objects and attachment.is_missing:
                attachment.write({"is_missing": False})

        existing = self.sudo().search([("storage_id", "=", storage.id)])
        existing_by_path = {orphan.path: orphan for orphan in existing}
        to_create = []
        for path, info in objects.items():
            if path in known_paths:
                continue
            orphan = existing_by_path.get(path)
            if orphan:
                orphan.size = info.get("size") or 0
            else:
                to_create.append(
                    {
                        "storage_id": storage.id,
                        "path": path,
                        "size": info.get("size") or 0,
                    }
                )
        self.sudo().create(to_create)

        gone = existing.filtered(lambda o: o.state == "new" and o.path not in objects)
        gone.unlink()
        _logger.info(
            "Reconciled storage %s: %s objects, %s new orphans, %s removed",
            storage.code,
            len(objects),
            len(to_create),
            len(gone),
        )
