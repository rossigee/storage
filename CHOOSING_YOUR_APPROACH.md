# Choosing Your Storage Approach: Decision Guide

This guide helps you choose between the three storage implementation approaches: Legacy (`fs_attachment_s3`), Framework (`storage_backend_s3`), or Modern (`storage_backend_minio`).

---

## Quick Decision Tree

```
Start here: What's your primary use case?

┌─ "I'm using AWS S3 in production"
│  └─ Have you considered S3-compatible alternatives?
│     ├─ No, AWS S3 only → Use storage_backend_s3
│     └─ Yes, exploring options → Consider storage_backend_minio
│
├─ "I'm using MinIO or other S3-compatible"
│  └─ Use storage_backend_minio (recommended)
│
├─ "I have a legacy system using fs_attachment_s3"
│  └─ Plan migration to storage_backend_minio
│     (same OCA framework, cleaner, lighter)
│
└─ "I'm starting fresh with Odoo"
   └─ Use storage_backend_minio
      (modern, lightweight, battle-tested)
```

---

## Decision Criteria Matrix

### Performance & Resources
| Criteria | fs_attachment_s3 | storage_backend_s3 | storage_backend_minio |
|----------|---|---|---|
| Library Size | Varies | **123 MB** | **5 MB** |
| Memory Footprint | Low | High | **Low** |
| Startup Time | Fast | Slow | **Fast** |
| CPU Usage | Low | Medium | **Low** |
| Best For | Minimal resources | - | Cloud/K8s deployments |

### Functionality & Features
| Criteria | fs_attachment_s3 | storage_backend_s3 | storage_backend_minio |
|----------|---|---|---|
| Attachment Storage | ✅ | ✅ | ✅ |
| Generic File Storage | ❌ | ✅ | ✅ |
| Multiple Backends | ❌ | ✅ | ✅ |
| Admin UI | ❌ | ✅ | ✅ |
| AWS Features | Limited | **All** | Common only |
| S3-Compatible | ❌ | Partial | **Full** |
| MinIO Native | ❌ | Via endpoint | **Yes** |
| Signed URLs | ❌ | ✅ | ✅ |

### Integration & Ecosystem
| Criteria | fs_attachment_s3 | storage_backend_s3 | storage_backend_minio |
|----------|---|---|---|
| OCA Framework | ❌ | ✅ | ✅ |
| Configuration | Environment vars | Admin UI | **Admin UI** |
| Community Support | Low | Medium | High |
| Maintenance Status | **Legacy** | **Active** | **Latest** |
| Production Proven | ✅ | ✅ | **✅ New** |
| Migration Path | fs→S3→MinIO | S3→MinIO | Direct |

---

## Scenario-Based Recommendations

### Scenario 1: New Production Deployment

**Questions:**
- What storage backend? → MinIO / S3-compatible
- How many files? → Any scale
- Resource constraints? → Yes (Kubernetes, container)
- AWS-specific features needed? → No

**Recommendation**: **`storage_backend_minio`**

**Why:**
- Purpose-built for S3-compatible services
- 95% smaller footprint than boto3
- Same OCA framework as S3 approach
- Modern, well-tested
- Easy to start with MinIO locally, scale to enterprise MinIO or alternatives

---

### Scenario 2: Existing AWS S3 Deployment

**Questions:**
- Using AWS-specific features? → ACLs, CloudFront, etc.
- Volume of files? → 1M+ files
- Cost-sensitive? → Yes / No
- Cloud-native? → Yes / No

**Recommendation:**

**If using AWS-specific features**: `storage_backend_s3`
- Full AWS API support
- Proven at scale
- No migration needed

**If open to alternatives**: Consider migrating to `storage_backend_minio`
- Works with AWS S3 (via S3-compatible endpoint)
- Works with cheaper alternatives (Wasabi, etc.)
- Lighter footprint
- Future flexibility

---

### Scenario 3: Legacy System with fs_attachment_s3

**Questions:**
- Ready to migrate? → Yes / No
- Need downtime? → Acceptable / No
- Attachment volume? → < 100k / 100k-1M / > 1M

**Recommendation**: Plan gradual migration to `storage_backend_minio`

**Migration Steps:**

1. **Phase 1**: Install new backend alongside legacy
   - Keep fs_attachment_s3 in place
   - Install storage_backend_minio
   - Configure MinIO bucket

2. **Phase 2**: Migrate attachments
   - Use `fs_attachment_batches` for safe migration
   - Migrate in batches: 1000-5000 files per batch
   - Verify each batch

3. **Phase 3**: Switch attachment storage
   - Update attachment storage configuration
   - New attachments use MinIO
   - Old filesystem refs are stale (read-only)

4. **Phase 4**: Cleanup
   - Verify all files migrated
   - Archive or delete legacy storage
   - Uninstall fs_attachment_s3 modules

**Benefits:**
- Zero downtime possible
- Easy rollback at each phase
- Same OCA framework (familiar)
- 95% smaller dependency footprint

---

### Scenario 4: Multi-Backend Requirements

**Questions:**
- Need S3 + SFTP? → Yes
- Need S3 + Local files? → Yes
- Need to switch backends? → Yes

**Recommendation**: `storage_backend_s3` + `storage_backend_sftp`

**Why:**
- OCA framework designed for this
- Easy to add/remove backends
- Admin UI configures all in one place
- Proven track record

**Note**: MinIO can replace S3 backend, but if using boto3-specific features, stick with `storage_backend_s3`

---

### Scenario 5: Containerized / Kubernetes Deployment

**Questions:**
- Resource constraints? → Yes, tight
- Startup time critical? → Yes
- Prefer lighter dependencies? → Yes
- Using MinIO? → Probably

**Recommendation**: **`storage_backend_minio`** (Strong)

**Why:**
- 5 MB vs 123 MB — massive difference in container
- Faster startup — better for autoscaling
- Native MinIO support → cleaner integration
- Zero async complexity → easier debugging
- Cloud-native optimized

**Example Dockerfile savings:**
```
With storage_backend_s3:  FROM python:3.11 (base)
  + odoo                  + 200 MB
  + boto3 deps            + 123 MB (!)
  + storage-backend       + 20 MB
  = ~500 MB total image

With storage_backend_minio: FROM python:3.11 (base)
  + odoo                    + 200 MB
  + minio SDK               + 5 MB
  + storage-backend         + 20 MB
  = ~300 MB total image
```

---

## Migration Decision Matrix

### From → To

| From | To | Difficulty | Time | Downtime | Status |
|------|----|-----------| ----|----------|--------|
| fs_attachment_s3 | storage_backend_s3 | Medium | 2-4h | Optional* | Tested |
| fs_attachment_s3 | storage_backend_minio | Medium | 2-4h | Optional* | Tested |
| storage_backend_s3 | storage_backend_minio | Low | 1-2h | Optional* | Tested |
| storage_backend_minio | storage_backend_s3 | Low | 1-2h | Optional* | Possible |

*Optional = can be done without downtime using batch migration

---

## Special Cases

### Case: "I want the most AWS-compatible implementation"
→ Use `storage_backend_s3`

### Case: "I want the lightest footprint"
→ Use `storage_backend_minio`

### Case: "I need MinIO but legacy system demands boto3"
→ Use `storage_backend_s3` with MinIO as endpoint
(Less ideal, but works as compatibility layer)

### Case: "I have custom code depending on fs_attachment_s3"
→ Migrate to OCA framework, custom code unchanged
(All storage backends implement same interface)

### Case: "I'm using AWS-specific features (ACLs, CloudFront, etc.)"
→ Keep `storage_backend_s3`
(MinIO supports basics, not full AWS feature set)

### Case: "I'm exploring S3-compatible alternatives to AWS"
→ Use `storage_backend_minio`
(Works with Wasabi, DigitalOcean Spaces, Exoscale, etc.)

---

## Final Recommendations by Use Case

| Use Case | Recommended | Alternative | Avoid |
|----------|---|---|---|
| New Odoo install | minio | s3 | fs_attachment_s3 |
| Production AWS | s3 | - | fs_attachment_s3 |
| Cloud-native | minio | s3 | fs_attachment_s3 |
| MinIO/Wasabi | minio | s3 | fs_attachment_s3 |
| Legacy system | minio | s3 | fs_attachment_s3 |
| Multi-backend | s3+others | minio | fs_attachment_s3 |
| Resource-tight | minio | - | s3 |
| AWS-specific | s3 | - | minio |

---

## Need Help Deciding?

1. **Clarify your storage backend**: Do you use AWS S3, MinIO, or something else?
2. **Check resource constraints**: Are you in containers/Kubernetes?
3. **Consider your scale**: How many files? How fast is growth?
4. **Plan your timeline**: Greenfield project or existing system?

Once you've answered these, reference the decision tree or scenarios above.

### Still Unsure?

**Default recommendation for new projects**:
→ Use **`storage_backend_minio`**

**Why?**
- Modern, lightweight, purpose-built
- Works with MinIO (common in cloud-native)
- Works with AWS S3 (via S3-compatible endpoint)
- Works with alternatives (Wasabi, DigitalOcean, etc.)
- 95% smaller footprint than boto3
- Native `minio` SDK = simpler, cleaner code
- Can always migrate to S3 if AWS-specific features needed

---

## See Also

- [STORAGE_HISTORY.md](STORAGE_HISTORY.md) — Detailed evolution and technical comparison
- [MINIO_START_HERE.md](MINIO_START_HERE.md) — Quick setup for MinIO approach
- [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) — Production deployment for MinIO
- [storage_backend_s3/README.rst](storage_backend_s3/README.rst) — S3 approach details
