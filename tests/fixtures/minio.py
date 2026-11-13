"""MinIO image used by the Docker-backed tests.

The official ``minio/minio`` image is no longer pullable from Docker Hub, so the
tests use the community ``pgsty/minio`` build (multi-arch, ships ``mc``), pinned by
digest. Override with ``MINIO_TEST_IMAGE`` to try another build.
"""

import os

MINIO_IMAGE = os.environ.get(
    "MINIO_TEST_IMAGE",
    "pgsty/minio@sha256:b6bfe7239bfc83fb90d31612d9704d86039dd714f7904b3f1ad68f211e602372",
)
