#!/bin/sh
set -eu

seed_dir=/root/.idapro
user_dir="${HOME:-/home/ubuntu}/.idapro"

mkdir -p "$user_dir"
for name in idapro.hexlic ida.reg ida-config.json; do
    if [ ! -e "$user_dir/$name" ] && [ -r "$seed_dir/$name" ]; then
        cp "$seed_dir/$name" "$user_dir/$name"
    fi
done

exec "$@"
