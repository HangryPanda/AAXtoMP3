# Docker Cheat Sheet

This document provides a quick reference for Docker commands used in the Audible Library React project.

## Environments

*   **Production/Stable:** Uses `docker-compose.yml` (default). Images are optimized for size and performance.
*   **Development:** Uses `docker-compose.dev.yml`. Enables hot-reloading for API (FastAPI) and Web (Next.js) and mounts local source code.

## Common Commands

### Starting & Stopping

| Action | Production Command | Development Command | Description |
| :--- | :--- | :--- | :--- |
| **Start All** | `docker-compose up -d` | `docker-compose -f docker-compose.dev.yml up -d` | Starts all services in detached mode (background). |
| **Stop All** | `docker-compose down` | `docker-compose -f docker-compose.dev.yml down` | Stops and removes containers and networks. |
| **Stop & Volume** | `docker-compose down -v` | `docker-compose -f docker-compose.dev.yml down -v` | Stops all *and* deletes database volumes (resets DB). |
| **Rebuild** | `docker-compose up -d --build` | `docker-compose -f docker-compose.dev.yml up -d --build` | Rebuilds images before starting (use if Dockerfile changed). |

### Logs

| Action | Production Command | Development Command | Description |
| :--- | :--- | :--- | :--- |
| **All Logs** | `docker-compose logs -f` | `docker-compose -f docker-compose.dev.yml logs -f` | Follows logs from all containers. |
| **API Logs** | `docker-compose logs -f api` | `docker-compose -f docker-compose.dev.yml logs -f api` | Follows backend API logs. |
| **Web Logs** | `docker-compose logs -f web` | `docker-compose -f docker-compose.dev.yml logs -f web` | Follows frontend Web logs. |
| **DB Logs** | `docker-compose logs -f postgres` | `docker-compose -f docker-compose.dev.yml logs -f postgres` | Follows PostgreSQL logs. |

### Shell Access

To run commands inside a running container:

| Service | Production Container | Development Container | Command |
| :--- | :--- | :--- | :--- |
| **API** | `docker exec -it audible-api bash` | `docker exec -it audible-api-dev bash` | Open shell in API container. |
| **Web** | `docker exec -it audible-web sh` | `docker exec -it audible-web-dev sh` | Open shell in Web container. |
| **DB** | `docker exec -it audible-postgres bash` | `docker exec -it audible-postgres-dev bash` | Open shell in DB container. |

### Database Maintenance

**Access psql (PostgreSQL CLI):**

*   **Production:** `docker exec -it audible-postgres psql -U audible -d audible_db`
*   **Development:** `docker exec -it audible-postgres-dev psql -U audible -d audible_db`

**Common SQL Commands:**
*   `\dt` - List tables.
*   `\d books` - Describe "books" table schema.
*   `select * from books limit 5;` - View first 5 books.
*   `delete from books;` - Clear books table (Be careful!).

### Pruning (Cleanup)

*   `docker system prune -a` - Remove all unused containers, networks, images (both dangling and unreferenced). **Use with caution.**
*   `docker volume prune` - Remove all unused local volumes. **WARNING: Deletes database data.**

## Service details

### API Service (`api`)
*   **Port:** 8000
*   **Healthcheck:** `curl http://localhost:8000/health/live`
*   **Mounts:**
    *   `/data/downloads` -> Host download directory
    *   `/data/converted` -> Host converted directory
    *   `/audible-config` -> Host `~/.audible` (for auth)

### Web Service (`web`)
*   **Port:** 3000
*   **Healthcheck:** `wget http://localhost:3000/api/health`
*   **Dependencies:** Waits for `api` to be healthy before starting.

### Postgres Service (`postgres`)
*   **Port:** 5432 (Exposed to host)
*   **User/Pass:** `audible` / `password` (default)
*   **Database:** `audible_db`
