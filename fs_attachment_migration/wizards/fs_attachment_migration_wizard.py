from odoo import models, fields, api, _
from odoo.exceptions import AccessError, UserError
import logging

_logger = logging.getLogger(__name__)


class FSAttachmentMigrationWizard(models.TransientModel):
    _name = 'fs.attachment.migration.wizard'
    _description = 'Migrate Attachments to Object Storage'

    storage_id = fields.Many2one(
        'fs.storage',
        string='Target Storage',
        required=True,
        help='The filesystem storage to migrate attachments to'
    )

    pending_count = fields.Integer(
        string='Pending Attachments',
        readonly=True,
        help='Number of attachments that will be migrated'
    )

    migration_status = fields.Text(
        string='Status',
        readonly=True,
        help='Status of the migration process'
    )

    queue_job_id = fields.Many2one(
        'queue.job',
        string='Migration Job',
        readonly=True,
        help='The queued migration job'
    )

    @api.model
    def default_get(self, fields_list):
        """Compute default values including pending attachment count."""
        res = super().default_get(fields_list)

        # Default to the storage marked as default for attachments
        if 'storage_id' not in res or not res.get('storage_id'):
            default_storage = self.env['fs.storage'].search(
                [('use_as_default_for_attachments', '=', True)],
                limit=1
            )
            if default_storage:
                res['storage_id'] = default_storage.id

        # Compute pending count
        if 'pending_count' in fields_list and res.get('storage_id'):
            storage_id = res['storage_id']
            # Count attachments NOT yet stored in this storage and NOT in DB
            pending = self.env['ir.attachment'].search_count([
                ('fs_storage_id', '!=', storage_id),
                ('db_datas', '=', False),
            ])
            res['pending_count'] = pending

        return res

    def action_migrate(self):
        """Enqueue the attachment migration as a background job."""
        self.ensure_one()

        # Security check: admin only
        if not self.env.user.has_group('base.group_system'):
            raise AccessError(_('Only administrators can migrate attachments.'))

        if not self.storage_id:
            raise UserError(_('Please select a target storage.'))

        # Before migrating, re-affirm the storage config via ORM to ensure
        # the ormcache for get_default_storage_code_for_attachments is invalidated.
        # This is critical if this storage is marked as default, otherwise the
        # ORM's ormcache may still hold a stale result from before the config was set.
        _logger.info(
            'Affirming storage %s as default (forces ormcache invalidation)',
            self.storage_id.code
        )
        self.storage_id.write({
            'use_as_default_for_attachments': self.storage_id.use_as_default_for_attachments
        })

        # Also ensure ir_attachment.location fallback is set
        self.env['ir.config_parameter'].sudo().set_param(
            'ir_attachment.location',
            'file'  # Core Odoo fallback
        )
        _logger.info('Ensured ir_attachment.location fallback is set')

        # Enqueue the migration via queue_job
        description = _('Migrate attachments to %s') % self.storage_id.name
        _logger.info('Enqueuing migration: %s', description)

        try:
            job = self.env['ir.attachment'].sudo().with_delay(
                description=description
            ).force_storage()

            # Store reference to the job for UI feedback
            self.queue_job_id = job.id if hasattr(job, 'id') else None

            # Return action to show the queue job details
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'queue.job',
                'res_id': self.queue_job_id or job.id,
                'view_mode': 'form',
                'target': 'current',
            }
        except Exception as e:
            _logger.exception('Failed to enqueue migration: %s', str(e))
            raise UserError(
                _('Failed to enqueue migration: %s') % str(e)
            )
