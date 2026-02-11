#!/bin/sh
USERNAME=$1
CONFIG_FILE="/app/data/telemt.toml"
COMPOSE_FILE="/app/docker-compose.yml"

sed -i "/^$USERNAME = /d" "$CONFIG_FILE"
docker compose -f "$COMPOSE_FILE" restart telemt
