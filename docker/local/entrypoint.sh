#!/usr/bin/env bash

set -eu

dirs=(
    "/appdata/media"
)

if [[ ${USER_UID:+x} != "x" ]] || [[ ${USER_GID:+x} != "x" ]]; then
    # using docker desktop
    echo "Assuming Docker Desktop. Not changing permissions"
    echo "Running 'exec $@'"
    exec "$@"
else
    echo "Assuming not Docker Desktop. Changing permissions for specified folders"
    # not using docker desktop
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
fi
