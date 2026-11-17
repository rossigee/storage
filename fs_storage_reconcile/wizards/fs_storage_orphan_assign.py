# Copyright 2026 Ross Golder
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

import mimetypes
import os

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class FsStorageOrphanAssign(models.TransientModel):
    """Attach an existing, unassigned object to a record. Nothing is re-uploaded."""

    _name = "fs.storage.orphan.assign"
    _description = "Assign an unassigned storage object to a record"

    orphan_id = fields.Many2one(
        "fs.storage.orphan", required=True, readonly=True, ondelete="cascade"
    )
    name = fields.Char(string="Attachment Name", required=True)
    res_model = fields.Char(
        string="Model",
        required=True,
        help="Technical model name, e.g. bureaucracy.application",
    )
    res_id = fields.Integer(string="Record ID", required=True)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        orphan = self.env["fs.storage.orphan"].browse(res.get("orphan_id"))
        if orphan and "name" in fields_list:
            res["name"] = os.path.basename(orphan.path)
        return res

    def action_assign(self):
        self.ensure_one()
        orphan = self.orphan_id
        orphan._check_state_new()
        if self.res_model not in self.env:
            raise UserError(_("Unknown model %s.") % self.res_model)
        # Check the user can see the target record before linking anything to it
        record = self.env[self.res_model].browse(self.res_id).exists()
        if not record:
            raise UserError(
                _("No %(model)s record with ID %(id)s.")
                % {"model": self.res_model, "id": self.res_id}
            )
        record.check_access_rights("read")
        record.check_access_rule("read")

        mimetype = mimetypes.guess_type(self.name)[0] or "application/octet-stream"
        attachment = (
            self.env["ir.attachment"]
            .sudo()
            .create(
                {
                    "name": self.name,
                    "type": "binary",
                    "mimetype": mimetype,
                    "res_model": self.res_model,
                    "res_id": self.res_id,
                    "file_size": orphan.size,
                }
            )
        )
        # Link the existing object. Creating with store_fname set would make
        # fs_attachment rename the object in the bucket, so the link is written
        # afterwards; fs_storage_id is computed from it.
        attachment._force_write_store_fname(orphan.store_fname)
        orphan.write({"state": "assigned", "attachment_id": attachment.id})
        orphan.message_post(
            body=_("Assigned to %(model)s %(res_id)s by %(user)s.")
            % {
                "model": self.res_model,
                "res_id": self.res_id,
                "user": self.env.user.name,
            }
        )
        return {"type": "ir.actions.act_window_close"}
