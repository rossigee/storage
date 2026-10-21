{
    "name": "FS Attachment Migration Wizard",
    "author": "Odoo Community Association (OCA), Golder",
    "version": "17.0.1.0.1",
    "category": "Technical",
    "depends": ["fs_attachment", "fs_storage", "queue_job"],
    "data": [
        "security/ir.model.access.csv",
        "wizards/fs_attachment_migration_wizard_views.xml",
    ],
    "auto_install": False,
    "application": False,
    "website": "https://github.com/OCA/storage",
    "license": "AGPL-3",
}
