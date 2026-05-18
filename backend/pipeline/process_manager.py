"""Track and terminate subprocesses launched by long-running backend jobs."""

from __future__ import annotations

import logging
import os
import signal
import subprocess
import threading
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ManagedProcess:
    process: subprocess.Popen
    label: str


_lock = threading.Lock()
_processes: dict[int, ManagedProcess] = {}


def register_process(process: subprocess.Popen, label: str) -> None:
    """Register a subprocess so the dev dashboard can kill it later."""
    with _lock:
        _processes[process.pid] = ManagedProcess(process=process, label=label)
    logger.debug("Registered subprocess %s (%s)", process.pid, label)


def unregister_process(process: subprocess.Popen) -> None:
    """Remove a subprocess from tracking."""
    with _lock:
        _processes.pop(process.pid, None)
    logger.debug("Unregistered subprocess %s", process.pid)


def terminate_process_group(process: subprocess.Popen, label: str, timeout: float = 2.0) -> bool:
    if process.poll() is not None:
        return False

    logger.warning("Terminating subprocess %s (%s)", process.pid, label)
    if os.name == "posix":
        try:
            os.killpg(os.getpgid(process.pid), signal.SIGTERM)
        except ProcessLookupError:
            return False
    else:
        process.terminate()

    try:
        process.wait(timeout=timeout)
        return True
    except subprocess.TimeoutExpired:
        logger.warning("Subprocess %s (%s) ignored SIGTERM; killing", process.pid, label)
        if os.name == "posix":
            try:
                os.killpg(os.getpgid(process.pid), signal.SIGKILL)
            except ProcessLookupError:
                return True
        else:
            process.kill()
        process.wait(timeout=timeout)
        return True


def terminate_all_processes(timeout: float = 2.0) -> int:
    """Terminate all currently tracked subprocess groups."""
    with _lock:
        managed = list(_processes.values())

    killed = 0
    for item in managed:
        try:
            if terminate_process_group(item.process, item.label, timeout):
                killed += 1
        finally:
            unregister_process(item.process)

    if killed:
        logger.warning("Terminated %d tracked subprocess group(s)", killed)
    return killed


def run_tracked(
    args: Sequence[str],
    *,
    label: str,
    timeout: float | None = None,
    **kwargs: Any,
) -> subprocess.CompletedProcess[str]:
    """Run a subprocess with process-group tracking and subprocess.run-like output."""
    kwargs.setdefault("text", True)
    kwargs.setdefault("start_new_session", os.name == "posix")
    capture_output = kwargs.pop("capture_output", False)
    if capture_output:
        kwargs.setdefault("stdout", subprocess.PIPE)
        kwargs.setdefault("stderr", subprocess.PIPE)

    process = subprocess.Popen(args, **kwargs)
    register_process(process, label)
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        terminate_process_group(process, label, 2.0)
        stdout, stderr = process.communicate()
        raise
    finally:
        unregister_process(process)

    return subprocess.CompletedProcess(args, process.returncode, stdout, stderr)
