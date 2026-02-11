# tgprikol

Телеграм‑бот для продажи MTProto прокси + контейнер с telemt.

## Деплой (docker compose)

Клонирование репозитория:
```bash
git clone https://github.com/qaserdcesen/tgprikol.git
cd tgprikol
```

Установка Docker + Compose (Ubuntu/Debian):
```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
exec su -l $USER
```

```bash
cd ~/tgprikol
```

Подготовка (один раз):
```bash
mkdir -p data
cp env.example .env
nano .env
```

```bash
ADMIN_SECRET=$(openssl rand -hex 16)
sed "s/{{ADMIN_SECRET}}/$ADMIN_SECRET/" telemt/telemt.toml > data/telemt.toml
```

```bash
touch data/users.db
```

Сборка и запуск:
```bash
docker compose build
docker compose up -d
```

Проверка статуса:
```bash
docker compose ps
```

Логи бота:
```bash
docker compose logs -f bot
```

Обновление версии:
```bash
docker compose pull || docker compose build
docker compose up -d
```

Если видите `sqlite3.OperationalError: unable to open database file`, убедитесь, что каталог `data` существует, файл `data/users.db` создан на хосте (команда `touch data/users.db`), а в compose для бота и cleanup монтируется директория `./data:/app/data`.

Открыть порт 443 (если включён UFW):
```bash
sudo ufw allow 443/tcp
```

Сгенерировать ссылку на прокси для admin (использует ADMIN_SECRET из `data/telemt.toml`):
```bash
IP=$(curl -s -4 ifconfig.me)
DOMAIN=$(grep DEFAULT_DOMAIN .env | cut -d= -f2 | tr -d '"' || echo "1c.ru")
HEX_DOMAIN=$(echo -n "$DOMAIN" | od -A n -t x1 -w256 | sed 's/ //g')
HEX_LEN=$(printf "%02x" ${#DOMAIN})
echo "tg://proxy?server=$IP&port=443&secret=ee${ADMIN_SECRET}${HEX_LEN}${HEX_DOMAIN}"
```

## Безопасность
- Не коммитьте токены и файл `data/telemt.toml` с секретами.
- У бота есть доступ к docker.sock — оставляйте его только если нужно управлять контейнером, иначе уберите монтирование.


```
git pull
```
```
docker compose build bot cleanup
docker compose up -d
```
```
docker compose ps
docker compose logs -f bot
```
