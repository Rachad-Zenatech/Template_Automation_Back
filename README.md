# Enterprise Portal Backend Template (`Template_Automation_Back`)

Reference enterprise boilerplate backend providing a turnkey foundation for ZenaTech internal portals. Built on **FastAPI**, **PostgreSQL** (`asyncpg`), **FastMCP**, **Microsoft Entra ID OAuth 2.0**, **PBAC (Permission-Based Access Control)**, and zero-CPU **Server-Sent Events (SSE)**.

---

## System Architecture Diagram

```mermaid
flowchart TD
    subgraph ClientLayer [Client Consumers]
        FrontApp[Template React Frontend :6000]
        MCPClient[MCP AI Agents & Inspectors]
        ThirdParty[External REST Integrations]
    end

    subgraph APIGateway [FastAPI HTTP Engine :8900]
        CORS[CORS & Security Headers Middleware]
        RateLimit[In-Memory Sliding-Window Rate Limiter]
        AuthRouter[Auth & Microsoft SSO Router]
        RBACRouter[Users, Roles & PBAC Router]
        LogRouter[System & Audit Log Router]
        NotifRouter[Real-Time SSE Event Stream]
        ObsRouter[Health Checks & Telemetry]
        MCPEndpoint[FastMCP Protocol Server /mcp]
    end

    subgraph CoreServices [Service Layer]
        AuthService[Auth & Token Lifecycle Service]
        RBACService[Granular PBAC Authorization Engine]
        CacheService[L1 In-Memory Cache + PostgreSQL NOTIFY]
        AuditService[Audit Log & Action Differ]
        NotificationService[SSE Event Broadcaster & Queue]
        GeminiService[Google Gemini AI Integration]
    end

    subgraph DataPersistence [Database & State Layer]
        PG[(PostgreSQL asyncpg Connection Pool)]
        Alembic[Alembic Database Migration Engine]
    end

    FrontApp -->|REST API with HttpOnly Cookies| APIGateway
    FrontApp -->|Persistent EventSource Stream| NotifRouter
    MCPClient -->|Streamable HTTP /mcp| MCPEndpoint
    ThirdParty -->|Bearer Token API| APIGateway

    APIGateway --> RateLimit
    RateLimit --> CoreServices
    CoreServices --> CacheService
    CoreServices --> PG
    CacheService <-->|NOTIFY / LISTEN| PG
```

---

## Technologies & System Specifications

| Category | Technology | Description |
| :--- | :--- | :--- |
| **Framework & Engine** | [FastAPI](https://fastapi.tiangolo.com/), [Uvicorn](https://www.uvicorn.org/) | High-concurrency ASGI web framework running on port `8900` |
| **Language** | Python 3.12+ | Strongly typed with Pydantic v2 schemas and async event loops |
| **Database & Pooling** | [PostgreSQL](https://www.postgresql.org/), [asyncpg](https://github.com/MagicStack/asyncpg) | Direct binary wire protocol, synchronous pool manager `get_pool()`, atomic `UNNEST` batch queries |
| **Database Migrations**| [Alembic](https://alembic.sqlalchemy.org/) | Declarative schema revision management |
| **Model Context Protocol**| [FastMCP](https://github.com/jlowin/fastmcp), `mcp` SDK | Streamable HTTP endpoint (`/mcp`) exposing tools to Claude and Gemini AI agents |
| **Real-Time Streaming**| [Server-Sent Events (SSE)](https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events) | Event-driven async queues with 30s lightweight keepalive pings and automatic reconnect |
| **Authentication & SSO**| `Authlib`, `PyJWT`, `passlib`, `bcrypt` | Microsoft Entra ID (Azure AD) OAuth 2.0 PKCE and secure HttpOnly cookie sessions |
| **Authorization (PBAC)**| Custom PBAC Matrix | User -> Roles -> Group Actions (`VIEW`, `CREATE`, `EDIT`, `DELETE`) & Route Method Policies |
| **AI Integration** | [Google GenAI SDK](https://github.com/google/generative-ai-python) (`google-genai`) | Automated summaries, query expansion, and document insights |
| **Rate Limiting & Security**| Sliding Window Counter | Per-IP and per-user window throttling protecting sensitive auth routes |

---

<!-- project-structure:start -->
## Project Structure

```text
server.py             # FastAPI app: startup/shutdown, middleware, router registration
tools/                # HTTP routers (FastAPI APIRouter), grouped by feature
  shared/             # Auth, roles and permissions, logs, health/observability and search
    auth_router.py, log_router.py, observability.py
    rbac_router.py, search.py
  notifications/      # Notifications and messaging (SSE, RabbitMQ, MQTT, cross-portal events)
    notification_router.py
  microsoft_graph/    # Microsoft Graph (Entra users/org) client and background sync
    graph_router.py
services/             # Business logic, grouped by feature
  shared/             # Used by several features: auth, RBAC, caching, logging, audit, security
    audit_service.py, auth_service.py, cache_service.py
    logging_service.py, rbac_service.py, service_security_policy.py
  ai/                 # Gemini clients, assistant chat, guardrails, tracing, semantic cache, usage limits
    ai_guardrails.py, ai_observability.py, ai_usage_service.py
    assistant_chat_service.py, gemini_service.py, model_router.py
    semantic_cache.py
  notifications/      # Notifications and messaging (SSE, RabbitMQ, MQTT, cross-portal events)
    ceo_event_publisher.py, mqtt_presence.py, notification_service.py
    rabbitmq_service.py
  microsoft_graph/    # Microsoft Graph (Entra users/org) client and background sync
    graph_service.py, graph_sync_job.py
models/               # Pydantic request/response models, grouped by feature
  shared/             # Used by several features: users, roles, permissions, common types
    rbac_model.py
  notifications/      # Notifications and messaging (SSE, RabbitMQ, MQTT, cross-portal events)
    notification_model.py
mcp_tools/            # MCP server: registry, middleware, prompts; tools grouped by feature
    __init__.py (registry), middleware.py, prompts.py
  shared/             # Tools for several features: permissions and account lookups
    permissions.py
postgresql_db/        # database.py (asyncpg pool), schema_metadata.py, table scripts in schemas/
  schemas/            # setup_<feature>_schema.py: CREATE TABLE / migrations per feature
    notifications_schema.py, setup_ai_observability_schema.py, setup_graph_sync_schema.py
    setup_pbac_schema.py
alembic/              # Database migrations
scripts/              # Dev/ops scripts (seed, reset, pull prod data)
docs/                 # Longer design and integration docs
```

### Where new code goes

* **New feature `<x>`:** logic in `services/<x>/`, endpoints in `tools/<x>/<x>_router.py`, models in `models/<x>/`, MCP tools in `mcp_tools/<x>/` (register them in `mcp_tools/__init__.py`), tables in `postgresql_db/schemas/setup_<x>_schema.py` (run with `python -m postgresql_db.schemas.setup_<x>_schema`).
* **Code two or more features use** goes in the `shared/` folder of that layer (or `ai/`, `notifications/` when it fits there). A feature folder must not import another feature's folder; move the common piece to `shared/` instead.
* **No loose files** at the root of `tools/`, `services/` or `models/`. In `mcp_tools/` only the registry (`__init__.py`), `middleware.py` and `prompts.py` sit at the root.
* **Imports are absolute** (`from services.shared.auth_service import ...`). Feature folders are namespace packages with no `__init__.py`, like the rest of the repo.
* **When you move a module,** update every import, `mock.patch("...")` string, `python -m` command (CI, scripts) and doc path, and fix any `__file__`-relative path in it (one more folder deep means one more `dirname`).
<!-- project-structure:end -->

---

## API Endpoints Overview

| Method | Endpoint | Description | Auth Required |
| :--- | :--- | :--- | :--- |
| `GET` | `/health/live` | Container liveness probe | No |
| `POST` | `/api/auth/microsoft/login` | Initiate Microsoft Entra SSO | No |
| `GET` | `/api/auth/me` | Current session user & permission list | Yes |
| `POST` | `/api/auth/logout` | Clear session cookie | Yes |
| `GET` | `/api/configuration/users` | List portal users with pagination & search | `USERS:VIEW` |
| `POST` | `/api/configuration/users` | Create new portal user | `USERS:CREATE` |
| `GET` | `/api/configuration/roles` | List all configured roles and hierarchies | `ROLES:VIEW` |
| `PUT` | `/api/configuration/roles/{id}` | Update role permissions | `ROLES:EDIT` |
| `GET` | `/api/notifications/stream` | Real-time SSE event stream | Yes |
| `GET` | `/api/logs` | Query audit log trail and system events | `LOGS:VIEW` |
| `POST` | `/mcp` | FastMCP tool execution endpoint | Authenticated |

---

## Local Development & Setup

### 1. Python Environment Setup
```bash
python3 -m venv venv
# On Windows:
venv\Scripts\activate
# On Linux / WSL:
source venv/bin/activate
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Environment Variables (.env)
```env
PORT=8900
FRONTEND_URL=http://localhost:6000
DATABASE_URL=postgresql://postgres:postgres@localhost:3005/template_portal_dev
DATABASE_SSL=false
SESSION_SECRET=your-32-byte-secret-key-goes-here
MICROSOFT_CLIENT_ID=your-azure-ad-client-id
MICROSOFT_CLIENT_SECRET=your-azure-ad-client-secret
MICROSOFT_TENANT_ID=common
GEMINI_API_KEY=your-gemini-api-key
```

### 4. Run Development Server
```bash
uvicorn server:app --host 0.0.0.0 --port 8900 --reload
```
Open API docs at `http://localhost:8900/docs`.


## Local Database (Docker), DataGrip & Migrations

Each project in the ZenaTech ecosystem runs an isolated local PostgreSQL container mapped to a dedicated 3000-series host port to prevent port collisions.

### 1. Local Database Configuration
* **Container Name**: `template_db_local`
* **Host Port**: `localhost:3005` (mapped to internal PostgreSQL 5432)
* **Database Name**: `template_portal_dev`
* **User / Password**: `postgres` / `postgres`
* **Connection String**: `postgresql://postgres:postgres@localhost:3005/template_portal_dev`

### 2. Managing the Local Database
```bash
# Start local database container
docker compose up -d db

# Stop local database container
docker compose down
```
### 3. Connecting in DataGrip
1. Create a new **PostgreSQL** Data Source in DataGrip.
2. Settings:
   * **Host**: `localhost`
   * **Port**: `3005`
   * **Database**: `template_portal_dev`
   * **User**: `postgres`
   * **Password**: `postgres`
3. Click **Test Connection** and apply.

### 4. Syncing Latest Live Data from AWS RDS (Optional)
To pull a copy of real live records from AWS RDS into your local Docker DB for realistic development:
```powershell
.\scripts\pull_prod_to_local.ps1
```
* Safely downloads an RDS snapshot and restores it into `localhost:3005`.
* Read-only pull: live AWS RDS remains untouched and safe.

### 5. Creating Schema Changes & Migrations (PR Workflow)
When making table or column changes on a new branch:

1. **Create and Switch to Your New Feature Branch**:
   ```bash
   git checkout -b feature/your-feature-name
   ```
   *(The Git `post-checkout` hook in `.git/hooks/post-checkout` automatically triggers to ensure your local database is synced and ready).*

2. **Sync Live Data into Local DataGrip (Optional / Recommended)**:
   ```powershell
   .\scripts\pull_prod_to_local.ps1
   ```
   *(Safely pulls real current rows into your local Docker DB on port 3005 so you can build and test queries with actual data).*

3. **Update Code Schema**:
   Edit `postgresql_db/schema_metadata.py` to add or modify columns/tables.

4. **Auto-Generate Migration Diff**:
   ```bash
   alembic revision --autogenerate -m "describe changes"
   ```
   Alembic inspects your local database and writes a versioned migration in `alembic/versions/` containing **only the differences**.

5. **Apply & Test Locally**:
   ```bash
   alembic upgrade head
   ```
   Verify your changes and tables in DataGrip on `127.0.0.1:3005` with your test data.

6. **Submit in PR**:
   Commit and push:
   * `postgresql_db/schema_metadata.py`
   * `alembic/versions/<revision_id>_*.py`
   *(Local test data stays on your machine; only the table structure diff is merged to production!)*

### 6. Disposable Database Reset
To tear down and recreate your local container from scratch to match the current branch:
```powershell
.\scripts\reset_local_db.ps1
```
* A Git `post-checkout` hook is installed in `.git/hooks/post-checkout` to trigger this automatically on branch switches.
* Built-in safety guards immediately block resets if `DATABASE_URL` points to a remote AWS RDS host.



