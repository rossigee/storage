import logging
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class MinioWebhookEvent(models.Model):
    _name = "minio.webhook.event"
    _description = "MinIO Webhook Event"
    _order = "create_date DESC"

    event_type = fields.Char(string="Event Type", help="e.g. s3:ObjectCreated:Put")
    bucket = fields.Char(string="Bucket", help="MinIO bucket name")
    object_key = fields.Char(string="Object Key", help="MinIO object key (URL-encoded)")
    size = fields.Integer(string="Size (bytes)")
    content_type = fields.Char(string="Content Type")
    e_tag = fields.Char(string="E-Tag")
    status = fields.Selection(
        [
            ("received", "Received"),
            ("processed", "Processed"),
            ("failed", "Failed"),
            ("rejected", "Rejected"),
        ],
        string="Status",
        default="received",
        index=True,
    )
    attachment_id = fields.Many2one(
        "ir.attachment", string="Attachment", index=True, ondelete="set null"
    )
    job_uuid = fields.Char(string="Job UUID", index=True)
    detail = fields.Text(string="Detail")
    remote_addr = fields.Char(string="Remote Address")
    create_date = fields.Datetime(string="Received At", index=True)

    _sql_constraints = [
        (
            "object_key_bucket_uniq",
            "unique (bucket, object_key, create_date)",
            "Duplicate event for same bucket+key+time",
        ),
    ]

    @api.model
    def create_event(self, vals):
        return self.create(vals)

    def action_view_attachment(self):
        self.ensure_one()
        if not self.attachment_id:
            raise ValidationError(_("No attachment linked to this event."))
        return {
            "type": "ir.actions.act_window",
            "res_model": "ir.attachment",
            "res_id": self.attachment_id.id,
            "views": [(False, "form")],
        }

    def action_view_job(self):
        self.ensure_one()
        if not self.job_uuid:
            raise ValidationError(_("No job UUID linked to this event."))
        return {
            "type": "ir.actions.act_window",
            "res_model": "queue.job",
            "views": [(False, "form")],
            "domain": [("uuid", "=", self.job_uuid)],
        }

    def process_attachment(self, attachment_id):
        """Process the attachment associated with this event.

        This is the async job entry point called via with_delay().

        Args:
            attachment_id: ID of the ir.attachment record to process
        """
        attachment = self.env["ir.attachment"].browse(attachment_id)
        if not attachment.exists():
            _logger.warning(
                "process_attachment: attachment %s not found", attachment_id
            )
            return

        _logger.info(
            "process_attachment: processing attachment %s name=%s mimetype=%s",
            attachment.id,
            attachment.name,
            attachment.mimetype,
        )
        event = self.search(
            [("attachment_id", "=", attachment_id), ("status", "=", "received")],
            order="create_date DESC",
            limit=1,
        )
        if event:
            event.status = "processed"
        _logger.info(
            "process_attachment: attachment %s processed (stub)", attachment_id
        )
