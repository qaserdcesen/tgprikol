#!/bin/sh
SECRET=$1
USERNAME=$2
DOMAIN=${3:-"1c.ru"}
CONFIG_FILE="/app/data/telemt.toml"
TELEMT_CONTAINER=${TELEMT_CONTAINER:-telemt}

sed -i "/\[access.users\]/a $USERNAME = \"$SECRET\"" "$CONFIG_FILE"
docker restart "$TELEMT_CONTAINER" >/dev/null

IP=$(curl -s -4 ifconfig.me)
HEX_DOMAIN=$(echo -n "$DOMAIN" | od -A n -t x1 -w256 | sed 's/ //g')
HEX_LEN=$(printf "%02x" ${#DOMAIN})
LINK="tg://proxy?server=$IP&port=443&secret=ee${SECRET}${HEX_LEN}${HEX_DOMAIN}"
echo "$LINK"
