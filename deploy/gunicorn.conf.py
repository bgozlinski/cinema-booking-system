"""Gunicorn config. The child_exit hook lets prometheus_client clean up a
worker's metric files when it dies, so multiprocess aggregation stays correct.
Active only when PROMETHEUS_MULTIPROC_DIR is set (see entrypoint.sh)."""


def child_exit(server, worker):
    import os

    if os.environ.get("PROMETHEUS_MULTIPROC_DIR"):
        from prometheus_client import multiprocess

        multiprocess.mark_process_dead(worker.pid)
