# CI/CD: деплой на VPS (GitHub Actions + SSH)

После миграции сервера депой снова идёт из GitHub: workflow **`.github/workflows/deploy.yml`** по `push` в `main` и вручную (**Actions → Deploy VPS → Run workflow**).

## Два разных SSH-ключа (не путать)

| Ключ | Где приватный | Где публичный | Назначение |
|------|----------------|---------------|------------|
| **Deploy → VPS** | Secret `DEPLOY_SSH_KEY` в GitHub | `~/.ssh/authorized_keys` на VPS | Раннер GitHub подключается к серверу и запускает скрипт |
| **VPS → GitHub** | Только на VPS (например `~/.ssh/gh_auto_concierge_deploy`) | **Deploy keys** репозитория (read-only) | `git fetch` / `git pull` с GitHub на приватный репо |

## Секреты репозитория (Settings → Secrets and variables → Actions)

| Secret | Обязательно | Пример |
|--------|-------------|--------|
| `DEPLOY_HOST` | да | `152.53.227.37` |
| `DEPLOY_USER` | да | `root` |
| `DEPLOY_SSH_KEY` | да | приватный PEM (весь ключ, включая `BEGIN`/`END`) |
| `DEPLOY_PATH` | да | `/opt/auto-concierge-v1` |
| `DEPLOY_BRANCH` | нет | пусто = ветка `main` (см. `scripts/deploy-vps.sh`) |

Нестандартный SSH-порт: в workflow по умолчанию **22**. При необходимости добавь в `deploy.yml` параметр `port:` у `appleboy/ssh-action` (и не храни порт в открытом виде без нужды).

## Одноразовая настройка VPS

### 1) Ключ для GitHub Actions → VPS

На своей машине или на VPS:

```bash
ssh-keygen -t ed25519 -f ./gha_vps_deploy -C "github-actions-auto-concierge" -N ""
```

- Содержимое **`gha_vps_deploy.pub`** → в **`authorized_keys`** пользователя деплоя на VPS (часто `root`).
- Содержимое **`gha_vps_deploy`** (приватный) → в GitHub secret **`DEPLOY_SSH_KEY`**.

### 2) Доступ VPS → GitHub для `git pull`

- **Публичный репозиторий:** достаточно `git clone https://github.com/solomonczyk/auto-concierge-v1.git` — отдельный ключ не нужен.
- **Приватный репозиторий:** на VPS создай ключ и добавь как **Deploy key (read-only)** в настройках репо.

```bash
ssh-keygen -t ed25519 -f ~/.ssh/gh_auto_concierge_deploy -N ""
```

Публичный ключ → GitHub → **Settings → Deploy keys → Add deploy key** (только **Read**). В `~/.ssh/config` на VPS:

```
Host github.com
  HostName github.com
  User git
  IdentityFile ~/.ssh/gh_auto_concierge_deploy
  IdentitiesOnly yes
```

### 3) Каталог приложения как git clone

Если сейчас `/opt/auto-concierge-v1` **без `.git`**:

```bash
sudo mv /opt/auto-concierge-v1 /opt/auto-concierge-v1.bak.$(date +%Y%m%d)
sudo git clone https://github.com/solomonczyk/auto-concierge-v1.git /opt/auto-concierge-v1
# приватный репо: git clone git@github.com:solomonczyk/auto-concierge-v1.git ...
sudo cp /opt/auto-concierge-v1.bak.*/.env /opt/auto-concierge-v1/.env
# при необходимости: sudo cp .../docker-compose.override.yml ...
cd /opt/auto-concierge-v1 && git checkout main
```

Убедись, что **`postgres_data`** и данные БД не потеряны: в текущем `docker-compose.yml` том `postgres_data` — при смене каталога **имя проекта compose** может смениться и подняться **пустой** том. Безопасный вариант:

- либо перенести volume / данные по [документации Docker](https://docs.docker.com/storage/volumes/),
- либо не переносить каталог, а выполнить **`git init`** в существующем `/opt/auto-concierge-v1`, добавить `origin`, `fetch`, `reset --hard` (один раз сверить с репо и бэкап `.env`).

### 4) Права на скрипт

```bash
chmod +x /opt/auto-concierge-v1/scripts/deploy-vps.sh
```

### 5) Проверка вручную на VPS

```bash
cd /opt/auto-concierge-v1
bash scripts/deploy-vps.sh
```

## Что делает `scripts/deploy-vps.sh`

1. `git fetch` + `git reset --hard origin/<branch>` — **локальные правки на сервере затираются**.
2. `docker-compose` (или `docker compose`) **build** `backend`, `worker`, `frontend`.
3. `up -d`.
4. `alembic upgrade head` в контейнере `backend`.

Переменные окружения: **`COMPOSE_FILE`** (по умолчанию `docker-compose.yml`), **`DEPLOY_BRANCH`** (по умолчанию `main`).

## Замечания

- Пуш в `main` сразу запускает деплой; при желании оставь только `workflow_dispatch`, убрав триггер `push` в `deploy.yml`.
- Job **E2E** и **Deploy** независимы; при необходимости добавь защиту ветки `main` и required checks перед merge.
