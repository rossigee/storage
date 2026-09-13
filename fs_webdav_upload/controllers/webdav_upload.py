# WebDAV upload handler for bank statements
import base64
import logging
from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)

class WebDAVUploadController(http.Controller):

    @http.route('/upload/dav/<path:subpath>', type='http', auth='public', methods=['PUT', 'PROPFIND', 'MKCOL', 'OPTIONS'], csrf=False, priority=100)
    def handle_webdav_upload(self, subpath, **kwargs):
        """Handle WebDAV requests for bank statement uploads."""
        _logger.info(f"WebDAV {request.method} request: {subpath}")

        # Handle OPTIONS (pre-flight)
        if request.method == 'OPTIONS':
            return http.Response('', headers={
                'Allow': 'PUT, GET, HEAD, DELETE, PROPFIND, MKCOL, MOVE, COPY, OPTIONS',
                'DAV': '1,2',
            })

        # Handle PROPFIND (directory listing)
        if request.method == 'PROPFIND':
            return http.Response('', status=207, headers={'Content-Type': 'application/xml'})

        # Handle MKCOL (directory creation)
        if request.method == 'MKCOL':
            return http.Response('', status=201)

        # Handle PUT (file upload)
        if request.method == 'PUT':
            try:
                # Extract filename from path
                parts = subpath.rstrip('/').split('/')
                filename = parts[-1] if parts else 'upload.txt'

                # Read the file content
                file_data = request.httprequest.get_data()

                # Create attachment
                attachment = request.env['ir.attachment'].sudo().create({
                    'name': filename,
                    'datas': base64.b64encode(file_data),
                    'type': 'binary',
                    'res_model': 'ir.attachment',
                    'public': False,
                })

                _logger.info(f"WebDAV upload successful: {filename} (attachment id: {attachment.id})")
                return http.Response('', status=201, headers={
                    'Location': f'/attachment/{attachment.id}',
                })
            except Exception as e:
                _logger.error(f"WebDAV upload failed: {str(e)}")
                return http.Response(f'Upload failed: {str(e)}', status=500)

        return http.Response('Method not allowed', status=405)

    @http.route('/contact/submit', type='http', auth='public', methods=['POST'], csrf=False)
    def handle_contact_form(self, **post):
        """Handle contact form submission."""
        try:
            name = post.get('name', '').strip()
            email = post.get('email', '').strip()
            message = post.get('message', '').strip()

            if not all([name, email, message]):
                return http.Response('Missing required fields', status=400)

            # Send email via mail.mail
            mail_values = {
                'subject': f'New Contact Form Submission from {name}',
                'body_html': f'<p><strong>Name:</strong> {name}</p><p><strong>Email:</strong> {email}</p><p><strong>Message:</strong></p><p>{message.replace(chr(10), "<br/>")}</p>',
                'email_from': email,
                'email_to': request.env.user.company_id.email or 'contact@example.com',
            }
            request.env['mail.mail'].sudo().create(mail_values).send()

            _logger.info(f"Contact form submitted by {name} ({email})")
            return http.Response('<h1>Thank you!</h1><p>Your message has been sent successfully.</p>', status=200)
        except Exception as e:
            _logger.error(f"Contact form error: {str(e)}")
            return http.Response(f'Error: {str(e)}', status=500)
