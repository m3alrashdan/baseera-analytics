from __future__ import annotations

import argparse
import signal
import time

from .config import load_settings
from .database import build_engine, build_session_factory
from .jobs import claim_next_job, execute_job, recover_interrupted_jobs


def main() -> None:
    parser = argparse.ArgumentParser(description="Process BASEERA's persisted job queue")
    parser.add_argument("--once", action="store_true", help="Process at most one job, then exit")
    args = parser.parse_args()
    settings = load_settings()
    engine = build_engine(settings.database_url)
    factory = build_session_factory(engine)
    stopping = False

    def stop(*_: object) -> None:
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    with factory() as db:
        recover_interrupted_jobs(db)
    while not stopping:
        with factory() as db:
            job = claim_next_job(db)
            if job is not None:
                execute_job(db, job)
                if args.once:
                    break
                continue
        if args.once:
            break
        time.sleep(0.5)
    engine.dispose()


if __name__ == "__main__":
    main()
