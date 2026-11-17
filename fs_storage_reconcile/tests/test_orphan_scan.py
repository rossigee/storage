# Copyright 2026 Ross Golder
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

from unittest.mock import PropertyMock, patch

from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, tagged


class FakeFs:
    """Stands in for the rooted fsspec filesystem: find() returns a fixed listing."""

    def __init__(self, listing):
        self.listing = listing

    def find(self, path, detail=False, **kwargs):
        return dict(self.listing)


@tagged("post_install", "-at_install")
class TestOrphanScan(TransactionCase):
    def setUp(self):
        super().setUp()
        self.storage = self.env["fs.storage"].create(
            {"name": "Reconcile Test", "code": "reconcile-test", "protocol": "odoofs"}
        )
        self.Attachment = self.env["ir.attachment"].sudo()
        self.Orphan = self.env["fs.storage.orphan"]

    def _attachment(self, path):
        # store_fname cannot be set on create (fs_attachment would rename the
        # object in the bucket), so it is written afterwards, as the wizard does.
        attachment = self.Attachment.create(
            {"name": path.rsplit("/", 1)[-1], "type": "binary", "file_size": 1}
        )
        attachment._force_write_store_fname(f"reconcile-test://{path}")
        return attachment

    def _reconcile(self, listing):
        self.Orphan._reconcile(self.storage, FakeFs(listing))

    def test_unattached_objects_become_orphans(self):
        self._attachment("known/a.pdf")
        self._reconcile(
            {
                "known/a.pdf": {"type": "file", "size": 10},
                "orphan/b.pdf": {"type": "file", "size": 20},
                "orphan": {"type": "directory", "size": 0},
            }
        )
        orphans = self.Orphan.search([("storage_id", "=", self.storage.id)])
        self.assertEqual(orphans.mapped("path"), ["orphan/b.pdf"])
        self.assertEqual(orphans.size, 20)
        self.assertEqual(orphans.state, "new")
        self.assertEqual(orphans.store_fname, "reconcile-test://orphan/b.pdf")

    def test_missing_objects_are_flagged_and_cleared(self):
        attachment = self._attachment("gone/c.pdf")
        self._reconcile({})
        self.assertTrue(attachment.is_missing)
        self._reconcile({"gone/c.pdf": {"type": "file", "size": 5}})
        self.assertFalse(attachment.is_missing)

    def test_unacted_orphans_disappear_with_their_object(self):
        self._reconcile({"stale/d.pdf": {"type": "file", "size": 3}})
        self._reconcile({})
        self.assertFalse(self.Orphan.search([("storage_id", "=", self.storage.id)]))

    def test_ignored_orphans_are_kept_when_their_object_goes(self):
        self._reconcile({"kept/e.pdf": {"type": "file", "size": 3}})
        orphan = self.Orphan.search([("path", "=", "kept/e.pdf")])
        orphan.action_ignore()
        self._reconcile({})
        self.assertEqual(orphan.state, "ignored")
        self.assertTrue(orphan.exists())

    def test_assign_links_existing_object_without_reupload(self):
        self._reconcile({"loose/f.pdf": {"type": "file", "size": 42}})
        orphan = self.Orphan.search([("path", "=", "loose/f.pdf")])
        partner = self.env["res.partner"].create({"name": "Assign Target"})
        wizard = self.env["fs.storage.orphan.assign"].create(
            {
                "orphan_id": orphan.id,
                "name": "f.pdf",
                "res_model": "res.partner",
                "res_id": partner.id,
            }
        )
        wizard.action_assign()
        self.assertEqual(orphan.state, "assigned")
        attachment = orphan.attachment_id
        self.assertEqual(attachment.store_fname, "reconcile-test://loose/f.pdf")
        self.assertEqual(attachment.fs_storage_id, self.storage)
        self.assertEqual(
            (attachment.res_model, attachment.res_id), ("res.partner", partner.id)
        )
        # Once assigned, the object is no longer an orphan on the next scan
        self._reconcile({"loose/f.pdf": {"type": "file", "size": 42}})
        self.assertEqual(orphan.state, "assigned")

    def test_assign_to_unknown_model_is_refused(self):
        self._reconcile({"x/g.pdf": {"type": "file", "size": 1}})
        orphan = self.Orphan.search([("path", "=", "x/g.pdf")])
        wizard = self.env["fs.storage.orphan.assign"].create(
            {
                "orphan_id": orphan.id,
                "name": "g.pdf",
                "res_model": "no.such.model",
                "res_id": 1,
            }
        )
        with self.assertRaises(UserError):
            wizard.action_assign()
        self.assertEqual(orphan.state, "new")

    def test_delete_from_bucket_is_admin_only(self):
        self._reconcile({"del/h.pdf": {"type": "file", "size": 1}})
        orphan = self.Orphan.search([("path", "=", "del/h.pdf")])
        operator = self.env["res.users"].create(
            {
                "name": "Storage Operator",
                "login": "reconcile_operator",
                "groups_id": [
                    (
                        6,
                        0,
                        [
                            self.env.ref(
                                "fs_storage_reconcile.group_storage_operator"
                            ).id
                        ],
                    )
                ],
            }
        )
        with self.assertRaises(AccessError):
            orphan.with_user(operator).action_delete_from_bucket()
        self.assertEqual(orphan.state, "new")

    def test_scan_job_reads_the_storage_filesystem(self):
        with patch.object(
            type(self.storage),
            "fs",
            new_callable=PropertyMock,
            return_value=FakeFs({"job/i.pdf": {"type": "file", "size": 9}}),
        ):
            self.storage.run_orphan_scan()
        self.assertTrue(self.storage.last_orphan_scan)
        self.assertEqual(self.storage.orphan_count, 1)
