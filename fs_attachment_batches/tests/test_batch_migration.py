import os
from unittest import mock

from odoo.addons.fs_attachment.tests.common import TestFSAttachmentCommon


class TestBatchMigration(TestFSAttachmentCommon):
    def test_force_storage_moves_only_selected_records(self):
        selected = self.ir_attachment_model.create(
            {"name": "selected.txt", "raw": b"one"}
        )
        other = self.ir_attachment_model.create({"name": "other.txt", "raw": b"two"})
        self.env.flush_all()
        self.temp_backend.use_as_default_for_attachments = True
        with mock.patch.object(self.env.cr, "commit"), mock.patch(
            "odoo.addons.fs_attachment_batches.models.ir_attachment.clean_fs"
        ) as clean_fs:
            selected.force_storage()
            clean_fs.assert_called_once()
        self.assertTrue(selected.store_fname.startswith("tmp_dir://"))
        self.assertFalse(other.store_fname.startswith("tmp_dir://"))
        self.assertEqual(os.listdir(self.temp_dir), [f"selected-{selected.id}-0.txt"])
