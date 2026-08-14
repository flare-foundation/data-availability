import os


def post_fork(server, worker):
    """Initialize OpenTelemetry inside each worker process after Gunicorn forks."""
    worker_class_str = str(
        getattr(server.cfg, "worker_class", worker.__class__.__name__)
    ).lower()
    is_gevent = "gevent" in worker_class_str

    if is_gevent:
        try:
            from gevent import monkey

            # gevent monkey patch must run before OTel monkey patch.
            monkey.patch_all()
            server.log.info(
                f"Worker {worker.pid}: Gevent worker class detected and monkey patch applied."
            )
        except ImportError:
            server.log.error(
                f"Worker {worker.pid}: Gevent worker specified, but 'gevent' module is not installed."
            )
        except Exception as e:
            server.log.error(
                f"Worker {worker.pid}: Gevent worker class specified, but monkey patch failed: {e}"
            )

    if os.environ.get("OTEL_ENABLED", "false").lower() == "true":
        try:
            from project.telemetry import setup_telemetry

            setup_telemetry()
            server.log.info(f"Worker {worker.pid}: OpenTelemetry initialized.")
        except Exception as e:
            server.log.error(
                f"Worker {worker.pid}: Failed to initialize OpenTelemetry: {e}"
            )
