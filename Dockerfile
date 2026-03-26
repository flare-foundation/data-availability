FROM python:3.14-slim-trixie@sha256:fb83750094b46fd6b8adaa80f66e2302ecbe45d513f6cece637a841e1025b4ca AS builder

COPY --from=ghcr.io/astral-sh/uv:0.10.8 /uv /uvx /bin/

WORKDIR /app
COPY pyproject.toml uv.lock ./

ARG DEV=false
# avoid symlinks that break when copying between stages
ENV UV_LINK_MODE=copy
# install outside /app so local volume mounts don't shadow the venv
ENV UV_PROJECT_ENVIRONMENT=/opt/venv
RUN if [ "$DEV" = "true" ]; then \
      uv sync --locked; \
    else \
      uv sync --locked --no-dev; \
    fi

FROM python:3.14-slim-trixie@sha256:fb83750094b46fd6b8adaa80f66e2302ecbe45d513f6cece637a841e1025b4ca AS final

ARG DEV=false
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl \
      $([ "$DEV" = "true" ] && echo gosu) && \
    rm -rf /var/lib/apt/lists/*

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN addgroup --gid 10001 app && adduser --uid 10001 --ingroup app --disabled-password app

WORKDIR /app
COPY --from=builder /opt/venv /opt/venv
COPY . /app

ENV PATH="/opt/venv/bin:/app/docker/bin:${PATH}"

RUN chown -R 10001:10001 /app

EXPOSE 8000

USER app

CMD ["django-gunicorn"]
