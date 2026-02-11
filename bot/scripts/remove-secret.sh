#!/bin/sh
USERNAME=$1
CONFIG_FILE="/app/data/telemt.toml"
TELEMT_CONTAINER=${TELEMT_CONTAINER:-telemt}

sed -i "/^$USERNAME = /d" "$CONFIG_FILE"
docker restart "$TELEMT_CONTAINER" >/dev/null
