#!/usr/bin/env bash
set -eu

# no UID/GID set (e.g. docker desktop) — run directly
if [[ ${USER_UID:+x} != "x" ]] || [[ ${USER_GID:+x} != "x" ]]; then
    exec "$@"
fi

exec gosu "$USER_UID:$USER_GID" "$@"
