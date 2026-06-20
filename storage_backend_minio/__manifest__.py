# Copyright 2025 Ross Golder <ross@golder.org>
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

{
    "name": "Storage Backend MinIO",
    "summary": "MinIO storage backend using the minio Python library",
    "version": "16.0.1.0.0",
    "license": "LGPL-3",
    "author": "Ross Golder,Odoo Community Association (OCA)",
    "website": "https://github.com/OCA/storage",
    "depends": [
        "storage_backend",
    ],
    "external_dependencies": {
        "python": [
            "minio",
        ],
    },
    "installable": True,
}