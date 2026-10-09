{
    "name": "MinIO Webhook Ingest",
    "version": "1.0.0",
    "category": "Tools",
    "summary": "Receive MinIO bucket notifications and ingest uploaded files as attachments",
    "description": """
MinIO Webhook Ingest
====================

Receives MinIO S3-compatible bucket notifications (webhook) when files are
uploaded to a designated bucket (document-scans). For each uploaded file:

1. Fetches the object from MinIO
2. Creates an ir.attachment record
3. Enqueues a queue_job for async processing

Configuration (via ir.config_parameter):
- minio_webhook.allowed_ips: comma-separated list of allowed source IPs
- minio_webhook.secret: optional HMAC-SHA256 secret for signature validation
- minio_webhook.minio_endpoint: MinIO server endpoint (default: minio.golder.lan)
- minio_webhook.minio_access_key: MinIO access key
- minio_webhook.minio_secret_key: MinIO secret key
- minio_webhook.minio_secure: use HTTPS (default: true)
- minio_webhook.minio_bucket: bucket name (default: document-scans)
    """,
    "author": "Golder Associates",
    "website": "",
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
