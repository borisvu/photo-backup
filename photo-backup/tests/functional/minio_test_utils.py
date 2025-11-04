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
    def wait_for_minio_ready(container_name: str, max_attempts: int = 30) -> None:
        """Block until Minio is ready to accept commands or raise via pytest.fail."""
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
                        "http://localhost:9000",
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
    def start_or_reuse_minio(client: docker.DockerClient, container_name: str):
        """Start the test minio container or reuse an existing suitable one.
        Returns (container, started_by_fixture: bool).
        """
        # Try existing named container
        try:
            existing = client.containers.get(container_name)
            if existing.status == "running":
                return existing, False
            else:
                # remove stopped container to avoid conflicts
                with contextlib.suppress(Exception):
                    existing.remove()
        except docker.errors.NotFound:
            pass

        # Try generic "minio" container if ports busy
        try:
            container = client.containers.run(
                "minio/minio:latest",
                command="server /data --console-address :9001",
                ports={"9000/tcp": 9000, "9001/tcp": 9001},
                environment={"MINIO_ROOT_USER": "minioadmin", "MINIO_ROOT_PASSWORD": "minioadmin"},
                name=container_name,
                detach=True,
                remove=True,
            )
            return container, True
        except docker.errors.APIError as e:
            msg = str(e)
            if "port is already allocated" in msg or "Bind for" in msg:
                try:
                    reuse = client.containers.get("minio")
                    if reuse.status == "running":
                        return reuse, False
                except docker.errors.NotFound:
                    pass
            raise
