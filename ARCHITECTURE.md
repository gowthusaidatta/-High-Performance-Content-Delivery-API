# Architecture

## System Overview

The High-Performance Content Delivery API is designed to minimize latency and maximize cache hit rates through strategic use of HTTP caching, CDN integration, and object storage.

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                  CLIENTS                                     │
│  (Web Browsers, Mobile Apps, API Consumers)                                 │
└────────────────────────────────────────┬────────────────────────────────────┘
                                         │
                    ┌────────────────────┴────────────────────┐
                    │                                         │
            (HTTPS/HTTP)                            (HTTPS/HTTP)
                    │                                         │
        ┌───────────▼────────────┐              ┌──────────────▼─────────┐
        │  CDN Edge Servers      │              │  Origin API Server     │
        │  (Cloudflare, etc.)    │              │  (FastAPI)             │
        │                        │              │                        │
        │ - Cache Layer 1        │◄─────────────┤ - Request Routing      │
        │ - Origin Shield        │              │ - Request Handling     │
        │ - DDoS Protection      │              │ - ETag Generation      │
        │ - Compression          │              │ - Token Validation     │
        └────────────┬───────────┘              └──────────┬─────────────┘
                     │                                     │
                     └─────────────────┬───────────────────┘
                                       │
                    ┌──────────────────┼──────────────────┐
                    │                  │                  │
                    ▼                  ▼                  ▼
        ┌─────────────────────┐ ┌─────────────────┐ ┌──────────────────┐
        │   PostgreSQL DB     │ │  Redis Cache    │ │ Object Storage   │
        │                     │ │  (Optional)     │ │ (MinIO/S3)       │
        │ - Asset Metadata    │ │                 │ │                  │
        │ - Versions          │ │ - Session Cache │ │ - Asset Files    │
        │ - Access Tokens     │ │ - Query Cache   │ │ - Versioned Objs │
        └─────────────────────┘ └─────────────────┘ └──────────────────┘
```

## Request Flow

### 1. Public Asset Download (Cached)

```
Client Request (GET /assets/{id}/download)
    │
    ├─► CDN Edge Server
    │   ├─ Cache HIT (304 or 200 with cached content)
    │   └─ Return response (0-10ms)
    │
    └─► (If cache MISS)
        └─► Origin API Server
            ├─ Query PostgreSQL for asset metadata
            ├─ Generate/retrieve ETag
            ├─ Check If-None-Match header
            ├─ Download from S3 if needed
            ├─ Set Cache-Control: public, max-age=31536000, immutable
            ├─ Return 200 OK with content
            └─ CDN caches response for 1 year
```

**Response Headers:**
```
HTTP/1.1 200 OK
ETag: "a1b2c3d4e5f6..."
Last-Modified: Wed, 10 Jan 2024 10:00:00 GMT
Cache-Control: public, max-age=31536000, immutable
Content-Type: application/pdf
Content-Length: 1024000
X-Content-Type-Options: nosniff
```

### 2. Conditional Request (304 Not Modified)

```
Client Request (GET with If-None-Match: "etag")
    │
    ├─► CDN Edge Server
    │   └─ Cache HIT (return 304 with empty body)
    │       OR pass through to origin
    │
    └─► Origin API Server
        ├─ Query PostgreSQL for asset
        ├─ Compare ETag (no hash calculation!)
        ├─ Match found
        ├─ Return 304 Not Modified (0 bytes)
        └─ Saves bandwidth
```

**Benefits:**
- Zero bytes transmitted
- Reduces bandwidth by 99%+
- Client uses cached version
- Sub-millisecond response time

### 3. Private Asset Access (Token-Based)

```
Client Request (GET /assets/private/{token})
    │
    ├─► CDN (NOT cached)
    │   └─ Pass through to origin
    │
    └─► Origin API Server
        ├─ Query PostgreSQL for access token
        ├─ Validate token
        │  ├─ Check if token exists
        │  ├─ Check if not revoked
        │  ├─ Check if not expired
        │
        ├─ If valid
        │  ├─ Query asset metadata
        │  ├─ Set Cache-Control: private, no-store, no-cache, must-revalidate
        │  ├─ Download from S3
        │  └─ Return 200 OK
        │
        └─ If invalid
           └─ Return 403 Forbidden
```

**Response Headers (Private):**
```
HTTP/1.1 200 OK
ETag: "x1y2z3a4b5c6..."
Cache-Control: private, no-store, no-cache, must-revalidate
Content-Type: application/pdf
X-Content-Type-Options: nosniff
```

### 4. Asset Upload Flow

```
Client Request (POST /assets/upload)
    │
    └─► Origin API Server
        ├─ Receive file upload
        ├─ Calculate SHA-256 ETag of content
        ├─ Upload to MinIO/S3
        ├─ Store metadata in PostgreSQL
        │  ├─ Asset ID (UUID)
        │  ├─ Filename
        │  ├─ MIME type
        │  ├─ File size
        │  ├─ ETag (strong)
        │  ├─ Object storage key
        │  └─ Timestamps
        │
        └─ Return 200 OK with metadata
            {
              "id": "asset-uuid",
              "filename": "file.pdf",
              "etag": "\"sha256hash\"",
              "size": 1024000,
              "is_public": true,
              "created_at": "2024-01-10T10:00:00"
            }
```

### 5. Asset Publishing (Versioning)

```
Client Request (POST /assets/{id}/publish)
    │
    └─► Origin API Server
        ├─ Query current asset
        ├─ Download current content from S3
        ├─ Create version object key: versions/{id}/v{n}/filename
        ├─ Upload to S3 (immutable)
        ├─ Store AssetVersion in PostgreSQL
        │  ├─ Version number
        │  ├─ Object key
        │  ├─ ETag
        │  └─ Timestamp
        │
        ├─ Increment asset version counter
        ├─ Trigger CDN purge (if enabled)
        │
        └─ Return 200 OK
            {
              "version_id": "version-uuid",
              "version_number": 1,
              "etag": "\"sha256hash\"",
              "url": "https://cdn.example.com/assets/public/version-uuid"
            }
```

## Caching Strategy

### Three-Tier Cache Architecture

```
┌─────────────────────────────────────────────┐
│  Tier 1: Browser Cache (Client-side)        │
│  - max-age: 60 seconds                      │
│  - Revalidates after 60s                    │
│  - Respects ETag                            │
│  - Saves bandwidth                          │
└─────────────────────────────────────────────┘
                     │
┌─────────────────────▼─────────────────────────┐
│  Tier 2: CDN Edge Cache (Cloudflare, etc)    │
│  - max-age (public): 31536000 (1 year)       │
│  - max-age (mutable): 3600 (1 hour)          │
│  - Origin shield: Additional layer            │
│  - Immutable flag for versioned content      │
│  - Cache hit ratio target: >95%              │
└─────────────────────────────────────────────┘
                     │
┌─────────────────────▼─────────────────────────┐
│  Tier 3: Origin Server Cache (Optional)      │
│  - Query result cache                        │
│  - Asset metadata cache                      │
│  - ETag lookup cache                         │
└─────────────────────────────────────────────┘
```

### Cache Directives

#### Immutable Content (Versioned)
```
Cache-Control: public, max-age=31536000, immutable
```
- Cached for 1 year (31536000 seconds)
- Never expires
- Immutable flag prevents revalidation
- Safe for versioned URLs

#### Mutable Content (Latest)
```
Cache-Control: public, s-maxage=3600, max-age=60
```
- Browser: 60 seconds (max-age)
- CDN: 3600 seconds (s-maxage)
- After browser cache expires, revalidates
- CDN holds longer for efficiency

#### Private Content
```
Cache-Control: private, no-store, no-cache, must-revalidate
```
- Not cached by CDN
- Not stored in browser cache
- Always revalidates
- Required for sensitive content

## ETag Strategy

### Strong ETag Generation

```python
import hashlib

def generate_etag(content: bytes) -> str:
    """Generate strong ETag using SHA-256"""
    hash_value = hashlib.sha256(content).hexdigest()
    return f'"{hash_value}"'
```

**Advantages:**
- SHA-256 provides collision resistance
- Changes for any byte modification
- Stored in DB (no recalculation)
- Used for 304 Not Modified responses

### ETag-Based Conditional Requests

```
Client: GET /assets/123
Server Response:
  HTTP/1.1 200 OK
  ETag: "a1b2c3d4e5f6..."
  
Client (later):
  GET /assets/123
  If-None-Match: "a1b2c3d4e5f6..."
  
Server (matching ETag):
  HTTP/1.1 304 Not Modified
  (empty body - 0 bytes!)
  
Client: Uses cached version
```

## Security Architecture

### Access Token System

```
1. Create Token:
   POST /assets/{id}/access-token
   ├─ Generate 32-byte random token
   ├─ Set expiry: now + TOKEN_EXPIRY_SECONDS
   ├─ Store in PostgreSQL
   └─ Return to client

2. Use Token:
   GET /assets/private/{token}
   ├─ Query token from DB
   ├─ Validate:
   │  ├─ Token exists
   │  ├─ Not revoked
   │  ├─ Not expired (datetime.utcnow() < expires_at)
   └─ If valid: return content
   └─ If invalid: 403 Forbidden

3. Token Expiry:
   ├─ Configured per environment
   ├─ Default: 3600 seconds (1 hour)
   ├─ Adjustable per token
   └─ Automatic cleanup (optional job)
```

### Origin Protection

```
CDN Configuration:
├─ Origin Shield enabled
├─ IP whitelist
│  ├─ Only CDN IPs can access origin
│  └─ Blocks direct attacks
│
├─ Rate limiting
│  ├─ Per-IP limits
│  ├─ Protects upload endpoint
│  └─ Prevents DOS
│
└─ HTTPS/TLS
   ├─ Origin ↔ CDN: TLS
   ├─ Client ↔ CDN: TLS
   └─ Encryption in transit
```

## Scalability Considerations

### Horizontal Scaling

```
Multiple Origin Servers (Behind Load Balancer)
┌──────────────────────────────────────────┐
│         Load Balancer (HAProxy)          │
│  - Session persistence (optional)        │
│  - Health checks                         │
│  - Request distribution                  │
└─┬────────────────────────────────────────┘
  │
  ├─► Origin Server 1 (FastAPI)
  ├─► Origin Server 2 (FastAPI)
  ├─► Origin Server 3 (FastAPI)
  │
  ├─ Shared PostgreSQL (read replicas)
  │
  └─ Shared Object Storage (MinIO/S3)
```

### Database Optimization

```
PostgreSQL:
├─ Indexes on frequently queried columns
│  ├─ Asset.id (primary key)
│  ├─ AccessToken.token
│  └─ AssetVersion.asset_id
│
├─ Partitioning (optional for scale)
│  ├─ Partition AccessToken by month
│  └─ Archive old versions
│
└─ Connection pooling
   ├─ SQLAlchemy pool_size=20
   └─ max_overflow=40
```

## Performance Optimizations

### 1. ETag Caching
- ETags pre-calculated during upload
- No expensive hash calculations per request
- Direct database lookup

### 2. Conditional Response Handling
- Fast string comparison
- Return 304 with empty body
- Saves 99% of bandwidth

### 3. CDN Configuration
- Aggressive caching for public content
- Origin shield to reduce backend load
- Cache purging on updates (optional)

### 4. Object Storage
- Async uploads to S3/MinIO
- Streaming downloads
- Signed URLs for direct access

## Monitoring & Observability

### Metrics to Track

```
Performance Metrics:
├─ Response time (p50, p95, p99)
├─ Cache hit ratio (>95% target)
├─ Error rates (4xx, 5xx)
├─ Request throughput (req/sec)
└─ Bandwidth saved by caching

Business Metrics:
├─ Assets uploaded (count)
├─ Total storage used (GB)
├─ Private vs public asset split
└─ Token generation rate
```

### Logging

```
Structure:
├─ Request logging
│  ├─ Timestamp
│  ├─ Method, Path, Status
│  ├─ Response time
│  ├─ Cache status
│  └─ User agent
│
└─ Application logging
   ├─ Upload operations
   ├─ Token creation/validation
   ├─ CDN purge operations
   └─ Errors and exceptions
```

## Disaster Recovery

### Backup Strategy

```
1. Database Backups
   ├─ Frequency: Daily
   ├─ Retention: 30 days
   ├─ Location: S3 backup bucket
   └─ Restore time: <5 minutes

2. Asset Backups
   ├─ Frequency: Continuous (S3 versioning)
   ├─ Retention: Per bucket policy
   ├─ Location: Multi-region (optional)
   └─ Restore time: <1 minute

3. Configuration Backups
   ├─ Frequency: On change
   ├─ Location: Git repo
   └─ Version control enabled
```

## Summary

This architecture prioritizes:
1. **Performance**: Multi-tier caching, conditional requests
2. **Scalability**: Stateless origin servers, distributed caching
3. **Reliability**: Database backups, monitoring
4. **Security**: Token-based access, origin protection
5. **Cost-efficiency**: Reduced bandwidth, origin load
