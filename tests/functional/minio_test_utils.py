import contextlib
import subprocess
import time
from collections.abc import Generator

import docker
import pytest

from tests.fixtures.minio import MINIO_IMAGE


class MinioTestUtils:
    """Utilities to manage Minio/Docker for functional tests."""

    @staticmethod
    def get_docker_client() -> docker.DockerClient | None:
        """Return a docker client, trying desktop socket if available."""
        try:
            result = subprocess.run(["docker", "context", "ls"], capture_output=True, text=True)
            if result.returncode == 0:
                socket_path = None
                for line in result.stdout.split("\n"):
                    if "*" in line and "desktop" in line.lower():
                        for part in line.split():
                            if part.startswith("unix://"):
                                socket_path = part.replace("unix://", "")
                                break
                        if socket_path:
                            break
                if socket_path:
                    return docker.DockerClient(base_url=f"unix://{socket_path}")
            # Fallback
            return docker.from_env()
        except Exception:
            return None

    @staticmethod
    def wait_for_minio_ready(container_name: str, port: int = 9000, max_attempts: int = 30) -> None:
        """Block until Minio is ready to accept commands or raise via pytest.fail.

        Note: The port parameter is kept for API compatibility but not used internally.
        Inside the container, Minio always listens on port 9000 (the container's internal port).
        The port mapping is only for external access from the host.
        """
        import pytest  # local import to avoid test import cost elsewhere

        for _attempt in range(max_attempts):
            try:
                result = subprocess.run(
                    [
                        "docker",
                        "exec",
                        container_name,
                        "mc",
                        "alias",
                        "set",
                        "test",
                        "http://localhost:9000",  # Always use internal port 9000
                        "minioadmin",
                        "minioadmin",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                if result.returncode == 0:
                    return
            except (subprocess.TimeoutExpired, subprocess.CalledProcessError):
                pass
            time.sleep(2)
        else:
            pytest.fail("Minio container failed to start within timeout")

    @staticmethod
    def start_or_reuse_minio(
        client: docker.DockerClient, container_name: str, port: int = 9000, console_port: int | None = None
    ):
        """Start the test minio container or reuse an existing suitable one.
        Returns container object.

        Args:
            client: Docker client
            container_name: Name for the container
            port: External port to expose Minio API (default: 9000)
            console_port: External port for Minio console (default: port + 90)

        Note: Inside the container, Minio always listens on port 9000 for API and 9001 for console.
        The port parameters control the external host ports that map to these internal ports.
        """
        if console_port is None:
            console_port = port + 90

        # Try existing named container
        try:
            existing = client.containers.get(container_name)
            if existing.status == "running":
                return existing
            else:
                # remove stopped container to avoid conflicts
                with contextlib.suppress(Exception):
                    existing.remove()
        except docker.errors.NotFound:
            pass

        # Start new container - no fallback to avoid test isolation issues
        # Map container's internal ports (9000 for API, 9001 for console) to external ports
        container = client.containers.run(
            MINIO_IMAGE,
            command="server /data --console-address :9001",  # Internal ports: 9000 (API), 9001 (console)
            ports={"9000/tcp": port, "9001/tcp": console_port},  # Map internal -> external
            environment={"MINIO_ROOT_USER": "minioadmin", "MINIO_ROOT_PASSWORD": "minioadmin"},
            name=container_name,
            detach=True,
            remove=True,
        )
        return container

    @staticmethod
    @contextlib.contextmanager
    def minio_container_context(container_name: str, port: int = 9000) -> Generator[docker.models.containers.Container]:
        """Context manager for Minio container lifecycle.

        Handles container startup, readiness check, and cleanup.

        Args:
            container_name: Unique name for the container
            port: External port to expose Minio API (default: 9000)

        Yields:
            Container object

        Example:
            with MinioTestUtils.minio_container_context("test-container", 9000) as container:
                # Use container
                pass
        """
        client = MinioTestUtils.get_docker_client()
        if client is None:
            pytest.skip("Docker not available or not running")

        try:
            container = MinioTestUtils.start_or_reuse_minio(client, container_name, port=port)
            MinioTestUtils.wait_for_minio_ready(container.name, port=port)
            yield container
        finally:
            # Cleanup - stop AND remove container
            if client is not None:
                with contextlib.suppress(docker.errors.NotFound, docker.errors.APIError):
                    try:
                        container = client.containers.get(container_name)
                        container.stop(timeout=5)
                        container.remove(force=True)
                    except Exception:
                        pass

    @staticmethod
    def create_minio_fixture(container_name: str, port: int = 9000, yield_id: bool = True):
        """Factory function to create a minio_container pytest fixture.

        This eliminates code duplication across test files by providing a reusable
        fixture factory for Minio container management.

        Args:
            container_name: Unique name for the container (e.g., "photo-backup-test-xyz")
            port: External port to expose Minio API (default: 9000)
            yield_id: If True, yields container.id; if False, yields container object

        Returns:
            A pytest fixture function that manages the container lifecycle

        Example:
            class TestMyFeature:
                MINIO_PORT = 9002
                minio_container = MinioTestUtils.create_minio_fixture(
                    "photo-backup-my-test", port=MINIO_PORT
                )
        """

        @pytest.fixture
        def minio_fixture(self):
            """Manage Minio container lifecycle."""
            with MinioTestUtils.minio_container_context(container_name, port) as container:
                yield container.id if yield_id else container

        return minio_fixture
