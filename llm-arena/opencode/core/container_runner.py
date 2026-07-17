"""Container runner for managing Docker containers per model.

Each model runs in its own isolated Docker container with:
- Fixed OpenCode version
- Fixed agent configuration
- Fixed system prompts
- Isolated workspace
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import docker
from docker.errors import DockerException, NotFound


@dataclass
class ContainerConfig:
    """Configuration for a model container."""
    model_id: str
    model_provider: str
    model_version: str
    api_key: str
    max_steps: int = 100
    timeout: int = 300
    memory_limit: str = "2g"
    cpu_limit: float = 2.0
    network: str = "opencode-network"
    image: str = "opencode-model:latest"
    environment: dict = field(default_factory=dict)


@dataclass
class RunResult:
    """Result of a container run."""
    run_id: str
    status: str  # "success", "failed", "timeout"
    exit_code: int
    stdout: str
    stderr: str
    duration: float
    workspace_path: str


class ContainerRunner:
    """Manages Docker containers for model runs.

    Each run creates a fresh container with:
    - Clean workspace
    - Fixed environment
    - Resource limits
    - Network isolation
    """

    def __init__(self, docker_url: Optional[str] = None):
        """Initialize the container runner.

        Args:
            docker_url: Docker daemon URL (default: from environment / Docker Desktop)
        """
        if docker_url:
            self.client = docker.DockerClient(base_url=docker_url)
        else:
            self.client = docker.from_env()

    def create_container(
        self,
        config: ContainerConfig,
        task_path: str,
        workspace_path: str,
    ) -> str:
        """Create a new container for a model run.

        Args:
            config: Container configuration
            task_path: Path to the task files
            workspace_path: Path to the workspace

        Returns:
            Container ID
        """
        # Prepare environment variables (include API key from frontend / request)
        provider_upper = (config.model_provider or "anthropic").upper()
        env = {
            "MODEL_ID": config.model_id,
            "MODEL_PROVIDER": config.model_provider,
            "MODEL_VERSION": config.model_version,
            "MAX_STEPS": str(config.max_steps),
            "TIMEOUT": str(config.timeout),
            **config.environment,
        }
        if config.api_key:
            env[f"{provider_upper}_API_KEY"] = config.api_key
            env["API_KEY"] = config.api_key
            # Aliases so OpenAI-compatible clients inside the runner can find the key
            if provider_upper in ("DEEPSEEK", "CUSTOM", "OPENAI", "MIMO"):
                env.setdefault("OPENAI_API_KEY", config.api_key)
            if provider_upper == "GOOGLE":
                env.setdefault("GOOGLE_API_KEY", config.api_key)
            if provider_upper == "ANTHROPIC":
                env.setdefault("ANTHROPIC_API_KEY", config.api_key)
            if provider_upper == "MIMO":
                env.setdefault("MIMO_API_KEY", config.api_key)
                env.setdefault(
                    "MIMO_BASE_URL",
                    config.environment.get("BASE_URL")
                    or config.environment.get("OPENAI_BASE_URL")
                    or "https://api.xiaomimimo.com/v1",
                )
                env.setdefault(
                    "OPENAI_BASE_URL",
                    env["MIMO_BASE_URL"],
                )
            if provider_upper == "DEEPSEEK":
                env.setdefault("DEEPSEEK_API_KEY", config.api_key)
                env.setdefault("OPENAI_BASE_URL", "https://api.deepseek.com/v1")

        # Prepare volumes
        volumes = {
            task_path: {
                "bind": "/workspace/task",
                "mode": "ro",  # Read-only for task files
            },
            workspace_path: {
                "bind": "/workspace/src",
                "mode": "rw",  # Read-write for code
            },
        }

        # Create container
        container = self.client.containers.run(
            image=config.image,
            command="python runner.py",
            environment=env,
            volumes=volumes,
            network=config.network,
            mem_limit=config.memory_limit,
            cpu_quota=int(config.cpu_limit * 100000),
            detach=True,
            auto_remove=False,
            labels={
                "opencode.model_id": config.model_id,
                "opencode.run_id": str(uuid.uuid4()),
            },
        )

        return container.id

    def run_task(
        self,
        config: ContainerConfig,
        task_path: str,
        timeout: Optional[int] = None,
    ) -> RunResult:
        """Run a task in a container and return results.

        Args:
            config: Container configuration
            task_path: Path to the task files
            timeout: Override timeout in seconds

        Returns:
            RunResult with execution details
        """
        run_id = str(uuid.uuid4())
        workspace_path = tempfile.mkdtemp(prefix=f"opencode_{run_id}_")

        try:
            # Create container
            container_id = self.create_container(
                config=config,
                task_path=task_path,
                workspace_path=workspace_path,
            )

            container = self.client.containers.get(container_id)

            # Wait for completion with timeout
            actual_timeout = timeout or config.timeout
            result = container.wait(timeout=actual_timeout)

            # Get logs
            stdout = container.logs(stdout=True, stderr=False).decode("utf-8")
            stderr = container.logs(stdout=False, stderr=True).decode("utf-8")

            # Get run duration from container stats
            stats = container.stats(stream=False)
            duration = stats.get("read", "0s")  # Simplified

            # Clean up container
            container.remove(force=True)

            return RunResult(
                run_id=run_id,
                status="success" if result["StatusCode"] == 0 else "failed",
                exit_code=result["StatusCode"],
                stdout=stdout,
                stderr=stderr,
                duration=0.0,  # Would calculate from actual timestamps
                workspace_path=workspace_path,
            )

        except subprocess.TimeoutExpired:
            # Kill container on timeout
            try:
                container = self.client.containers.get(container_id)
                container.kill()
                container.remove(force=True)
            except Exception:
                pass

            return RunResult(
                run_id=run_id,
                status="timeout",
                exit_code=-1,
                stdout="",
                stderr="Task exceeded timeout",
                duration=float(actual_timeout),
                workspace_path=workspace_path,
            )

        except Exception as e:
            return RunResult(
                run_id=run_id,
                status="failed",
                exit_code=-1,
                stdout="",
                stderr=str(e),
                duration=0.0,
                workspace_path=workspace_path,
            )

    def cleanup(self, run_id: Optional[str] = None) -> None:
        """Clean up containers and workspaces.

        Args:
            run_id: Specific run to clean up, or None for all
        """
        if run_id:
            # Clean up specific run
            containers = self.client.containers.list(
                filters={"label": f"opencode.run_id={run_id}"},
                all=True,
            )
            for container in containers:
                container.remove(force=True)
        else:
            # Clean up all opencode containers
            containers = self.client.containers.list(
                filters={"label": "opencode.model_id"},
                all=True,
            )
            for container in containers:
                container.remove(force=True)

    def get_container_logs(self, container_id: str) -> str:
        """Get logs from a running container.

        Args:
            container_id: Docker container ID

        Returns:
            Container logs as string
        """
        try:
            container = self.client.containers.get(container_id)
            return container.logs().decode("utf-8")
        except NotFound:
            return "Container not found"
        except Exception as e:
            return f"Error getting logs: {e}"

    def stream_logs(self, container_id: str):
        """Stream logs from a running container.

        Args:
            container_id: Docker container ID

        Yields:
            Log lines as they are produced
        """
        try:
            container = self.client.containers.get(container_id)
            for line in container.logs(stream=True, follow=True):
                yield line.decode("utf-8").strip()
        except Exception as e:
            yield f"Error streaming logs: {e}"
