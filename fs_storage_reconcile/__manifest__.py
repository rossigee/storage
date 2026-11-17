# Copyright 2026 Ross Golder
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

{
    "name": "FS Storage Reconcile",
    "summary": "Storage usage and unassigned-object reconciliation for fs_attachment",
    "version": "17.0.1.0.0",
    "category": "Tools",
    "author": "Ross Golder,Odoo Community Association (OCA)",
    "website": "https://github.com/OCA/storage",
    "license": "LGPL-3",
    "depends": ["fs_attachment", "queue_job", "mail"],
    "data": [
        "security/security.xml",
        "security/ir.model.access.csv",
        "wizards/fs_storage_orphan_assign_views.xml",
        "views/fs_storage_orphan_views.xml",
        "views/fs_storage_views.xml",
    ],
    "installable": True,
    "application": False,
}
