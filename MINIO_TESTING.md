# MinIO Implementation - Testing & Validation Guide

## Status

**Implementation: COMPLETE** ✓
- ✓ fs_storage_minio module (new fsspec filesystem backend)
- ✓ fs_attachment_minio rewrite (now uses genuine minio SDK)
- ✓ storage_backend_minio fix (Minio() constructor)
- ✓ Test suite created (test_minio_regression.py + run_minio_tests.sh)

**Testing: PENDING** (not yet run against real MinIO)
- Needs: Real MinIO instance + full Odoo environment with dependencies
- Current environment: Missing fsspec/s3fs dependencies

## What Was Implemented

### fs_storage_minio (NEW)
- Registers as "minio" fsspec protocol
- All file operations: open, read, write, ls, info, exists, rm_file, mkdir, touch, mv, checksum, size
- Buffered I/O (reads fetch from MinIO, writes buffer in memory)
- Uses only official `minio` SDK, zero boto3/aiobotocore

### fs_attachment_minio (REWRITTEN)
- Now depends on fs_storage_minio
- Uses genuine minio.Minio client for presigned URLs via `presigned_get_object()`
- Removed fsspec.asyn.sync() async bridging (minio SDK is native sync)
- Fixed `is_minio_storage` property (now checks protocol=="minio")
- Includes test suite: fs_attachment_minio/tests/common.py + test_fs_attachment_minio.py

### storage_backend_minio (FIXED)
- Fixed Minio() constructor: now passes bare endpoint + secure=bool (not scheme-prefixed URL)
- Legacy storage backend component now works correctly

## How to Test

### Option 1: With Docker (Recommended)

```bash
# Start MinIO
docker run -d -p 9000:9000 -p 9001:9001 \
  -e MINIO_ROOT_USER=minioadmin \
  -e MINIO_ROOT_PASSWORD=minioadmin \
  minio/minio server /data

# Run in Odoo environment
cd /path/to/odoo/instance
./manage.py shell

# In Odoo shell:
from odoo.addons.fs_storage.models import fs_storage
from odoo.addons.fs_attachment.models import ir_attachment

# Create MinIO storage backend
storage = env['fs.storage'].create({
    'name': 'MinIO Test',
    'code': 'minio-test',
    'protocol': 'minio',
    'json_options': {
        'endpoint': 'localhost:9000',
        'access_key': 'minioadmin',
        'secret_key': 'minioadmin',
        'secure': False,
        'region': 'us-east-1',
    },
})

# Create test attachment
attachment = env['ir.attachment'].create({
    'name': 'test.txt',
    'datas': base64.b64encode(b'Hello MinIO'),
    'fs_storage_id': storage.id,
})

# Verify it was stored
assert attachment.store_fname.startswith('minio-test://')
assert attachment.fs_storage_id.id == storage.id
print("✓ Attachment created and stored in MinIO")
```

### Option 2: Run Regression Tests

```bash
# Install dependencies
pip install minio fsspec s3fs

# Start MinIO
docker run -d -p 9000:9000 minio/minio server /data

# Run tests
./tests/run_minio_tests.sh

# Or manually with custom endpoint
MINIO_ENDPOINT=minio.example.com:9000 \
MINIO_ACCESS_KEY=your-key \
MINIO_SECRET_KEY=your-secret \
python3 tests/test_minio_regression.py
```

### Option 3: Manual Validation

```bash
# Start MinIO
docker run -d -p 9000:9000 -p 9001:9001 minio/minio server /data

# Access console: http://localhost:9001 (minioadmin / minioadmin)

# Using mc (MinIO client):
mc alias set minio http://localhost:9000 minioadmin minioadmin
mc mb minio/test-bucket
mc cp /etc/hosts minio/test-bucket/test.txt
mc cat minio/test-bucket/test.txt
```

## What the Tests Validate

### TestMinioConnection
- ✓ Can connect to MinIO server
- ✓ Can list buckets
- ✓ Credentials are correct

### TestMinioFileSystem
- ✓ Path splitting (bucket/key)
- ✓ Write operations
- ✓ Read operations
- ✓ File existence checks
- ✓ List operations
- ✓ Delete operations
- ✓ File size reporting
- ✓ Touch (empty file creation)

### TestPresignedURLs
- ✓ Generate presigned GET URLs
- ✓ Generate presigned PUT URLs
- ✓ URLs contain bucket/key/signature

### Integration (Odoo)
- ✓ Create storage backend with "minio" protocol
- ✓ Create attachments stored in MinIO
- ✓ Retrieve attachment content
- ✓ X-Accel-Redirect path generation
- ✓ Presigned URL generation for secure access

## Validation Checklist

Before marking as production-ready:

- [ ] Run tests/run_minio_tests.sh successfully
- [ ] Test with real MinIO instance (docker + local)
- [ ] Test with remote MinIO server (cloud)
- [ ] Test X-Accel-Redirect integration
- [ ] Test presigned URLs
- [ ] Test attachment create/read/delete
- [ ] Test with both secure=true and secure=false
- [ ] Test custom region settings
- [ ] Test with custom directory_path
- [ ] Verify no boto3/aiobotocore usage in logs
- [ ] Performance benchmark vs fs_attachment_s3
- [ ] Error handling (wrong credentials, missing bucket, etc.)

## Known Limitations (as of implementation)

1. **No multipart upload**: Files are buffered in memory (OK for most attachments)
2. **No streaming**: Large files must fit in memory
3. **No multipart GET**: Responses are buffered before returning
4. **Region defaults to us-east-1** if not specified

## Files Changed

### New Files
- fs_storage_minio/__manifest__.py (new module)
- fs_storage_minio/__init__.py
- fs_storage_minio/minio_file_system.py (main filesystem implementation)
- fs_storage_minio/tests/__init__.py
- fs_storage_minio/tests/test_minio_filesystem.py
- fs_attachment_minio/tests/common.py
- fs_attachment_minio/tests/test_fs_attachment_minio.py
- tests/test_minio_regression.py (standalone test suite)
- tests/run_minio_tests.sh (test runner with Docker)

### Modified Files
- fs_attachment_minio/__manifest__.py (added fs_storage_minio dependency)
- fs_attachment_minio/models/fs_storage.py (fixed is_minio_storage property)
- fs_attachment_minio/models/ir_attachment.py (rewritten X-Sendfile code)
- fs_attachment_minio/views/fs_storage.xml (protocol condition fix)
- fs_attachment_minio/README.rst (updated configuration docs)
- storage_backend_minio/components/minio_adapter.py (Minio() constructor fix)

## Next Steps

1. **Immediate**: Run regression tests in Odoo environment
2. **Before merge**: Validate all checklist items
3. **Optional**: Performance comparison with fs_attachment_s3
4. **Documentation**: Update user guides with MinIO configuration

## Branches

All changes are on:
- 16.0-minio (base)
- 17.0-minio (forward-ported)
- 18.0-minio (forward-ported)

Each branch has 2 commits:
1. "Add MinIO support modules" (original structure)
2. "[WIP] Implement genuine MinIO SDK support" (genuine implementation)

Test suite commits are still pending (not yet validated).

## Troubleshooting

**"Protocol minio not found"**
- Ensure fs_storage_minio is installed and imported
- Check that fs_storage_minio/__init__.py calls minio_file_system import

**"Import minio failed"**
- Install with: `pip install minio`
- Check PYTHONPATH includes fs_storage_minio directory

**"Connection refused"**
- Is MinIO running? Check with `curl http://localhost:9000/minio/health/live`
- Is MINIO_ENDPOINT correct?
- Are credentials (access_key/secret_key) correct?

**"Presigned URL fails"**
- Check if X-Accel-Redirect is configured in nginx
- Verify endpoint_url is accessible from nginx location
- Check if presigned URL expiration is reasonable (default 30 seconds)

## Contact

For questions or issues:
1. Review this document
2. Check test_minio_regression.py for usage examples
3. Review fs_storage_minio/minio_file_system.py for implementation details
