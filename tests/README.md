# MinIO Regression Tests

This directory contains regression tests for the MinIO implementation across all three modules:
- `fs_storage_minio`: fsspec filesystem backend
- `fs_attachment_minio`: Odoo attachment storage integration  
- `storage_backend_minio`: Legacy storage backend adapter

## Quick Start

### Option 1: Automatic (recommended)
Run the provided shell script, which will:
1. Check if MinIO is already running
2. Start a MinIO container if needed (requires Docker)
3. Run the full test suite
4. Clean up the container

```bash
./tests/run_minio_tests.sh
```

### Option 2: Manual Setup
If you prefer to manage MinIO yourself:

```bash
# Start MinIO (change port if needed)
docker run -d -p 9000:9000 -p 9001:9001 \
  -e MINIO_ROOT_USER=minioadmin \
  -e MINIO_ROOT_PASSWORD=minioadmin \
  minio/minio server /data

# Run tests
python3 tests/test_minio_regression.py
```

### Option 3: Against Remote MinIO
Point to an existing MinIO server:

```bash
MINIO_ENDPOINT=minio.example.com:9000 \
MINIO_ACCESS_KEY=your-key \
MINIO_SECRET_KEY=your-secret \
MINIO_SECURE=true \
python3 tests/test_minio_regression.py
```

## Test Coverage

### TestMinioConnection
- ✓ Basic connectivity to MinIO server
- ✓ Can list buckets

### TestMinioFileSystem
- ✓ Path splitting (bucket/key extraction)
- ✓ Write and read file content
- ✓ File existence checking
- ✓ List files in directory
- ✓ File deletion
- ✓ Creating empty files with touch()
- ✓ Getting file size

### TestPresignedURLs
- ✓ Generate presigned GET URLs (time-limited read access)
- ✓ Generate presigned PUT URLs (time-limited write access)

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `MINIO_ENDPOINT` | `localhost:9000` | MinIO server address |
| `MINIO_ACCESS_KEY` | `minioadmin` | Access key for authentication |
| `MINIO_SECRET_KEY` | `minioadmin` | Secret key for authentication |
| `MINIO_SECURE` | `false` | Use HTTPS (`true` or `false`) |

## Requirements

- Python 3.6+
- `minio` package: `pip install minio`
- Docker (for automatic MinIO setup)
- 9000/9001 ports available (or change `MINIO_ENDPOINT`)

## Troubleshooting

### "Connection refused"
MinIO is not running. Either:
- Start MinIO manually with Docker (see Quick Start Option 2)
- Check that the endpoint is correct: `MINIO_ENDPOINT=your-endpoint python3 tests/test_minio_regression.py`

### "Access Denied"
Wrong credentials. Set the correct access key and secret:
```bash
MINIO_ACCESS_KEY=correct-key MINIO_SECRET_KEY=correct-secret python3 tests/test_minio_regression.py
```

### Port already in use
If 9000 is already in use, map to a different port:
```bash
docker run -d -p 9001:9000 -p 9002:9001 \
  -e MINIO_ROOT_USER=minioadmin \
  -e MINIO_ROOT_PASSWORD=minioadmin \
  minio/minio server /data

MINIO_ENDPOINT=localhost:9001 python3 tests/test_minio_regression.py
```

## What the Tests Validate

1. **fs_storage_minio**: The new fsspec filesystem backend
   - Can connect to MinIO
   - Can write/read files
   - Can list objects
   - Can delete objects
   - Can create empty files
   - File operations return correct sizes

2. **Presigned URLs**: Critical for X-Accel-Redirect support in fs_attachment_minio
   - Can generate time-limited GET URLs
   - Can generate time-limited PUT URLs
   - URLs contain correct bucket/key and signature

3. **Integration**: Ensures all three MinIO modules work together
   - No boto3/aiobotocore dependencies
   - Native minio SDK usage
   - Proper error handling

## CI/CD Integration

To run in CI/CD pipeline:

```yaml
# Example GitHub Actions
- name: Run MinIO regression tests
  run: |
    docker run -d -p 9000:9000 minio/minio server /data
    python3 -m pip install minio
    ./tests/run_minio_tests.sh
```

## Notes

- Tests create and clean up their own test buckets (`test-fs-regression`, `test-presigned`)
- No external data is modified
- All tests are idempotent and can be run multiple times safely
- Tests take ~10-30 seconds depending on network latency
