# Copyright 2025 Ross Golder
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo.tests.common import TransactionCase

from odoo.addons.base.tests.common import DISABLED_MAIL_CONTEXT


class TestFSAttachmentMinioCommon(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, **DISABLED_MAIL_CONTEXT))
        cls.minio_backend_config = {
            "name": "MinIO Storage",
            "protocol": "minio",
            "code": "miniotst",
            "directory_path": "test-bucket",
            "json_options": {
                "endpoint": "localhost:9000",
                "access_key": "minio-key",
                "secret_key": "minio-secret",
                "secure": False,
                "region": "us-east-1",
            },
            "base_url": False,  # MinIO does not use base_url for x-sendfile
        }
        cls.minio_backend = cls.env["fs.storage"].create(cls.minio_backend_config)
        cls.ir_attachment_model = cls.env["ir.attachment"]

        cls.fake_attachment_minio = cls.env["ir.attachment"].create(
            {
                "name": "fake_minio_file.txt",
                "fs_storage_id": cls.minio_backend.id,
            }
        )
        cls.fake_attachment_minio.flush_recordset()
        # Update the attachment in database since we don't have a real MinIO bucket
        cls.env.cr.execute(
            """
                UPDATE
                    ir_attachment
                SET
                    store_fname = 'miniotst://dir/sub/fake_minio_file.txt',
                    fs_filename = 'fake_minio_file.txt',
                    fs_storage_code = 'miniotst',
                    checksum = 234,
                    file_size = 1234,
                    fs_storage_id = %s
                WHERE
                    id = %s
            """,
            (cls.minio_backend.id, cls.fake_attachment_minio.id),
        )
        cls.fake_attachment_minio.invalidate_recordset()

    def setUp(self):
        super().setUp()
        # Enforce backend_config fields since they may be reset on savepoint rollback
        self.minio_backend.write(self.minio_backend_config)
