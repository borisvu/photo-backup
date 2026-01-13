# Error Recovery Test Guide

Manual chaos-engineering test for the Photo Backup System (Task 106).

## Purpose

Test that the backup system:

1. Handles mid-backup failures gracefully
2. Reports errors correctly
3. Recovers when the remote becomes available again
4. Maintains data integrity after recovery

## Requirements

- Docker running
- Project installed: `pip install -e .`
- **Existing photo folder** with sufficient files (see below)

## Minimum Photo Requirements

Based on performance results (T2: 146.5 files/sec, 446 MB/sec with local Minio):

| Scenario        | Min Files | Min Size | Transfer Window |
| --------------- | --------- | -------- | --------------- |
| Minimum         | 500       | ~1.5 GB  | ~3-4 seconds    |
| Recommended     | 1000+     | ~3 GB    | ~7+ seconds     |
| RAW/Large files | 200       | ~2 GB    | ~5 seconds      |

**Note:** Local Minio is very fast. If your photos are on a slow drive or you have large RAW files, fewer files may suffice. The goal is having enough transfer time to stop Minio mid-operation.

---

## Test Procedure

### Terminal Setup

You'll need **3 terminals** open:

- **Terminal 1:** Minio container
- **Terminal 2:** Photo backup commands
- **Terminal 3:** Chaos injection (stopping/starting Minio)

### Phase 1: Setup

**Terminal 1 - Start Minio:**

```bash
docker run --name photo-backup-chaos-test \
  -p 9050:9000 -p 9140:9001 \
  -e MINIO_ROOT_USER=minioadmin \
  -e MINIO_ROOT_PASSWORD=minioadmin \
  minio/minio:latest server /data --console-address :9001
```

**Terminal 2 - Prepare environment:**

```bash
cd /path/to/photo-backup
source venv/bin/activate

# Set your photo source path (must have 500+ photos)
export TEST_PHOTO_PATH="/path/to/your/photos"

# Verify file count
find "$TEST_PHOTO_PATH" -type f \( -iname "*.jpg" -o -iname "*.jpeg" -o -iname "*.png" -o -iname "*.heic" \) | wc -l
```

**Terminal 3 - Wait for Minio ready:**

```bash
# Wait until this succeeds
docker exec photo-backup-chaos-test mc alias set test http://localhost:9000 minioadmin minioadmin

# Create bucket
docker exec photo-backup-chaos-test mc mb test/my-photo-backup-bucket-test --ignore-existing
```

### Phase 2: Start Backup

**Terminal 2:**

```bash
# Start sync with verbose logging
PHOTO_BACKUP_TEST_MODE=1 \
PHOTO_BACKUP_SOURCE_PATH="$TEST_PHOTO_PATH" \
PHOTO_BACKUP_S3_ENDPOINT="http://localhost:9050" \
photo-backup sync --verbose
```

### Phase 3: Chaos Injection

**Terminal 3 - Stop Minio mid-transfer:**

Watch Terminal 2 for transfer progress (e.g., "Transferring:" or progress percentage), then:

```bash
# Wait 2-3 seconds after transfer starts, then:
docker stop photo-backup-chaos-test
```

### Phase 4: Observe Failure

**Expected behavior in Terminal 2:**

- Error messages: "connection refused", "network unreachable", or "timeout"
- Backup operation fails
- Error is logged with categorization

**Verify state was saved:**

```bash
# Check state file for failure tracking
cat ~/.local/state/photo-backup-test/backup_state.json | grep -E '"consecutive_failures"|"last_error"'
```

Expected: `consecutive_failures` should be > 0

### Phase 5: Recovery

**Terminal 3 - Restart Minio:**

```bash
docker start photo-backup-chaos-test

# Wait for ready
sleep 5
docker exec photo-backup-chaos-test mc alias set test http://localhost:9000 minioadmin minioadmin
```

**Terminal 2 - Run sync again:**

```bash
PHOTO_BACKUP_TEST_MODE=1 \
PHOTO_BACKUP_SOURCE_PATH="$TEST_PHOTO_PATH" \
PHOTO_BACKUP_S3_ENDPOINT="http://localhost:9050" \
photo-backup sync --verbose
```

### Phase 6: Verify Data Integrity

**Terminal 3 - Check files in Minio:**

```bash
# Count files in bucket
docker exec photo-backup-chaos-test mc ls --recursive test/my-photo-backup-bucket-test/ | wc -l

# Compare with source
find "$TEST_PHOTO_PATH" -type f \( -iname "*.jpg" -o -iname "*.jpeg" -o -iname "*.png" -o -iname "*.heic" \) | wc -l
```

**Terminal 2 - Run verification:**

```bash
PHOTO_BACKUP_TEST_MODE=1 \
PHOTO_BACKUP_SOURCE_PATH="$TEST_PHOTO_PATH" \
PHOTO_BACKUP_S3_ENDPOINT="http://localhost:9050" \
photo-backup verify --verbose
```

---

## Success Criteria

| Check           | Expected Outcome                         | Status |
| --------------- | ---------------------------------------- | ------ |
| Error detection | "Connection refused" or similar logged   | ☐      |
| State tracking  | `consecutive_failures` > 0 after failure | ☐      |
| Recovery sync   | Completes successfully                   | ☐      |
| File count      | Matches source count                     | ☐      |
| Verification    | Passes with no mismatches                | ☐      |

---

## Cleanup

```bash
docker stop photo-backup-chaos-test
docker rm photo-backup-chaos-test
```

---

## Troubleshooting

### Transfer completes too quickly

If you can't stop Minio in time:

- Use a larger photo collection (2000+ files)
- Use RAW photos (10-25 MB each)
- Add network throttling: `docker network create --driver bridge --opt com.docker.network.bridge.host_binding_ipv4=127.0.0.1 slow-net`

### Minio won't restart

```bash
docker rm -f photo-backup-chaos-test
# Then start fresh from Phase 1
```

### State file not found

The state file location in test mode:

- macOS: `~/.local/state/photo-backup-test/backup_state.json`
- Linux: `~/.local/state/photo-backup-test/backup_state.json`

---

## Results Template

```markdown
## Run: YYYY-MM-DD

**Photo Source:** [path, file count, total size]  
**Machine:** [e.g., MacBook Pro M1]

| Phase             | Outcome | Notes                        |
| ----------------- | ------- | ---------------------------- |
| Chaos injection   |         | Time to stop: Xs after start |
| Error detection   |         | Error type logged:           |
| State persistence |         | consecutive_failures:        |
| Recovery          |         |                              |
| Verification      |         |                              |

**Result:** PASS / FAIL

### Notes

-
```
