import logging
from odoo import SUPERUSER_ID

_logger = logging.getLogger(__name__)


def process_document_scan(session, attachment_id):
    """Generic hook for post-upload document scan processing.

    This job is called after a file is uploaded to MinIO and a corresponding
    ir.attachment record has been created. The actual processing logic
    (OCR, categorization, parsing, etc.) should be implemented here.

    Args:
        session: Odoo session (queue_job convention)
        attachment_id: ID of the ir.attachment record to process
    """
    env = session.env
    attachment = env["ir.attachment"].browse(attachment_id)
    if not attachment.exists():
        _logger.warning("process_document_scan: attachment %s not found", attachment_id)
        return

    _logger.info(
        "process_document_scan: processing attachment %s name=%s mimetype=%s",
        attachment_id,
        attachment.name,
        attachment.mimetype,
    )
    # TODO: implement actual processing (OCR, categorization, etc.)
    # For now this is a stub that logs and marks the event as processed
    event = env["minio.webhook.event"].search(
        [("attachment_id", "=", attachment_id), ("status", "=", "received")],
        order="create_date DESC",
        limit=1,
    )
    if event:
        event.status = "processed"
    _logger.info("process_document_scan: attachment %s processed (stub)", attachment_id)
