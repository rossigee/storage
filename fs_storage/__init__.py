# register protocols first
from . import odoo_file_system
from . import rooted_dir_file_system

# Eagerly register minio protocol if the package is available.
# fs_storage_minio depends on fs_storage, so it loads after us.
# Without this, _get_protocols() won't include 'minio' during -u all,
# causing server.env.mixin to fail when writing 'minio' into the
# x_protocol_env_default sparse Selection field.
try:
    from fs_storage_minio import minio_file_system  # noqa: F401
except ImportError:
    pass

# then add normal imports
from . import models
from . import wizards
