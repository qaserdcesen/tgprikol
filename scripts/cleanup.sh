#!/bin/sh
DB="/app/data/users.db"
CONFIG="/app/data/telemt.toml"
COMPOSE="/app/docker-compose.yml"

expired=$(sqlite3 "$DB" "SELECT telegram_id, 'user_'||telegram_id FROM users WHERE expires_at < date('now')")
echo "$expired" | while IFS='|' read -r uid username; do
    [ -z "$uid" ] && continue
    sed -i "/^$username = /d" "$CONFIG"
    sqlite3 "$DB" "DELETE FROM users WHERE telegram_id = $uid"
done
docker compose -f "$COMPOSE" restart telemt
