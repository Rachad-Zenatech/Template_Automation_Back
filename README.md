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

## Directory Structure

```text
Template_Automation_Back/
├── alembic/                    # Database migrations and environment configs
├── models/                     # Pydantic v2 domain schemas
│   ├── rbac_model.py           # User, role, permission models
│   └── notification_model.py   # Notification models
├── postgresql_db/              # Database pool & DDL scripts
│   ├── database.py             # asyncpg get_pool() manager
│   ├── setup_pbac_schema.py    # PBAC permission tables
│   └── seed_database.py        # Seed script for initial admin user & roles
├── services/                   # Core business logic
│   ├── auth_service.py         # SSO login and session management
│   ├── rbac_service.py         # PBAC permission resolution & checks
│   ├── cache_service.py        # Memory cache & PostgreSQL NOTIFY invalidation
│   ├── audit_service.py        # Action logging and request audit trails
│   ├── notification_service.py # SSE broadcast queues
│   ├── gemini_service.py       # AI assistant integration
│   └── service_security_policy.py # require_permission() FastAPI dependencies
├── tools/                      # FastAPI endpoint routers
│   ├── auth_router.py          # /api/auth endpoints
│   ├── rbac_router.py          # /api/configuration endpoints
│   ├── notification_router.py  # /api/notifications endpoints
│   ├── log_router.py           # /api/logs endpoints
│   └── observability.py        # /health/live and telemetry
├── server.py                   # Root FastAPI app & router registry
├── requirements.txt
└── run_server.sh
```

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
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/template_portal_dev
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
