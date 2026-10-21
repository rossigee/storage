{
    "name": "MinIO Webhook Ingest",
    "version": "17.0.1.0.0",
    "category": "Tools",
    "summary": "Receive MinIO bucket notifications and ingest files as attachments",
    "author": "Ross Golder,Odoo Community Association (OCA)",
    "website": "https://github.com/OCA/storage",
    "license": "LGPL-3",
    "depends": [
        "base",
        "queue_job",
    ],
    "external_dependencies": {
        "python": [
            "minio",
        ],
    },
    "data": [
        "security/ir.model.access.csv",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
