{
    'name': 'FS Attachment Migration Wizard',
    'description': 'Admin wizard to migrate file-based attachments to configured object storage (Minio, S3, etc.)',
    'version': '17.0.1.0.0',
    'category': 'Technical',
    'depends': ['fs_attachment', 'fs_storage', 'queue_job'],
    'data': [
        'security/ir.model.access.csv',
        'wizards/fs_attachment_migration_wizard_views.xml',
    ],
    'auto_install': False,
    'application': False,
}
