{
    "name": "FS Attachment Migration Wizard",
    "summary": "Migrate file-based attachments to object storage (Minio, S3)",
    "version": "17.0.1.0.1",
    "category": "Technical",
    "author": "Ross Golder,Odoo Community Association (OCA)",
    "website": "https://github.com/OCA/storage",
    "depends": ["fs_attachment", "fs_storage", "queue_job"],
    "data": [
        "security/ir.model.access.csv",
        "wizards/fs_attachment_migration_wizard_views.xml",
    ],
    "auto_install": False,
    "application": False,
    "license": "AGPL-3",
}
