"""Docker-managed database commands."""

from __future__ import annotations

import shutil
import subprocess
import time
from typing import Annotated

import typer
from rich.console import Console

db_app = typer.Typer(help="Manage the local database container.")
console = Console()

_CONTAINER_NAME = "codex-graph-db"
_IMAGE = "ghcr.io/fmueller/codex-graph-db:latest"
_DEFAULT_PORT = 5432


def _docker_available() -> bool:
    return shutil.which("docker") is not None


def _container_state() -> str | None:
    """Return 'running', 'exited', etc. or None if container not found."""
    result = subprocess.run(
        ["docker", "inspect", "-f", "{{.State.Status}}", _CONTAINER_NAME],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def _wait_for_ready(port: int, timeout: int = 30) -> bool:
    """Wait for postgres to accept connections."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = subprocess.run(
            ["docker", "exec", _CONTAINER_NAME, "pg_isready", "-U", "postgres", "-p", str(port)],
            capture_output=True,
        )
        if result.returncode == 0:
            return True
        time.sleep(1)
    return False


@db_app.command("start")
def start(
    port: Annotated[int, typer.Option(help="Host port to map.")] = _DEFAULT_PORT,
) -> None:
    """Pull the database image and start the container."""
    if not _docker_available():
        console.print("[red]Docker is not installed or not in PATH.[/red]")
        console.print("Install Docker: https://docs.docker.com/get-docker/")
        raise typer.Exit(1)

    state = _container_state()
    if state == "running":
        console.print(f"[green]Container {_CONTAINER_NAME} is already running.[/green]")
        return
    if state == "exited":
        console.print(f"Restarting stopped container {_CONTAINER_NAME}...")
        subprocess.run(["docker", "start", _CONTAINER_NAME], check=True)
    else:
        console.print(f"Pulling {_IMAGE}...")
        subprocess.run(["docker", "pull", _IMAGE], check=True)
        console.print("Starting container...")
        subprocess.run(
            [
                "docker",
                "run",
                "-d",
                "--name",
                _CONTAINER_NAME,
                "-p",
                f"{port}:5432",
                "-e",
                "POSTGRES_PASSWORD=postgres",
                _IMAGE,
            ],
            check=True,
        )

    console.print("Waiting for database to be ready...")
    if _wait_for_ready(port):
        console.print(f"[green]Database ready on localhost:{port}[/green]")
    else:
        console.print("[red]Database did not become ready in time.[/red]")
        raise typer.Exit(1)


@db_app.command("stop")
def stop() -> None:
    """Stop and remove the database container."""
    if not _docker_available():
        console.print("[red]Docker is not installed or not in PATH.[/red]")
        raise typer.Exit(1)

    state = _container_state()
    if state is None:
        console.print(f"Container {_CONTAINER_NAME} not found.")
        return

    console.print(f"Stopping {_CONTAINER_NAME}...")
    subprocess.run(["docker", "stop", _CONTAINER_NAME], check=True)
    subprocess.run(["docker", "rm", _CONTAINER_NAME], check=True)
    console.print("[green]Container stopped and removed.[/green]")


@db_app.command("status")
def status() -> None:
    """Show the database container state."""
    if not _docker_available():
        console.print("[red]Docker is not installed or not in PATH.[/red]")
        raise typer.Exit(1)

    state = _container_state()
    if state is None:
        console.print(f"Container {_CONTAINER_NAME}: [yellow]not found[/yellow]")
    elif state == "running":
        console.print(f"Container {_CONTAINER_NAME}: [green]{state}[/green]")
    else:
        console.print(f"Container {_CONTAINER_NAME}: [yellow]{state}[/yellow]")
