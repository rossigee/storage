# WebDAV upload handler for bank statements
import base64
import logging
from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)

class WebDAVUploadController(http.Controller):

    @http.route('/upload/dav/<path:subpath>', type='http', auth='public', methods=['PUT', 'PROPFIND', 'MKCOL', 'OPTIONS'], csrf=False)
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
