"""FPL data ingestion scheduler.

Runs sync + embed every 4 hours, forever.
Logs to stdout AND scheduler.log. Handles failures gracefully.

Run with:  python -m scripts.scheduler
Stop with: Ctrl+C
"""
import logging
import sys
import subprocess
import time
import traceback
from datetime import datetime

INTERVAL_HOURS = 4
INTERVAL_SECONDS = INTERVAL_HOURS * 60 * 60

logging.basicConfig(
    filename="scheduler.log",
    level=logging.INFO,
    format="%(asctime)s %(message)s",
)


def log(msg: str) -> None:
    """Timestamped log line to stdout and to scheduler.log."""
    print(f"[{datetime.now().isoformat(timespec='seconds')}] {msg}", flush=True)
    logging.info(msg)


def run_once() -> None:
    """One full cycle: sync then embed. Raises on failure."""
    log("sync starting")
    subprocess.run([sys.executable, "-m", "scripts.sync"], check=True)
    log("sync complete")

    log("embed starting")
    subprocess.run([sys.executable, "-m", "scripts.embed"], check=True)
    log("embed complete")


def main() -> None:
    log(f"scheduler started — interval {INTERVAL_HOURS}h")
    while True:
        try:
            run_once()
        except subprocess.CalledProcessError as exc:
            log(f"cycle failed: subprocess returned {exc.returncode} — will retry next cycle")
        except Exception as exc:
            log(f"FATAL: {type(exc).__name__}: {exc}")
            traceback.print_exc()
            logging.exception("fatal error — exiting")
            log("scheduler exiting — fix the bug and restart")
            return

        log(f"sleeping {INTERVAL_HOURS}h until next cycle")
        time.sleep(INTERVAL_SECONDS)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("scheduler stopped by user")