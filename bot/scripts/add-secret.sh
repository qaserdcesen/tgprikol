#!/bin/sh
SECRET=$1
USERNAME=$2
DOMAIN=${3:-"1c.ru"}
CONFIG_FILE="/app/data/telemt.toml"
COMPOSE_FILE="/app/docker-compose.yml"

sed -i "/\[access.users\]/a $USERNAME = \"$SECRET\"" "$CONFIG_FILE"
docker compose -f "$COMPOSE_FILE" restart telemt

IP=$(curl -s -4 ifconfig.me)
HEX_DOMAIN=$(echo -n "$DOMAIN" | od -A n -t x1 -w256 | sed 's/ //g')
HEX_LEN=$(printf "%02x" ${#DOMAIN})
LINK="tg://proxy?server=$IP&port=443&secret=ee${SECRET}${HEX_LEN}${HEX_DOMAIN}"
echo "$LINK"
