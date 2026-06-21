# Copyright 2025 Ross Golder <ross@golder.org>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

{
    "name": "Fs Attachment MinIO",
    "summary": """Store attachments into MinIO compliant filesystem""",
    "version": "16.0.1.0.0",
    "license": "AGPL-3",
    "author": "Ross Golder,Odoo Community Association (OCA)",
    "website": "https://github.com/OCA/storage",
    "depends": ["fs_attachment"],
    "external_dependencies": {
        "python": [
            "minio",
        ],
    },
    "data": [
        "views/fs_storage.xml",
    ],
    "installable": True,
}