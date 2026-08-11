import json
import logging
import os
from urllib.parse import unquote

import hmac
import hashlib

from odoo import http
from odoo.http import request



_logger = logging.getLogger(__name__)


class MinioWebhookController(http.Controller):
    @staticmethod
    def _get_config(key, default=""):
        return (
            request.env["ir.config_parameter"]
            .sudo()
            .get_param(f"minio_webhook.{key}", default)
        )

    @staticmethod
    def _allowed_ips():
        raw = MinioWebhookController._get_config("allowed_ips", "")
        if not raw:
            return set()
        return {ip.strip() for ip in raw.split(",") if ip.strip()}

    @staticmethod
    def _secret():
        return MinioWebhookController._get_config("secret", "")

    @staticmethod
    def _minio_config():
        return {
            "endpoint": MinioWebhookController._get_config("minio_endpoint", "minio.golder.lan"),
            "access_key": MinioWebhookController._get_config("minio_access_key", ""),
            "secret_key": MinioWebhookController._get_config("minio_secret_key", ""),
            "secure": MinioWebhookController._get_config("minio_secure", "true").lower()
            in ("true", "1", "yes"),
            "bucket": MinioWebhookController._get_config("minio_bucket", "document-scans"),
        }

    def _validate_ip(self):
        remote_addr = request.httprequest.remote_addr
        if not remote_addr:
            _logger.warning("minio_webhook: no remote_addr")
            return False
        allowed = self._allowed_ips()
        if not allowed:
            _logger.warning("minio_webhook: no allowed_ips configured, rejecting all")
            return False
        if remote_addr not in allowed:
            _logger.warning(
                "minio_webhook: rejected IP %s (allowed: %s)",
                remote_addr,
                allowed,
            )
            return False
        return True

    def _validate_signature(self, payload_bytes):
        secret = self._secret()
        if not secret:
            return True
        received_sig = request.httprequest.headers.get("X-Webhook-Signature", "")
        if not received_sig:
            _logger.warning("minio_webhook: missing signature header")
            return False
        timestamp = request.httprequest.headers.get("X-Webhook-Timestamp", "")
        signed_payload = (
            f"{timestamp}{payload_bytes.decode('utf-8')}" if timestamp else payload_bytes.decode("utf-8")
        )
        expected = hmac.new(
            secret.encode("utf-8"),
            signed_payload.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(received_sig, expected):
            _logger.warning("minio_webhook: invalid signature")
            return False
        return True

    def _log_event(self, event_type, bucket, object_key, status, detail="", attachment_id=None, job_uuid=None):
        try:
            request.env["minio.webhook.event"].sudo().create(
                {
                    "event_type": event_type,
                    "bucket": bucket,
                    "object_key": object_key,
                    "status": status,
                    "detail": detail,
                    "remote_addr": request.httprequest.remote_addr or "unknown",
                    "attachment_id": attachment_id,
                    "job_id": job_id,
                    "job_uuid": job_uuid,
                }
            )
        except Exception as e:
            _logger.error("minio_webhook: failed to log event: %s", e)

    def _create_attachment(self, bucket, object_key, data, content_type):
        name = os.path.basename(unquote(object_key))
        if not name:
            name = "upload"
        if "/" in object_key:
            name = object_key.split("/")[-1]
        vals = {
            "name": name,
            "type": "binary",
            "mimetype": content_type or "application/octet-stream",
            "raw": data,
            "description": f"Uploaded from MinIO bucket '{bucket}' key '{object_key}'",
        }
        attachment = request.env["ir.attachment"].sudo().create(vals)
        _logger.info(
            "minio_webhook: created attachment %s name=%s bucket=%s key=%s",
            attachment.id,
            name,
            bucket,
            object_key,
        )
        return attachment

    def _enqueue_processing(self, attachment_id):
        job = (
            request.env["minio.webhook.event"]
            .sudo()
            .with_delay(channel="root")
            .process_attachment(attachment_id)
        )
        job_uuid = getattr(job, "uuid", str(job))
        _logger.info(
            "minio_webhook: enqueued process_attachment job %s for attachment %s",
            job_uuid,
            attachment_id,
        )
        return job_uuid

    @http.route(
        "/webhook/attachment/upload",
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
    )
    def receive_upload(self):
        raw_body = request.httprequest.data

        if not self._validate_ip():
            self._log_event(
                event_type="request",
                bucket="",
                object_key="",
                status="rejected",
                detail=f"IP not allowed: {request.httprequest.remote_addr}",
            )
            return request.make_response(
                json.dumps({"error": "IP not allowed"}),
                status=403,
                headers=[("Content-Type", "application/json")],
            )

        if not self._validate_signature(raw_body):
            self._log_event(
                event_type="auth",
                bucket="",
                object_key="",
                status="rejected",
                detail="Invalid signature",
            )
            return request.make_response(
                json.dumps({"error": "Invalid signature"}),
                status=401,
                headers=[("Content-Type", "application/json")],
            )

        try:
            payload = json.loads(raw_body)
        except Exception as e:
            _logger.warning("minio_webhook: failed to parse JSON: %s", e)
            self._log_event(
                event_type="parse",
                bucket="",
                object_key="",
                status="rejected",
                detail=f"Invalid JSON: {e}",
            )
            return request.make_response(
                json.dumps({"error": "Invalid JSON"}),
                status=400,
                headers=[("Content-Type", "application/json")],
            )

        if payload.get("Event") == "s3:TestEvent":
            _logger.info("minio_webhook: test notification received")
            self._log_event(
                event_type="s3:TestEvent",
                bucket=payload.get("Bucket", ""),
                object_key="",
                status="processed",
                detail=json.dumps(payload),
            )
            return request.make_response(
                json.dumps({"status": "ok", "event": "test"}),
                headers=[("Content-Type", "application/json")],
            )

        records = payload.get("Records", [])
        if not records:
            _logger.info("minio_webhook: no records in payload")
            return request.make_response(
                json.dumps({"status": "ok", "processed": 0}),
                headers=[("Content-Type", "application/json")],
            )

        mc_config = self._minio_config()
        mc_endpoint = mc_config["endpoint"]
        mc_access_key = mc_config["access_key"]
        mc_secret_key = mc_config["secret_key"]
        mc_secure = mc_config["secure"]
        mc_bucket = mc_config["bucket"]

        try:
            from minio import Minio

            mc = Minio(
                mc_endpoint,
                access_key=mc_access_key,
                secret_key=mc_secret_key,
                secure=mc_secure,
            )
        except Exception as e:
            _logger.error("minio_webhook: failed to create MinIO client: %s", e)
            self._log_event(
                event_type="config",
                bucket=mc_bucket,
                object_key="",
                status="failed",
                detail=f"MinIO client init failed: {e}",
            )
            return request.make_response(
                json.dumps({"error": "Internal server error"}),
                status=500,
                headers=[("Content-Type", "application/json")],
            )

        processed = 0
        for record in records:
            event_name = record.get("eventName", "")
            s3_info = record.get("s3", {})
            bucket_name = s3_info.get("bucket", {}).get("name", "")
            object_info = s3_info.get("object", {})
            object_key = unquote(object_info.get("key", ""))
            size = object_info.get("size", 0)
            content_type = object_info.get("contentType", "")
            e_tag = object_info.get("eTag", "")

            _logger.info(
                "minio_webhook: event=%s bucket=%s key=%s size=%s",
                event_name,
                bucket_name,
                object_key,
                size,
            )

            if not object_key:
                continue

            if bucket_name != mc_bucket:
                _logger.debug(
                    "minio_webhook: skipping bucket %s (expected %s)",
                    bucket_name,
                    mc_bucket,
                )
                continue

            if not event_name.startswith("s3:ObjectCreated:"):
                _logger.debug(
                    "minio_webhook: skipping non-create event %s",
                    event_name,
                )
                continue

            try:
                data = mc.get_object(mc_bucket, object_key)
                file_bytes = data.read()
                data.close()
            except Exception as e:
                _logger.error(
                    "minio_webhook: failed to fetch %s/%s: %s",
                    bucket_name,
                    object_key,
                    e,
                )
                self._log_event(
                    event_type=event_name,
                    bucket=bucket_name,
                    object_key=object_key,
                    status="failed",
                    detail=f"Failed to fetch from MinIO: {e}",
                )
                continue

            try:
                attachment = self._create_attachment(
                    bucket_name, object_key, file_bytes, content_type
                )
                job_uuid = self._enqueue_processing(attachment.id)
                self._log_event(
                    event_type=event_name,
                    bucket=bucket_name,
                    object_key=object_key,
                    status="received",
                    attachment_id=attachment.id,
                    job_uuid=job_uuid,
                    detail=f"size={size} etag={e_tag}",
                )
                processed += 1
            except Exception as e:
                _logger.error(
                    "minio_webhook: failed to create attachment for %s/%s: %s",
                    bucket_name,
                    object_key,
                    e,
                )
                self._log_event(
                    event_type=event_name,
                    bucket=bucket_name,
                    object_key=object_key,
                    status="failed",
                    detail=f"Attachment creation failed: {e}",
                )
                continue

        _logger.info("minio_webhook: processed %s objects", processed)
        return request.make_response(
            json.dumps({"status": "ok", "processed": processed}),
            headers=[("Content-Type", "application/json")],
        )

    @http.route(
        "/webhook/attachment/upload/test",
        type="http",
        auth="public",
        methods=["GET"],
        csrf=False,
    )
    def test(self):
        return request.make_response(
            json.dumps(
                {
                    "status": "ok",
                    "endpoint": "/webhook/attachment/upload",
                    "minio_bucket": self._minio_config()["bucket"],
                    "allowed_ips": list(self._allowed_ips()),
                    "has_secret": bool(self._secret()),
                }
            ),
            headers=[("Content-Type", "application/json")],
        )
