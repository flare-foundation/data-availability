#!/usr/bin/env bash

set -eu

dirs=(
    "/appdata/static"
    "/appdata/media"
)

for d in ${dirs[@]}; do
    if [[ -d "$d" ]] && [[ "$(stat -c '%u:%g' $d)" != "$USER_UID:$USER_GID" ]]; then
        # TODO:(matej) what if directory is owned but content is not?
        echo "Found not owned directory '$d'. Running `chown -R $USER_UID:$USER_GID $d`"
        chown -R "$USER_UID:$USER_GID" "$d"
    else
        echo "Specified directory '$d' not found"
        
    fi
done

echo "Running 'exec gosu $USER_UID:$USER_GID $@'"
exec gosu "$USER_UID:$USER_GID" "$@"
