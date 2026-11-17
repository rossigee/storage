import logging

import psycopg2

from odoo import api, models

from odoo.addons.fs_attachment.models.ir_attachment import clean_fs

_logger = logging.getLogger(__name__)


class IrAttachment(models.Model):
    _inherit = "ir.attachment"

    @api.model
    def _force_storage_to_object_storage(self, new_cr=False):
        """Move attachments to object storage, restricted to ``self`` when given.

        Without records this is the upstream behaviour: every attachment in
        the storage is migrated. With records, only the selected ones are.
        The body follows upstream fs_attachment; keep it in sync when
        upgrading fs_attachment.
        """
        if not self:
            return super()._force_storage_to_object_storage(new_cr=new_cr)
        _logger.info("migrating selected files to the object storage")
        storage = self.env.context.get("storage_location") or self._storage()
        if self._is_storage_disabled(storage):
            return
        # The weird "res_field = False OR res_field != False" domain
        # is required! It's because of an override of _search in ir.attachment
        # which adds ('res_field', '=', False) when the domain does not
        # contain 'res_field'.
        domain = [
            "!",
            ("store_fname", "=like", f"{storage}://%"),
            "|",
            ("res_field", "=", False),
            ("res_field", "!=", False),
        ]
        with self._do_in_new_env(new_cr=new_cr) as new_env:
            model_env = new_env["ir.attachment"]
            ids = model_env.search(domain + [("id", "in", self.ids)]).ids
            files_to_clean = []
            for attachment_id in ids:
                try:
                    with new_env.cr.savepoint():
                        # check that no other transaction has
                        # locked the row, don't send a file to storage
                        # in that case
                        self.env.cr.execute(
                            "SELECT id "
                            "FROM ir_attachment "
                            "WHERE id = %s "
                            "FOR UPDATE NOWAIT",
                            (attachment_id,),
                            log_exceptions=False,
                        )
                        # Clear the cache so the 'datas' function fields are
                        # not computed for every attachment on each iteration.
                        new_env.clear()
                        attachment = model_env.browse(attachment_id)
                        path = attachment._move_attachment_to_store()
                        if path:
                            files_to_clean.append(path)
                except psycopg2.OperationalError:
                    _logger.error(
                        "Could not migrate attachment %s to object storage",
                        attachment_id,
                    )

            # delete the files from the filesystem once we know the changes
            # have been committed in ir.attachment
            if files_to_clean:
                new_env.cr.commit()
                clean_fs(files_to_clean)
