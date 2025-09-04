from __future__ import annotations

import os

from worker.queue import RQContext  # noqa: F401 (kept for future enqueues)


def main() -> None:
    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    try:
        # Start a blocking RQ worker via CLI (compatible across RQ versions)
        import subprocess

        print("[worker] Starting RQ worker via CLI on default queue...")
        subprocess.run(["rq", "worker", "-u", redis_url, "default"], check=True)
    except Exception as e:  # pragma: no cover - optional
        print(f"[worker] Unable to start RQ worker: {e}")
        print("Install redis-server + python packages or adjust REDIS_URL.")
        return


if __name__ == "__main__":
    main()
