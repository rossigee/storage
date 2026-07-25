from odoo import models, _


class FSStorage(models.Model):
    _inherit = 'fs.storage'

    def action_open_migration_wizard(self):
        """Open the migration wizard with this storage pre-selected."""
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'fs.attachment.migration.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_storage_id': self.id,
            },
        }
