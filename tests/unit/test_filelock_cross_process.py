import subprocess
import sys

SNIPPET = r"""
import sys, time
from filelock import FileLock
lock_path, log_path, name = sys.argv[1:4]
with FileLock(lock_path):
    with open(log_path, "a", encoding="utf-8") as fh:
        fh.write(f"{name} start {time.time()}\n")
    time.sleep(0.6)
    with open(log_path, "a", encoding="utf-8") as fh:
        fh.write(f"{name} end {time.time()}\n")
"""


def test_filelock_cross_process(tmp_path):
    lock, log = tmp_path / "claude.lock", tmp_path / "log.txt"
    procs = [subprocess.Popen([sys.executable, "-c", SNIPPET, str(lock), str(log), n]) for n in ("a", "b")]
    assert all(p.wait(timeout=30) == 0 for p in procs)
    events = [line.split() for line in log.read_text(encoding="utf-8").splitlines()]
    # Sin solapamiento: el orden debe ser start/end/start/end del mismo proceso por parejas.
    assert [e[1] for e in events] == ["start", "end", "start", "end"]
    assert events[0][0] == events[1][0] and events[2][0] == events[3][0]
    assert float(events[2][2]) >= float(events[1][2])
