import contextlib
import subprocess
import time

import docker


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
    def wait_for_minio_ready(container_name: str, port: int = 9000, max_attempts: int = 30) -> None:  # noqa: ARG004
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
            "minio/minio:latest",
            command="server /data --console-address :9001",  # Internal ports: 9000 (API), 9001 (console)
            ports={"9000/tcp": port, "9001/tcp": console_port},  # Map internal -> external
            environment={"MINIO_ROOT_USER": "minioadmin", "MINIO_ROOT_PASSWORD": "minioadmin"},
            name=container_name,
            detach=True,
            remove=True,
        )
        return container
