# Copyright 2025 Ross Golder
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

{
    "name": "FS Storage MinIO",
    "summary": """MinIO filesystem backend for fs_storage using the official minio SDK""",
    "version": "17.0.1.0.0",
    "license": "LGPL-3",
    "author": "Ross Golder",
    "website": "https://github.com/OCA/storage",
    "depends": ["fs_storage"],
    "external_dependencies": {
        "python": ["minio"],
    },
    "installable": True,
}
