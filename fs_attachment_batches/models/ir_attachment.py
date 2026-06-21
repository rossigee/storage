import os
import psycopg2

from odoo import models, api

import logging
_logger = logging.getLogger(__name__)


def clean_fs(files):
    _logger.info("cleaning old files from filestore")
    for full_path in files:
        if os.path.exists(full_path):
            try:
                os.unlink(full_path)
            except OSError:
                _logger.info(
                    "_file_delete could not unlink %s", full_path, exc_info=True
                )
            except IOError:
                # Harmless and needed for race conditions
                _logger.info(
                    "_file_delete could not unlink %s", full_path, exc_info=True
                )


class IrAttachment(models.Model):
    _inherit = 'ir.attachment'

    @api.model
    def _force_storage_to_object_storage(self, new_cr=False):
        _logger.info("migrating files to the object storage")
        storage = self.env.context.get("storage_location") or self._storage()
        _logger.info(f"found storage: {storage}")
        if self._is_storage_disabled(storage):
            return
        # The weird "res_field = False OR res_field != False" domain
        # is required! It's because of an override of _search in ir.attachment
        # which adds ('res_field', '=', False) when the domain does not
        # contain 'res_field'.
        # https://github.com/odoo/odoo/blob/9032617120138848c63b3cfa5d1913c5e5ad76db/
        # odoo/addons/base/ir/ir_attachment.py#L344-L347
        domain = [
            "!",
            ("store_fname", "=like", "{}://%".format(storage)),
            "|",
            ("res_field", "=", False),
            ("res_field", "!=", False),
        ]
        # We do a copy of the environment so we can workaround the cache issue
        # below. We do not create a new cursor by default because it causes
        # serialization issues due to concurrent updates on attachments during
        # the installation
        with self._do_in_new_env(new_cr=new_cr) as new_env:
            model_env = new_env["ir.attachment"]
            ids = model_env.search(domain).ids
            files_to_clean = []

            # Get the IDs of the selected records from the context
            ids = self.env.context.get('active_ids', [])
            if not ids:
                _logger.error("No active ids found.")
                return

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

                        # This is a trick to avoid having the 'datas'
                        # function fields computed for every attachment on
                        # each iteration of the loop. The former issue
                        # being that it reads the content of the file of
                        # ALL the attachments on each loop.
                        new_env.clear()
                        attachment = model_env.browse(attachment_id)
                        path = attachment._move_attachment_to_store()
                        if path:
                            files_to_clean.append(path)
                except psycopg2.OperationalError:
                    _logger.error(
                        "Could not migrate attachment %s to S3", attachment_id
                    )

            # delete the files from the filesystem once we know the changes
            # have been committed in ir.attachment
            if files_to_clean:
                new_env.cr.commit()
                clean_fs(files_to_clean)