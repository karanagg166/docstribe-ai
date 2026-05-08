# Docker + Lint Commands

Use this guide to run the full stack with Docker and manage common commands.

## 0. Where To Run Commands

Run all commands from project root:

`/Users/karanagg/Desktop/Projects/docstribe-ai`

If you run commands from another folder, Docker Compose may not find `docker-compose.yml`.

## 1. Validate Setup (Before Starting)

Validate compose file syntax:

```bash
docker compose config
```

See current status of containers:

```bash
docker compose ps
```

Check logs if something fails:

```bash
docker compose logs -f backend
docker compose logs -f frontend
```

## 2. Build Images (When To Use)

Use build when:
- Dockerfiles changed
- `requirements.txt` or `package.json`/`pnpm-lock.yaml` changed
- base dependencies changed

Build all services:

```bash
docker compose build
```

Build only backend or frontend:

```bash
docker compose build backend
docker compose build frontend
```

Rebuild without cache (if build is stuck/corrupted):

```bash
docker compose build --no-cache
```

## 3. Start Services (up / up -d)

Start and keep terminal attached (best for debugging):

```bash
docker compose up
```

Start in background (`-d` = detached mode):

```bash
docker compose up -d
```

Start specific services only:

```bash
docker compose up -d backend
```

Build and start in one command:

```bash
docker compose up --build
docker compose up -d --build
```

## 4. Stop vs Down (When To Use)

Stop containers but keep them for quick restart:

```bash
docker compose stop
```

Start again after stop:

```bash
docker compose start
```

Stop and remove containers/networks:

```bash
docker compose down
```

## 5. Restart / Recreate Quick Commands

Restart one service:

```bash
docker compose restart backend
```

Recreate backend after compose/env changes:

```bash
docker compose up -d --force-recreate backend
```

## 6. Run Commands Inside Containers (exec)

Backend shell:

```bash
docker compose exec backend sh
```

Frontend shell:

```bash
docker compose exec frontend sh
```

## 7. Frontend Lint + Type Commands (Next.js)

Since the frontend uses `pnpm`, we use `pnpm` instead of `npm`.

### Check lint errors (ESLint):

```bash
docker compose exec frontend pnpm run lint
```

### Check type errors (TypeScript):

```bash
docker compose exec frontend pnpm exec tsc --noEmit
```

Type errors cannot be auto-fixed — tsc tells you what is wrong and you fix them manually.

## 8. Recommended Daily Flow

1. `docker compose up -d`
2. `docker compose ps`
3. Run your code changes
4. Before pushing code, run lint + type checks:
   ```bash
   # Frontend
   docker compose exec frontend pnpm run lint
   docker compose exec frontend pnpm exec tsc --noEmit
   ```
5. Check logs if needed:
   ```bash
   docker compose logs -f backend
   docker compose logs -f frontend
   ```
6. End work with `docker compose stop` (or `docker compose down` if you want cleanup)

## 9. Project Structure

View your project structure (excluding noise folders):

```bash
tree -I 'node_modules|.next|__pycache__|.git|.venv|*.pyc|generated' --dirsfirst
```
