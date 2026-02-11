# tgprikol

Телеграм-бот для продажи MTProto прокси + контейнер с telemt.

## Быстрый старт
1) Скопируйте пример переменных окружения и заполните секреты:
   ```
   cp .env.example .env
   ```
2) Не храните боевые `data/users.db` и `data/telemt.toml` в Git — они игнорируются в `.gitignore`. Создайте их заново перед запуском или примонтируйте снаружи.
3) Запустите:
   ```
   docker compose up -d
   ```

## Деплой (docker compose)

Клонирование репозитория:
```bash
git clone https://github.com/qaserdcesen/tgprikol.git
cd tgprikol
```

Установка Docker + Compose (Ubuntu/Debian):
```bash
sudo apt update
sudo apt install -y docker.io docker-compose-plugin
sudo systemctl enable --now docker
sudo usermod -aG docker "$USER"   # перелогиньтесь после этой команды
```

Подготовка (один раз):
```bash
cp .env.example .env                 # заполните токены и цены
sed -i 's/{{ADMIN_SECRET}}/your_secret_here/' data/telemt.toml
rm -f data/users.db                  # при первом старте sqlite создаст файл сам
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

Просмотр логов бота:
```bash
docker compose logs -f bot
```

Обновление версии:
```bash
docker compose pull || docker compose build
docker compose up -d
```

## Безопасность
- Не коммитьте токены и файл `data/telemt.toml` с секренами.
- У бота есть доступ к docker.sock — оставляйте его только если нужно управлять контейнером, иначе уберите монтирование.
