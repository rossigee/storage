# MinIO Implementation - Production Deployment Guide

## Overview

This guide covers deploying the new genuine MinIO storage implementation to production. The implementation is **fully tested and production-ready** as of 2026-06-21.

**Status**: ✅ Ready for production deployment

## Pre-Deployment Requirements

### 1. MinIO Server Setup

You need a running MinIO instance. Options:

#### Option A: Self-Hosted MinIO
```bash
# Docker (recommended)
docker run -d \
  -p 9000:9000 \
  -p 9001:9001 \
  -e MINIO_ROOT_USER=your-access-key \
  -e MINIO_ROOT_PASSWORD=your-secret-key \
  --name minio \
  minio/minio server /data

# Or use MinIO on Kubernetes
helm repo add minio https://charts.min.io
helm install minio minio/minio --values values.yaml
```

#### Option B: Cloud-Hosted MinIO
- AWS S3 (S3-compatible via custom endpoint)
- Wasabi
- DigitalOcean Spaces
- Any S3-compatible provider

### 2. Prerequisites

- Odoo 16.0, 17.0, or 18.0
- Python 3.6+
- MinIO Python SDK: `pip install minio`
- fsspec: `pip install fsspec` (for fs_storage_minio)
- Existing attachment storage (if migrating)

### 3. Network Access

- Odoo server must reach MinIO on port 9000 (configurable)
- If using X-Accel-Redirect, nginx must reach MinIO
- DNS resolution for MinIO endpoint

## Deployment Steps

### 1. Install Modules

Option A: Git clone (development)
```bash
cd /path/to/odoo/addons
git clone https://github.com/OCA/storage.git
cd storage
git checkout 18.0-minio  # or 17.0-minio, 16.0-minio
```

Option B: Direct installation
```bash
pip install git+https://github.com/OCA/storage.git@18.0-minio
```

### 2. Update Odoo Add-ons Path

Edit `~/.odoorc` or your Odoo configuration:
```ini
[options]
addons_path = /path/to/storage,/path/to/other/addons
```

### 3. Install Modules in Odoo

Via command line:
```bash
odoo -d your-database -c ~/.odoorc -i fs_storage_minio,fs_attachment_minio --stop-after-init
```

Or via Odoo web interface:
1. Go to **Apps**
2. Search for "MinIO"
3. Install **fs_storage_minio** first
4. Install **fs_attachment_minio**
5. (Optional) Uninstall **fs_attachment_s3** if migrating

### 4. Create Storage Backend in Odoo

1. Go to **Storage > Storage Backends**
2. Click **New**
3. Fill in:
   - **Name**: "Production MinIO" (or your name)
   - **Code**: "minio-prod" (unique identifier)
   - **Protocol**: "minio"
   - **Directory Path**: "odoo-attachments" (bucket name)
   - **Endpoint**: Your MinIO endpoint (e.g., "minio.example.com:9000")
   - **Access Key**: Your MinIO access key
   - **Secret Key**: Your MinIO secret key
   - **Secure**: ✅ checked (for HTTPS) or unchecked (for HTTP)
   - **Region**: "us-east-1" (or your region)

4. Click **Test Config** to verify
5. Save

### 5. Set as Default (Optional)

If you want ALL new attachments to use MinIO:

```python
# In Odoo Python shell:
env['ir.config_parameter'].set_param(
    'ir_attachment.storage.location.default',
    'minio-prod'
)
```

Or in configuration file:
```ini
[options]
ir_attachment_storage_location = minio-prod
```

### 6. Migrate Existing Attachments (Optional)

Only needed if you're moving from S3 or another backend.

**Option A: Bulk migration (fastest)**

```python
# Run in Odoo shell (odoo --shell)
from odoo import api
env = api.Environment(cr, uid, context)

# Get storage backends
old_storage = env['fs.storage'].search([('code', '=', 's3-prod')])[0]
new_storage = env['fs.storage'].search([('code', '=', 'minio-prod')])[0]

# Find attachments using old storage
attachments = env['ir.attachment'].search([
    ('fs_storage_id', '=', old_storage.id),
])

print(f"Migrating {len(attachments)} attachments...")

# Process in batches
batch_size = 100
for i in range(0, len(attachments), batch_size):
    batch = attachments[i:i+batch_size]
    for att in batch:
        att.write({'datas': att.datas})  # Re-write triggers migration
    env.cr.commit()
    print(f"Migrated {min(i+batch_size, len(attachments))}/{len(attachments)}")

print("Done!")
```

**Option B: Gradual migration (safer)**

Set MinIO as default and let new attachments migrate organically:

```python
env['ir.config_parameter'].set_param(
    'ir_attachment.storage.location.default',
    'minio-prod'
)
# New attachments go to MinIO
# Old ones stay in S3 until manually migrated
```

### 7. Configure X-Accel-Redirect (Optional)

For efficient file serving via nginx:

**Nginx configuration:**
```nginx
location ~ ^/fs_x_sendfile/https?/(.*?)/(.*)$ {
    internal;
    proxy_pass $1://$2/$3;
    proxy_http_version 1.1;
    proxy_set_header Host $2;
    proxy_buffering off;
}
```

**Odoo configuration:**

Go to **Storage > Storage Backends** > Your MinIO storage:
- ✅ Check **Use X-Accel-Redirect to serve internal URL**
- ✅ Check **Use signed URL for X-Accel-Redirect** (for time-limited URLs)
- Set **Signed URL Expiration** (default: 30 seconds)

### 8. Verify Deployment

Test in Odoo:
```python
# In Odoo shell
env = api.Environment(cr, uid, context)

# Create test attachment
att = env['ir.attachment'].create({
    'name': 'test.txt',
    'datas': base64.b64encode(b'test content'),
    'fs_storage_id': env['fs.storage'].search([('code', '=', 'minio-prod')]).id,
})

# Verify it was stored
assert att.store_fname.startswith('minio-prod://')
print(f"✓ Attachment created: {att.store_fname}")

# Download it
assert att.datas == base64.b64encode(b'test content')
print("✓ Attachment retrieved successfully")

# Check in MinIO
# mc ls minio-prod/odoo-attachments/
```

## Post-Deployment Verification

### Checklist

- [ ] All modules installed without errors
- [ ] Storage backend created and test config passes
- [ ] Test attachment created and retrieved successfully
- [ ] Files appear in MinIO bucket via `mc ls`
- [ ] File content matches original
- [ ] X-Accel-Redirect working (if enabled)
- [ ] Presigned URLs are generated (if enabled)
- [ ] Performance is acceptable
- [ ] Logs show no errors or warnings
- [ ] Database backups are current

### Monitoring

Set up monitoring for:

**MinIO metrics:**
- Bucket size: `du -sh /data`
- Object count: `mc du minio-prod`
- Read/write operations
- Disk usage

**Odoo logs:**
```bash
tail -f /var/log/odoo/odoo-server.log | grep -i "minio\|attachment"
```

**System resources:**
```bash
# Monitor during heavy attachment usage
watch -n 1 'ps aux | grep odoo; df -h'
```

## Troubleshooting Deployment Issues

### Module Installation Fails

**Error**: "No module named fsspec"
```bash
pip install fsspec s3fs
```

**Error**: "minio not installed"
```bash
pip install minio
```

### Storage Backend Test Fails

**"Connection refused"**: MinIO not accessible
```bash
# Verify MinIO is running
curl http://your-minio-endpoint:9000/minio/health/live

# Check firewall
sudo ufw allow 9000/tcp

# Verify hostname resolution
nslookup your-minio-endpoint
```

**"Access Denied"**: Wrong credentials
```bash
# Verify with MinIO client
mc alias set test-alias http://your-endpoint access-key secret-key
mc ls test-alias
```

**"SSL: CERTIFICATE_VERIFY_FAILED"**: TLS issue
- Check **Secure** setting matches your setup (HTTP=unchecked, HTTPS=checked)
- Verify certificate is valid: `openssl s_client -connect your-endpoint:9000`

### Attachment Upload Fails

**"Permission denied"**: MinIO user lacks permissions
```bash
# Verify bucket exists and is accessible
mc ls minio-alias/bucket-name

# Check user policy
# Go to MinIO console and verify user has readwrite policy
```

**"Connection timeout"**: Network issue
```bash
# Test connectivity from Odoo server
telnet your-minio-endpoint 9000
```

### Performance Issues

**Slow uploads/downloads**:
- Check MinIO disk I/O: `iostat -x 1`
- Check network latency: `ping your-minio-endpoint`
- Verify MinIO resource limits
- Check Odoo logs for errors

**High memory usage**:
- File buffering happens in memory
- Large files (>500MB) may cause issues
- Consider setting upload size limits in Odoo

## Scaling Considerations

### Small Deployment (< 100GB)

- Single MinIO instance sufficient
- Standard Docker deployment OK
- No special configuration needed

### Medium Deployment (100GB - 1TB)

- Distributed MinIO (multiple nodes) recommended
- MinIO with persistent storage
- Monitor disk usage monthly
- Set up daily backups

### Large Deployment (> 1TB)

- MinIO with erasure coding (fault tolerance)
- Kubernetes deployment recommended
- Object lifecycle policies (delete old attachments)
- S3 sync for disaster recovery
- Monitoring and alerting required

## Backup & Disaster Recovery

### Backup Strategy

**Option A: MinIO Native**
```bash
# Backup to S3
mc mirror minio-prod/bucket s3/backup-bucket

# Or to another MinIO
mc mirror minio-prod/bucket minio-backup/bucket
```

**Option B: File System**
```bash
# If using local storage
rsync -av /data /backup/minio-daily-$(date +%Y%m%d)
```

**Option C: Database**
```bash
# Backup Odoo database (stores file references)
pg_dump odoo-database > /backup/odoo-$(date +%Y%m%d).sql
```

### Recovery

If MinIO data is lost but database intact:
1. Restore MinIO data from backup
2. Odoo will find attachments automatically (by store_fname)
3. If MinIO lost but DB intact: recover MinIO data, then restore to Odoo

If both lost:
1. Restore database from backup
2. Restore MinIO data from backup
3. Re-link if necessary

## Maintenance

### Regular Tasks

**Daily:**
- Monitor MinIO health: `curl localhost:9000/minio/health/live`
- Check disk usage: `df -h /data`
- Review Odoo logs for errors

**Weekly:**
- Verify attachment creation/retrieval working
- Check MinIO performance metrics
- Review resource usage

**Monthly:**
- Backup verification (test restore)
- Disk usage trending
- Security audit (logs, access patterns)

### Upgrades

**MinIO Upgrade:**
```bash
# Stop old instance
docker stop minio

# Pull new version
docker pull minio/minio:latest

# Start with new version (data persists)
docker run -d ... minio/minio:latest ...
```

**Odoo Module Update:**
```bash
# Pull latest code
cd /path/to/storage && git pull origin 18.0-minio

# Update modules
odoo -d your-database -u fs_storage_minio,fs_attachment_minio --stop-after-init
```

## Production Checklist - Final

Before going live:

- [ ] MinIO instance is production-hardened
- [ ] Persistent storage is configured
- [ ] Backups are automated and tested
- [ ] SSL/TLS certificates are valid
- [ ] Access controls are restricted (no default credentials)
- [ ] Monitoring and alerting are set up
- [ ] Odoo modules are installed and tested
- [ ] Storage backend test passes
- [ ] Existing attachments are migrated (if applicable)
- [ ] X-Accel-Redirect is configured (if using nginx)
- [ ] Disaster recovery plan is documented
- [ ] Team is trained on troubleshooting
- [ ] Performance baseline is established
- [ ] Runbooks are written for common issues
- [ ] On-call rotation is aware of system

## Support & Documentation

- **Testing Report**: See `MINIO_VALIDATION_REPORT.md`
- **Migration Guide**: See `MINIO_MIGRATION_GUIDE.md`
- **Architecture**: See `fs_storage_minio/minio_file_system.py`
- **Configuration**: See Odoo UI or `fs_attachment_minio/` models
- **Issues**: GitHub issues on OCA/storage repository

## Success Criteria

Your MinIO deployment is successful when:

✅ Attachments are reliably stored and retrieved  
✅ Files appear in MinIO bucket  
✅ No boto3/aiobotocore in logs  
✅ Native minio SDK is being used  
✅ X-Accel-Redirect works (if configured)  
✅ Performance meets or exceeds S3 baseline  
✅ Backups are automated and tested  
✅ Monitoring is active and alerting on issues  
✅ Team is confident in the system  

---

**Deployment Date**: [Fill in]  
**Deployed By**: [Fill in]  
**Status**: Production  
**Next Review**: [Fill in]
