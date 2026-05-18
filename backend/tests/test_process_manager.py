import subprocess
import sys
import time

from pipeline.process_manager import register_process, terminate_all_processes


def test_terminate_all_processes_kills_registered_process_group():
    proc = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(60)"],
        start_new_session=True,
    )
    register_process(proc, "test sleeper")

    killed = terminate_all_processes(timeout=1.0)

    assert killed == 1
    for _ in range(10):
        if proc.poll() is not None:
            break
        time.sleep(0.1)
    assert proc.poll() is not None
