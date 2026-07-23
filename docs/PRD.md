# PRLedger — Product Requirements Document (PRD)

| Field | Value |
|---|---|
| **Product Name** | PRLedger (Pull Request Ledger) |
| **Document Version** | 1.0 |
| **Status** | Released |
| **Classification** | Internal — All Teams |

---

## Table of Contents

1. [Product Overview](#1-product-overview)
2. [Product Goals & Scope](#2-product-goals--scope)
3. [User Roles & Personas](#3-user-roles--personas)
4. [System Architecture](#4-system-architecture)
5. [Feature Specifications](#5-feature-specifications)
6. [Data Model](#6-data-model)
7. [API Specification](#7-api-specification)
8. [Frontend Specification](#8-frontend-specification)
9. [Non-Functional Requirements](#9-non-functional-requirements)
10. [Deployment & Infrastructure](#10-deployment--infrastructure)
11. [Glossary](#11-glossary)

---

## 1. Product Overview

### 1.1 Purpose

PRLedger is a **PR Code Review Result Storage and Management System**. It provides a centralized platform for storing, tracking, scoring, and analyzing pull request (PR) code reviews from multi-Git providers (Bitbucket Server, GitHub Enterprise). The system enables teams to manage reviewer assignments, evaluate review quality through scoring, and gain analytics insights into code review processes.

### 1.2 Problem Statement

Organizations using multiple Git providers lack a unified view of code review activities. Review data is siloed within each provider, making it difficult to:
- Track review workload distribution across teams
- Measure review quality and consistency
- Enforce review policies and assignment rules
- Generate cross-project analytics

### 1.3 Target Users

| Persona | Description |
|---|---|
| **Developer** | Submits PRs, views review results, scores reviews |
| **Reviewer** | Performs code reviews, receives assignments, submits scores |
| **Review Admin** | Manages review assignments, creates auto-assignment rules, monitors review quality |
| **System Admin** | Manages users, roles, system configuration, project registry |
| **Viewer** | Read-only access to review data and analytics |

### 1.4 Key Value Propositions

- **Multi-Git Provider Support**: Per-project provider tracking (Bitbucket Server + GitHub Enterprise concurrently)
- **Centralized Review Storage**: Single source of truth for all review data across providers
- **Multi-Reviewer Assignment**: Multiple reviewers per PR with independent status tracking
- **Configurable Auto-Assignment**: Rule-based automatic reviewer assignment with priority ordering
- **Review Scoring**: File-level and PR-level scoring with configurable 0–10 scale
- **Real-Time Notifications**: SSE-based real-time event streaming
- **Role-Based Access Control**: Hierarchical roles with resource-scoped permissions and delegation

---

## 2. Product Goals & Scope

### 2.1 In Scope

| Area | Description |
|---|---|
| Review Management | CRUD operations for PR reviews, status transitions, soft delete |
| Multi-Reviewer System | Multiple reviewers per PR, independent assignment tracking |
| Auto-Assignment Engine | Rule-based automatic reviewer assignment with conditions |
| Review Scoring | File-level and PR-level scoring, analytics |
| User Management | Git users (from providers) + Auth users (system login) |
| Project Management | Projects, repositories, project registry (virtual app grouping) |
| RBAC | Role-based access control with delegation support |
| Notifications | In-app notifications with preference management |
| Real-Time Events | SSE streaming for live review updates |
| Export | PDF, Excel, CSV, JSON export of review data |
| Search | Global search across reviews, users, projects |
| Audit Trail | Operation audit logging with CSV export |
| Monitoring | Prometheus metrics + Grafana dashboards |
| LLM Proxy | Backend proxy for AI-powered review analysis (PageAgent) |
| Frontend SPA | Vue 3 + Element Plus web application |

### 2.2 Out of Scope

- Direct Git operations (clone, push, merge) — the system stores review results, not Git data
- CI/CD pipeline integration
- Chat/messaging between reviewers
- IDE plugin integration (future consideration)

---

## 3. User Roles & Personas

### 3.1 Role Hierarchy

```
system_admin
  └── review_admin
       └── reviewer
            └── viewer
```

### 3.2 Permission Matrix

| Permission | viewer | reviewer | review_admin | system_admin |
|---|:---:|:---:|:---:|:---:|
| View reviews | ✅ | ✅ | ✅ | ✅ |
| Create/edit reviews | ❌ | ✅ | ✅ | ✅ |
| Score reviews | ❌ | ✅ | ✅ | ✅ |
| Manage task assignments | ❌ | ❌ | ✅ | ✅ |
| Create auto-assignment rules | ❌ | ❌ | ✅ | ✅ |
| Manage users (Git) | ❌ | ❌ | ❌ | ✅ |
| Manage auth users | ❌ | ❌ | ❌ | ✅ |
| Manage roles & permissions | ❌ | ❌ | ❌ | ✅ |
| Manage project registry | ❌ | ❌ | ❌ | ✅ |
| Manage system settings | ❌ | ❌ | ❌ | ✅ |
| Delegate roles | ❌ | ❌ | ✅ | ✅ |
| View audit logs | ❌ | ❌ | ❌ | ✅ |
| Export data | ✅ | ✅ | ✅ | ✅ |
| Manage notifications | ✅ | ✅ | ✅ | ✅ |
| Manage personal access tokens | ✅ | ✅ | ✅ | ✅ |

### 3.3 Resource Scope

Permissions can be scoped at three levels:
- **Global**: Applies to all resources in the system
- **Project**: Applies to a specific project (identified by `project_key`)
- **Repository**: Applies to a specific repository (identified by `repository_slug`)

### 3.4 Delegation

Role holders (review_admin, system_admin) can delegate their permissions to other users for a limited time period:
- Delegations have `starts_at` / `expires_at` temporal validity
- Delegations can be scoped to specific resources
- Delegations can be revoked before expiration
- Delegation status lifecycle: `pending` → `active` → `expired` / `revoked`

---

## 4. System Architecture

### 4.1 High-Level Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                        Clients                                │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐   │
│  │  Vue 3 SPA   │  │  API Clients │  │  Git Providers   │   │
│  │  (Browser)   │  │  (PAT/JWT)   │  │  (Webhooks/API)  │   │
│  └──────┬───────┘  └──────┬───────┘  └────────┬─────────┘   │
└─────────┼──────────────────┼───────────────────┼─────────────┘
          │                  │                   │
┌─────────┼──────────────────┼───────────────────┼─────────────┐
│         ▼                  ▼                   ▼              │
│  ┌──────────────────────────────────────────────────────┐    │
│  │              FastAPI Application (Async)               │    │
│  │  ┌─────────┐ ┌──────────┐ ┌──────────┐ ┌─────────┐  │    │
│  │  │Endpoints│ │Middleware│ │ Services │ │  Utils  │  │    │
│  │  │  (API)  │ │(CORS,Rate│ │(Business │ │(Cache,  │  │    │
│  │  │         │ │Limit,Auth)│ │  Logic)  │ │Metrics) │  │    │
│  │  └────┬────┘ └──────────┘ └────┬─────┘ └─────────┘  │    │
│  └───────┼────────────────────────┼─────────────────────┘    │
│          │                        │                           │
│  ┌───────▼───────┐  ┌────────────▼────────┐                  │
│  │    MySQL      │  │       Redis          │                  │
│  │  (Primary DB) │  │  (Cache + PubSub)   │                  │
│  │  SQLAlchemy   │  │  SSE Broker         │                  │
│  │  2.0 Async    │  │  Rate Limiting      │                  │
│  └───────────────┘  └─────────────────────┘                  │
│                                                               │
│  ┌──────────────────────────────────────────────────────┐     │
│  │           Monitoring Stack (Standalone)               │     │
│  │  Prometheus → Grafana → AlertManager                 │     │
│  └──────────────────────────────────────────────────────┘     │
└───────────────────────────────────────────────────────────────┘
```

### 4.2 Technology Stack

| Layer | Technology | Purpose |
|---|---|---|
| **Backend Framework** | Python 3.12+, FastAPI | Async REST API |
| **ORM** | SQLAlchemy 2.0 (async) | Database access |
| **Database** | MySQL | Primary data store |
| **Migrations** | Alembic | Schema versioning (29 migrations) |
| **Cache** | Redis | Caching + pub/sub for SSE |
| **Validation** | Pydantic v2 | Request/response schemas |
| **Auth** | JWT (HS256) | Token-based authentication |
| **Real-Time** | SSE (Server-Sent Events) | Live event streaming |
| **Frontend** | Vue 3.4+ (Composition API) | SPA |
| **UI Framework** | Element Plus 2.x | UI components |
| **Build Tool** | Vite 5.x | Frontend bundling |
| **State** | Pinia 2.x | Frontend state management |
| **i18n** | vue-i18n | English, Simplified Chinese, Traditional Chinese |
| **Monitoring** | Prometheus + Grafana | Metrics and dashboards |
| **Containerization** | Docker + Docker Compose | Deployment |
| **Git Providers** | Bitbucket Server, GitHub Enterprise | Multi-provider abstraction |

### 4.3 Backend Layer Architecture

```
Request → Middleware → Endpoint → Service → Model/DB
              │            │          │
              │            │          └── Redis Cache
              │            │
              │            └── Pydantic Schemas (validation)
              │
              └── Rate Limit, Auth, CORS, Timing, DB Connection
```

**Key Layers:**

| Layer | Files | Responsibility |
|---|---|---|
| **API Endpoints** | `src/api/v1/endpoints/*.py` | HTTP request handling, dependency injection |
| **Core** | `src/core/*.py` | Config, database, exceptions, middleware, permissions |
| **Models** | `src/models/*.py` | SQLAlchemy ORM entities |
| **Schemas** | `src/schemas/*.py` | Pydantic request/response models |
| **Services** | `src/services/*.py` | Business logic, caching, metrics |
| **Utils** | `src/utils/*.py` | Redis, metrics, logging, password, JWT, i18n, timezone |

### 4.4 Git Provider Abstraction

```python
BaseGitProvider (Abstract)
├── BitbucketServerProvider   # Bitbucket Server / Data Center
└── GitHubEnterpriseProvider  # GitHub Enterprise
```

- Provider resolution: `get_git_provider(project)` returns the correct adapter
- Hybrid resolution: registry → payload hint → project config → default
- Each provider implements: fetch PRs, fetch diffs, sync entities

### 4.5 SSE Architecture

```
Redis PubSub → SSEBroker (singleton) → asyncio.Queue per client → SSE stream
                    │
                    ├── Single subscription shared across ALL clients
                    ├── In-memory fan-out per client relevance
                    ├── Auto-reconnection with exponential backoff
                    └── Auto-start/stop lifecycle (0 clients = freed Redis connection)
```

---

## 5. Feature Specifications

### 5.1 Review Management

**Description**: Core feature for storing and managing pull request code review data.

**Functional Requirements:**

| ID | Requirement | Priority |
|---|---|---|
| FR-5.1.1 | System SHALL support upsert (create-or-update) of reviews via POST | P0 |
| FR-5.1.2 | Each review is uniquely identified by `(pull_request_id, project_key, repository_slug, source_filename)` | P0 |
| FR-5.1.3 | Reviews store: PR ID, commit ID, branches, code diff, AI suggestions, status, metadata | P0 |
| FR-5.1.4 | Review status lifecycle: `draft` → `open` → `merged` / `closed`; `closed` → `open` | P0 |
| FR-5.1.5 | System SHALL support soft delete (mark as deleted, not physical removal) | P1 |
| FR-5.1.6 | System SHALL store raw incoming payloads for validation audit trail | P1 |
| FR-5.1.7 | System SHALL support review pinning (per-user private bookmarks) | P2 |
| FR-5.1.8 | System SHALL support bidirectional review associations (linking related PRs) | P2 |
| FR-5.1.9 | System SHALL support `page_size=0` sentinel for full dataset retrieval (export) | P1 |
| FR-5.1.10 | Code diff field supports MEDIUMTEXT (up to 16MB) for large diffs | P1 |
| FR-5.1.11 | AI review ID tracking for associating AI-generated suggestions | P2 |

**Business Rules:**
- Reviews are never physically deleted (soft delete only)
- Deleting a Git user sets `pull_request_user` to NULL (preserves review history)
- Upsert matches on composite key `(pull_request_id, project_key, repository_slug, source_filename)`

### 5.2 Multi-Reviewer System

**Description**: Support multiple reviewers per pull request with independent tracking.

**Functional Requirements:**

| ID | Requirement | Priority |
|---|---|---|
| FR-5.2.1 | Each review can have multiple reviewer assignments | P0 |
| FR-5.2.2 | Each assignment tracks: reviewer, assigned_by, assignment_status, comments | P0 |
| FR-5.2.3 | Assignment status lifecycle: `pending` → `assigned` → `in_progress` → `completed` | P0 |
| FR-5.2.4 | Unique constraint: one assignment per (review, reviewer) pair | P0 |
| FR-5.2.5 | Manual assignment by review_admin via task assignment endpoints | P0 |
| FR-5.2.6 | Automatic assignment via auto-assignment engine when no reviewer specified | P1 |
| FR-5.2.7 | Deleting a reviewer (Git user) sets assignment's reviewer to NULL | P1 |

### 5.3 Auto-Assignment Engine

**Description**: Rule-based automatic reviewer assignment for incoming reviews.

**Functional Requirements:**

| ID | Requirement | Priority |
|---|---|---|
| FR-5.3.1 | Rules are evaluated in priority order (lower number = higher priority) | P0 |
| FR-5.3.2 | Conditions stored as JSON: `project_key`, `repository_slug`, `source_branch_prefix`, `pr_author`, `status` | P0 |
| FR-5.3.3 | Each rule specifies `assign_to` (list of git usernames) | P0 |
| FR-5.3.4 | `max_assignments` controls how many from the list to assign (0 = all) | P1 |
| FR-5.3.5 | Rules support temporal validity (`starts_at`, `expires_at`) | P1 |
| FR-5.3.6 | Rules can be enabled/disabled via toggle | P0 |
| FR-5.3.7 | First matching rule wins (evaluation stops after first match) | P0 |
| FR-5.3.8 | Only review_admin and system_admin can manage rules | P0 |

**Rule Evaluation Flow:**
```
Review Created (no reviewer)
    → Load all active, non-expired rules ordered by priority
    → Evaluate conditions against review attributes
    → First match: assign reviewers from rule's assign_to list
    → Create assignment records with status "assigned"
    → Send notifications to assigned reviewers
```

### 5.4 Review Scoring

**Description**: Quality scoring system for code reviews at file and PR level.

**Functional Requirements:**

| ID | Requirement | Priority |
|---|---|---|
| FR-5.4.1 | Scores use configurable 0–10 float scale | P0 |
| FR-5.4.2 | Support file-level scoring (specific `source_filename`) | P0 |
| FR-5.4.3 | Support PR-level scoring (`source_filename` = NULL) | P0 |
| FR-5.4.4 | Unique constraint: one score per (reviewer, PR, file) combination | P0 |
| FR-5.4.5 | Score includes: score value, description, reviewer comments | P0 |
| FR-5.4.6 | Scores support soft delete with `active` flag | P1 |
| FR-5.4.7 | Deleting a reviewer sets score's reviewer to NULL (preserves data) | P1 |
| FR-5.4.8 | Score trends endpoint for analytics over time | P2 |

### 5.5 User Management

**Description**: Dual user model — Git users (from providers) and Auth users (system login).

#### 5.5.1 Git Users

| ID | Requirement | Priority |
|---|---|---|
| FR-5.5.1 | Git users represent external identities from Bitbucket/GitHub | P0 |
| FR-5.5.2 | Fields: user_id (business ID), username, display_name, email, active, is_reviewer | P0 |
| FR-5.5.3 | `is_reviewer` flag controls eligibility for review assignments | P0 |
| FR-5.5.4 | Toggle reviewer status endpoint | P0 |
| FR-5.5.5 | Deleting a Git user preserves reviews (FK SET NULL) | P0 |
| FR-5.5.6 | Entity sync service auto-creates/updates Git users from provider data | P1 |

#### 5.5.2 Auth Users

| ID | Requirement | Priority |
|---|---|---|
| FR-5.5.7 | Auth users are system login accounts with password authentication | P0 |
| FR-5.5.8 | Optional link to Git user via `user_id` (auto-linked by username) | P0 |
| FR-5.5.9 | JWT-based authentication with access + refresh tokens | P0 |
| FR-5.5.10 | Access token expiry configurable (default 30 min) | P0 |
| FR-5.5.11 | Refresh token idle timeout (default 120 min) | P0 |
| FR-5.5.12 | `must_change_password` flag forces password change on next login | P1 |
| FR-5.5.13 | Avatar upload support (JPEG, PNG, WebP, GIF; max 5MB) | P2 |
| FR-5.5.14 | Admin can delete auth user (cascades to roles, audit, PATs; preserves Git user) | P1 |
| FR-5.5.15 | Activate/deactivate auth user accounts | P0 |

### 5.6 Project & Repository Management

**Description**: Organize code review data by projects and repositories.

| ID | Requirement | Priority |
|---|---|---|
| FR-5.6.1 | Projects identified by `project_key` (unique, e.g., "PROJ-A") | P0 |
| FR-5.6.2 | Repositories belong to a project, identified by `repository_slug` | P0 |
| FR-5.6.3 | Project statistics endpoint (review counts, reviewer counts) | P1 |
| FR-5.6.4 | Unpaginated project list for dropdown menus | P2 |
| FR-5.6.5 | Entity sync auto-creates projects/repos from Git provider data | P1 |

### 5.7 Project Registry (Virtual App Grouping)

**Description**: Virtual `app_name` architecture for organizing projects into logical applications without schema changes.

| ID | Requirement | Priority |
|---|---|---|
| FR-5.7.1 | Registry maps `(project_key, repository_slug)` → `app_name` | P0 |
| FR-5.7.2 | `app_name` is computed at query time (not stored in review table) | P0 |
| FR-5.7.3 | Unregistered projects auto-assign to "Unknown" app | P0 |
| FR-5.7.4 | Multi-app query support: `GET /reviews?app_names=member,tv` | P0 |
| FR-5.7.5 | Admin APIs: register, update (move), unregister project-repo pairs | P0 |
| FR-5.7.6 | List all apps with project counts | P1 |
| FR-5.7.7 | Batch resolution prevents N+1 queries | P0 |

**Query Flow:**
```
Request: GET /reviews?app_names=member,tv
    → Parse app_names list
    → Query registry: resolve (project_key, repository_slug) pairs
    → Build review query with OR conditions
    → Batch resolve app_names for results
    → Inject app_name into each response item
```

### 5.8 Authentication & Authorization

#### 5.8.1 JWT Authentication

| ID | Requirement | Priority |
|---|---|---|
| FR-5.8.1 | Login endpoint returns access_token + refresh_token | P0 |
| FR-5.8.2 | Access token sent as Bearer header | P0 |
| FR-5.8.3 | Refresh token stored in Redis session store | P0 |
| FR-5.8.4 | Token refresh endpoint rotates both tokens | P0 |
| FR-5.8.5 | Expired/invalid tokens return 401 | P0 |

#### 5.8.2 Personal Access Tokens (PAT)

| ID | Requirement | Priority |
|---|---|---|
| FR-5.8.6 | Users can create PATs for API authentication | P1 |
| FR-5.8.7 | PATs have: name, token_hash, prefix, expiration | P1 |
| FR-5.8.8 | PATs can be revoked individually | P1 |
| FR-5.8.9 | Token shown only once at creation (stored as hash) | P1 |
| FR-5.8.10 | PAT authentication as alternative to JWT | P1 |

#### 5.8.3 RBAC

| ID | Requirement | Priority |
|---|---|---|
| FR-5.8.11 | Roles define permissions as JSON: `{"reviews": ["read", "create"]}` | P0 |
| FR-5.8.12 | Predefined roles: viewer, reviewer, review_admin, system_admin | P0 |
| FR-5.8.13 | Role assignments support resource scope (global/project/repository) | P0 |
| FR-5.8.14 | Custom roles can be created by system_admin | P1 |
| FR-5.8.15 | Permission checks at endpoint level via `Depends()` | P0 |

### 5.9 Notifications

| ID | Requirement | Priority |
|---|---|---|
| FR-5.9.1 | In-app notifications for review assignments, status changes | P1 |
| FR-5.9.2 | Notification types: assignment, status_change, score, mention | P1 |
| FR-5.9.3 | Priority levels: low, normal, high, urgent | P1 |
| FR-5.9.4 | Channel support: in_app, email, slack | P2 |
| FR-5.9.5 | Per-user notification preferences (enable/disable per type+channel) | P1 |
| FR-5.9.6 | Mark as read / mark all as read | P1 |
| FR-5.9.7 | Notification retention with configurable expiry (default 30 days) | P2 |
| FR-5.9.8 | Real-time delivery via SSE when client is connected | P1 |

### 5.10 Real-Time Events (SSE)

| ID | Requirement | Priority |
|---|---|---|
| FR-5.10.1 | SSE endpoint at `GET /api/v1/sse/stream` | P1 |
| FR-5.10.2 | JWT token passed as query parameter for SSE connections | P1 |
| FR-5.10.3 | Events: `review_created`, `review_updated`, `score_added` | P1 |
| FR-5.10.4 | Per-user relevance filtering (only events involving the user) | P1 |
| FR-5.10.5 | Connection limits: 3 per user (regular), 10 per user (admin) | P1 |
| FR-5.10.6 | Global connection limit: 2000 concurrent SSE connections | P1 |
| FR-5.10.7 | Idle timeout: 300 seconds (auto-disconnect) | P1 |
| FR-5.10.8 | Heartbeat every 15 seconds to keep connections alive | P1 |
| FR-5.10.9 | Oldest connection pruned when per-user limit exceeded | P1 |
| FR-5.10.10 | Broker auto-reconnects to Redis with exponential backoff | P1 |

### 5.11 Export

| ID | Requirement | Priority |
|---|---|---|
| FR-5.11.1 | Export reviews to PDF format | P1 |
| FR-5.11.2 | Export reviews to Excel (.xlsx) format | P1 |
| FR-5.11.3 | Export reviews to CSV format | P1 |
| FR-5.11.4 | Export reviews to JSON format | P1 |
| FR-5.11.5 | `page_size=0` returns all matching records for full export | P1 |
| FR-5.11.6 | Frontend "Export All Filtered Data" uses `page_size=0` | P1 |
| FR-5.11.7 | Audit log CSV export | P2 |

### 5.12 Global Search

| ID | Requirement | Priority |
|---|---|---|
| FR-5.12.1 | Search across reviews, users, and projects simultaneously | P1 |
| FR-5.12.2 | Filter by type: `review`, `user`, `project` | P1 |
| FR-5.12.3 | Configurable result limit per type (1–50) | P1 |
| FR-5.12.4 | Query timeout: 5 seconds (graceful degradation on timeout) | P1 |
| FR-5.12.5 | Search matches: PR ID, project key, repository slug, username, project name | P1 |

### 5.13 Audit Trail

| ID | Requirement | Priority |
|---|---|---|
| FR-5.13.1 | All mutations logged with: user, action, resource, old/new values, HTTP method/path, response status, execution time, IP, user agent | P1 |
| FR-5.13.2 | Audit logs queryable with filters (user, action, date range) | P1 |
| FR-5.13.3 | Audit logs exportable to CSV | P2 |
| FR-5.13.4 | Only system_admin can access audit logs | P1 |

### 5.14 LLM Proxy (PageAgent)

| ID | Requirement | Priority |
|---|---|---|
| FR-5.14.1 | Backend proxy for AI-powered code review analysis | P2 |
| FR-5.14.2 | Configuration via system_settings table (override env vars) | P2 |
| FR-5.14.3 | Streaming response support for LLM interactions | P2 |
| FR-5.14.4 | API key secured in backend (never exposed to frontend) | P2 |

### 5.15 ID Obfuscation

| ID | Requirement | Priority |
|---|---|---|
| FR-5.15.1 | Numeric IDs encoded to opaque, URL-safe strings (hashids) | P2 |
| FR-5.15.2 | Minimum 10 characters, alphanumeric | P2 |
| FR-5.15.3 | Entity-type prefixes: `rev_`, `sc_`, `usr_`, `rule_` | P2 |
| FR-5.15.4 | Deterministic encoding with configurable salt | P2 |
| FR-5.15.5 | Invalid decode returns `None` (no exceptions) | P2 |

### 5.16 Organization Hierarchy

| ID | Requirement | Priority |
|---|---|---|
| FR-5.16.1 | Support Group → Team hierarchy via self-referencing `organization_group` table | P2 |
| FR-5.16.2 | Group types: `group`, `team` | P2 |
| FR-5.16.3 | Nested groups via `parent_id` (NULL = root group) | P2 |

### 5.17 System Settings

| ID | Requirement | Priority |
|---|---|---|
| FR-5.17.1 | Key-value store for runtime configuration | P1 |
| FR-5.17.2 | Settings: LLM config, feature flags, system parameters | P1 |
| FR-5.17.3 | Only system_admin can manage settings | P1 |
| FR-5.17.4 | Settings take precedence over environment variable defaults | P1 |
| FR-5.17.5 | Each setting has: key, value, description, is_active, updated_by audit | P1 |

---

## 6. Data Model

### 6.1 Entity Relationship Overview

```
┌─────────────┐     ┌──────────────────────┐     ┌─────────────────┐
│   Project   │────<│  PullRequestReview   │>────│   Repository    │
│             │     │       Base           │     │                 │
└──────┬──────┘     └──────────┬───────────┘     └────────┬────────┘
       │                       │                           │
       │                ┌──────┴──────┐                    │
       │                │             │                    │
       │    ┌───────────▼──┐  ┌──────▼───────┐           │
       │    │  Assignment  │  │    Score     │           │
       │    │  (per        │  │  (per        │           │
       │    │  reviewer)   │  │  reviewer)   │           │
       │    └──────────────┘  └──────────────┘           │
       │                                                  │
┌──────┴──────┐     ┌──────────────────────┐              │
│   Project   │────<│  Project Registry    │              │
│  Registry   │     │  (app_name mapping)  │              │
└─────────────┘     └──────────────────────┘              │
                                                          │
┌─────────────┐     ┌──────────────────────┐              │
│  Auth User  │────<│  Role Assignment     │              │
│             │     │  (RBAC + Delegation) │              │
└──────┬──────┘     └──────────────────────┘              │
       │                                                   │
┌──────┴──────┐     ┌──────────────────────┐              │
│  User (Git) │>────│  Review Base         │──────────────┘
│             │     │  (FK SET NULL)       │
└─────────────┘     └──────────────────────┘
```

### 6.2 Database Tables

| Table | Purpose | Key Fields |
|---|---|---|
| `user` | Git users from providers | `id`, `user_id`, `username`, `display_name`, `email_address`, `active`, `is_reviewer` |
| `auth_user` | System login users | `id`, `username`, `email`, `password_hash`, `user_id` (FK→user), `is_active`, `must_change_password`, `avatar_url` |
| `project` | Code review projects | `id`, `project_id`, `project_name`, `project_key`, `project_url`, `git_provider` |
| `repository` | Repos per project | `id`, `repository_id`, `project_key` (FK), `repository_name`, `repository_slug` |
| `pull_request_review_base` | PR review records | `id`, `pull_request_id`, `project_key` (FK), `repository_slug` (FK), `source_filename`, `source_branch`, `target_branch`, `git_code_diff` (MEDIUMTEXT), `pull_request_status`, `pull_request_user` (FK→user, SET NULL), `ai_review_id` |
| `pull_request_review_assignment` | Reviewer assignments | `id`, `review_base_id` (FK), `reviewer` (FK→user, SET NULL), `assigned_by` (FK→user), `assignment_status`, `reviewer_comments` |
| `pull_request_score` | Review scores | `id`, `pull_request_id`, `project_key` (FK), `repository_slug` (FK), `source_filename`, `reviewer` (FK→user, SET NULL), `score` (Float), `score_description`, `active` |
| `pull_request_review_raw` | Raw incoming payloads | `id`, `request_payload` (JSON), `status`, `error_message`, `review_base_id` (FK) |
| `pull_request_review_association` | Review linking | `id`, `review_id` (FK), `associated_review_id` (FK), `created_by` (FK→auth_user) |
| `user_pinned_reviews` | User bookmarks | `id`, `user_id` (FK→auth_user), `review_id` (FK) |
| `pull_request_review_auto_assignment_rule` | Auto-assign rules | `id`, `name`, `priority`, `conditions` (JSON), `assign_to` (JSON), `max_assignments`, `starts_at`, `expires_at`, `is_active` |
| `project_registry` | App name mappings | `id`, `app_name`, `project_key` (FK), `repository_slug`, `description` |
| `role` | RBAC roles | `id`, `name`, `description`, `permissions` (JSON) |
| `user_role_assignment` | User-role mappings | `id`, `auth_user_id` (FK), `role_id` (FK), `resource_type`, `resource_id`, `is_delegated`, `delegator_id`, `delegation_status`, `expires_at` |
| `notification` | User notifications | `id`, `user_id` (FK→user), `type`, `title`, `message`, `is_read`, `priority`, `channel` |
| `notification_preference` | Per-user preferences | `id`, `user_id` (FK→user), `notification_type`, `channel_enabled`, `email_enabled`, `in_app_enabled`, `slack_enabled` |
| `personal_access_token` | API tokens | `id`, `auth_user_id` (FK), `name`, `token_hash`, `prefix`, `expires_at`, `is_active` |
| `audit_log` | Operation audit trail (BIGINT PK for high volume) | `id`, `auth_user_id` (FK), `action`, `resource_type`, `resource_id`, `old_values` (JSON), `new_values` (JSON), `ip_address`, `user_agent`, `request_method`, `request_path`, `response_status`, `execution_time_ms`, `error_message` |
| `system_settings` | Runtime config | `id`, `setting_key`, `setting_value`, `description`, `is_active` |
| `organization_group` | Org hierarchy (Group → Team) | `id`, `name`, `parent_id` (self-ref FK), `type` (group/team), `description` |

### 6.3 Key Design Decisions

1. **Business ID Strategy**: External IDs (`user_id`, `project_id`, `repository_id`) from Git providers are stored alongside internal auto-increment IDs. Foreign keys in review tables reference business string keys (`project_key`, `repository_slug`, `username`).

2. **Soft Delete for Reviews**: Reviews are never physically deleted. Status-based lifecycle with optional soft delete.

3. **FK SET NULL on User Deletion**: When a Git user is deleted, all related reviews, assignments, and scores survive with NULL references. This preserves historical data integrity.

4. **Virtual App Name**: The `app_name` grouping is resolved at query time via the `project_registry` table, not stored in the review table. This avoids schema proliferation.

5. **JSON Permissions**: Role permissions stored as JSON (`{"reviews": ["read", "create"]}`) for flexibility without schema changes.

6. **MEDIUMTEXT for Diffs**: Code diff field uses MySQL MEDIUMTEXT (up to 16MB) to handle large pull request diffs.

7. **Multi-Reviewer via Assignment Table**: Instead of a single reviewer column, a separate assignment table enables N reviewers per review with independent status tracking.

---

## 7. API Specification

### 7.1 API Conventions

| Convention | Detail |
|---|---|
| Base URL | `/api/v1/` |
| Auth | Bearer JWT in `Authorization` header, or PAT |
| Content Type | `application/json` |
| Pagination | `page` (1-based), `page_size` (default 20, max 100, 0 = all) |
| Error Format | `{"error": "code", "message": "description", "detail": {...}}` |
| ID Obfuscation | Public IDs use prefixed hashids: `rev_abc123...` |
| Rate Limiting | 1000 requests/60 seconds (configurable) |
| API Docs | OpenAPI/Swagger at `/api/docs` (dev only) |

### 7.2 Endpoint Summary

#### Reviews (`/api/v1/reviews`)

| Method | Path | Description | Auth |
|---|---|---|---|
| POST | `/` | Create/update review (upsert) | JWT/PAT |
| GET | `/` | List reviews with filters | JWT/PAT |
| GET | `/{project_key}/{repo_slug}/{pr_id}` | Get reviews by composite key | JWT/PAT |
| PUT | `/{project_key}/{repo_slug}/{pr_id}` | Update review | JWT/PAT |
| PATCH | `/{project_key}/{repo_slug}/{pr_id}/status` | Update status | JWT/PAT |
| DELETE | `/{project_key}/{repo_slug}/{pr_id}` | Soft delete | JWT/PAT |
| POST | `/{id}/pin` | Pin a review | JWT/PAT |
| DELETE | `/{id}/pin` | Unpin a review | JWT/PAT |
| POST | `/{id}/associate/{target_id}` | Link reviews | JWT/PAT |
| DELETE | `/{id}/associate/{target_id}` | Unlink reviews | JWT/PAT |
| GET | `/statistics` | Review statistics | JWT/PAT |
| GET | `/project/{project_key}` | Reviews by project | JWT/PAT |
| GET | `/reviewer/{username}` | Reviews by reviewer | JWT/PAT |
| GET | `/trends/reviewer-activity` | Reviewer activity trends | JWT/PAT |
| GET | `/trends/score-trends` | Score trends | JWT/PAT |
| PUT | `/score` | Upsert review score | JWT/PAT |
| DELETE | `/score/{reviewer}` | Delete score | JWT/PAT |

#### Auto-Assignment Rules (`/api/v1/auto-task-assignment/rules`)

| Method | Path | Description | Auth |
|---|---|---|---|
| POST | `/` | Create rule | review_admin |
| GET | `/` | List rules by priority | review_admin |
| GET | `/{id}` | Get rule | review_admin |
| PUT | `/{id}` | Update rule | review_admin |
| DELETE | `/{id}` | Delete rule | review_admin |
| PATCH | `/{id}/toggle` | Enable/disable | review_admin |

#### Task Assignment (`/api/v1/task-assignment`)

| Method | Path | Description | Auth |
|---|---|---|---|
| GET | `/` | List reviews with assignments | review_admin |
| GET | `/{id}` | Get review with assignments | review_admin |
| POST | `/{id}/assign` | Assign reviewer | review_admin |
| DELETE | `/{id}/assign/{reviewer}` | Remove reviewer | review_admin |
| PATCH | `/assignments/{id}/status` | Update assignment status | review_admin |

#### Auth (`/api/v1/users/auth`)

| Method | Path | Description | Auth |
|---|---|---|---|
| POST | `/register` | Register new user | Public |
| POST | `/login` | Login (returns JWT) | Public |
| POST | `/refresh` | Refresh tokens | JWT |
| GET | `/` | List auth users | system_admin |
| DELETE | `/{id}` | Delete auth user | system_admin |
| PATCH | `/{id}/activate` | Activate user | system_admin |
| PATCH | `/{id}/deactivate` | Deactivate user | system_admin |
| POST | `/{username}/avatar` | Upload avatar | JWT |
| DELETE | `/{username}/avatar` | Delete avatar | JWT |

#### Git Users (`/api/v1/users/git`)

| Method | Path | Description | Auth |
|---|---|---|---|
| POST | `/` | Create Git user | system_admin |
| GET | `/` | List Git users | JWT/PAT |
| GET | `/{id}` | Get by ID | JWT/PAT |
| PUT | `/{id}` | Update | system_admin |
| DELETE | `/{id}` | Delete (preserves reviews) | system_admin |
| GET | `/reviewers` | List active reviewers | JWT/PAT |
| PATCH | `/{id}/toggle-reviewer` | Toggle reviewer flag | system_admin |

#### RBAC (`/api/v1/roles`, `/api/v1/rbac`)

| Method | Path | Description | Auth |
|---|---|---|---|
| GET/POST | `/roles` | List/create roles | system_admin |
| GET/PUT/DELETE | `/roles/{id}` | Get/update/delete role | system_admin |
| POST | `/users/{id}/roles` | Assign role | system_admin |
| DELETE | `/users/{id}/roles/{role_id}` | Revoke role | system_admin |
| GET | `/users/{id}/roles` | Get user roles | system_admin |
| POST | `/rbac/delegations` | Delegate role | review_admin |
| PATCH | `/rbac/delegations/{id}/revoke` | Revoke delegation | review_admin |

#### Projects (`/api/v1/projects`)

| Method | Path | Description | Auth |
|---|---|---|---|
| POST | `/` | Create project | system_admin |
| GET | `/` | List projects | JWT/PAT |
| GET | `/all` | All projects (unpaginated) | JWT/PAT |
| GET | `/key/{project_key}` | Get by key | JWT/PAT |
| GET | `/key/{project_key}/repositories` | List repos | JWT/PAT |
| PUT | `/{id}` | Update | system_admin |
| DELETE | `/{id}` | Delete | system_admin |
| GET | `/statistics` | Project statistics | JWT/PAT |

#### Project Registry (`/api/v1/apps`, `/api/v1/admin/registry`)

| Method | Path | Description | Auth |
|---|---|---|---|
| GET | `/apps` | List all apps | JWT/PAT |
| GET | `/apps/{app_name}/projects` | Projects in app | JWT/PAT |
| POST | `/admin/registry/register` | Register to app | system_admin |
| PUT | `/admin/registry/update` | Move to different app | system_admin |
| DELETE | `/admin/registry/unregister` | Remove from registry | system_admin |

#### Notifications (`/api/v1/notifications`)

| Method | Path | Description | Auth |
|---|---|---|---|
| GET | `/` | List for current user | JWT |
| PATCH | `/{id}/read` | Mark as read | JWT |
| POST | `/read-all` | Mark all as read | JWT |
| GET | `/preferences` | Get preferences | JWT |
| PUT | `/preferences` | Update preferences | JWT |

#### Personal Access Tokens (`/api/v1/pat`)

| Method | Path | Description | Auth |
|---|---|---|---|
| POST | `/create` | Create PAT | JWT |
| GET | `/` | List user's PATs | JWT |
| DELETE | `/{id}` | Revoke PAT | JWT |

#### Search & SSE & Audit & LLM

| Method | Path | Description | Auth |
|---|---|---|---|
| GET | `/search/?q={query}` | Global search | JWT/PAT |
| GET | `/sse/stream` | SSE event stream | JWT (query param) |
| GET | `/audit/logs` | Query audit logs | system_admin |
| GET | `/audit/export` | Export audit CSV | system_admin |
| POST | `/llm/chat/completions` | LLM proxy (streaming) | JWT |
| GET | `/llm/config` | Get LLM config | JWT |

---

## 8. Frontend Specification

### 8.1 Technology Stack

| Component | Technology |
|---|---|
| Framework | Vue 3.4+ (Composition API, `<script setup>`) |
| Build | Vite 5.x |
| Language | TypeScript 5.x (strict mode) |
| UI Library | Element Plus 2.x |
| State | Pinia 2.x |
| Router | Vue Router 4.x |
| HTTP | Axios 1.x (with interceptors) |
| i18n | vue-i18n (en, zh-CN, zh-TW) |
| Charts | ECharts (via vue-echarts) |

### 8.2 Page Map

| Route | Page | Access |
|---|---|---|
| `/login` | Login | Public |
| `/register` | Registration | Public |
| `/force-password-change` | Force password change | Authenticated |
| `/` | Dashboard (trends, recent reviews) | Authenticated |
| `/reviews` | Review list (filtering, export, pinning) | Authenticated |
| `/reviews/:id` | Review detail (code diff, AI review, scores) | Authenticated |
| `/task-assignment` | Task assignment management | review_admin+ |
| `/task-assignment/analytics` | Assignment analytics dashboard | review_admin+ |
| `/task-assignment/rules` | Auto-assignment rule management | review_admin+ |
| `/task-assignment/app/:appName` | App-filtered task assignment | review_admin+ |
| `/task-assignment/:id` | Task assignment detail | review_admin+ |
| `/scores` | Score list with filters | Authenticated |
| `/scores/analytics` | Score analytics dashboard | Authenticated |
| `/notifications` | Notification list | Authenticated |
| `/notifications/preferences` | Notification preferences | Authenticated |
| `/profile` | User profile | Authenticated |
| `/myadmin/` | Admin dashboard | system_admin |
| `/myadmin/system-users` | Auth user management | system_admin |
| `/myadmin/git-users` | Git user management | system_admin |
| `/myadmin/roles` | Role management | system_admin |
| `/myadmin/delegations` | Delegation management | system_admin |
| `/myadmin/audit` | Audit log viewer | system_admin |
| `/myadmin/sessions` | Session management | system_admin |
| `/myadmin/project-registry` | Project registry management | system_admin |
| `/myadmin/settings` | System settings | system_admin |
| `/myadmin/review-validation` | Raw review validation | review_admin+ |

### 8.3 Frontend Architecture

```
src/
├── api/           # Typed API service modules (Axios)
│   ├── auth.ts, reviews.ts, scores.ts, users.ts, projects.ts
│   ├── taskAssignment.ts, autoAssignRules.ts, rbac.ts
│   ├── notifications.ts, pat.ts, search.ts, audit.ts
│   ├── projectRegistry.ts, llm.ts
├── components/    # Reusable Vue components
│   ├── auth/      # Login forms, avatar
│   ├── charts/    # ECharts wrappers
│   ├── common/    # Shared UI components
│   ├── delegation/# Delegation UI
│   ├── review/    # Review-specific components
│   ├── stats/     # Statistics display
│   └── user/      # User profile components
├── composables/   # Composition API functions
│   ├── usePermission.ts    # RBAC permission checks
│   ├── useSse.ts           # SSE connection management
│   ├── useTheme.ts         # Dark/light theme
│   ├── useLanguage.ts      # i18n language switching
│   ├── useLoading.ts       # Loading state management
│   ├── useKeyboardShortcuts.ts  # Keyboard shortcuts
│   ├── usePageAgent.ts     # AI assistant integration
│   ├── usePrUrl.ts         # PR URL parsing
│   └── useTaskAssignmentAnalytics.ts  # Analytics calculations
├── layouts/       # DefaultLayout, AdminLayout
├── locales/       # en.json, zh-CN.json, zh-TW.json
├── router/        # Vue Router with navigation guards
├── stores/        # Pinia stores (auth, notifications)
├── types/         # TypeScript type definitions
├── utils/         # Utility functions
│   └── export/    # PDF, Excel, CSV, JSON export
└── views/         # Page components (27 views)
```

### 8.4 Key Frontend Features

| Feature | Description |
|---|---|
| **JWT Auth Flow** | Login → store tokens → Axios interceptor → auto-redirect on 401 |
| **RBAC Navigation** | Route guards check roles; forbidden → 403 page |
| **Password Enforcement** | `must_change_password` → force redirect to change page |
| **SSE Real-Time** | Auto-reconnect with exponential backoff, tab visibility recovery |
| **Export** | Client-side PDF/Excel/CSV/JSON generation from filtered data |
| **i18n** | Three languages with runtime switching |
| **Theme** | Dark/light mode toggle |
| **Keyboard Shortcuts** | Global shortcuts for common actions |
| **PageAgent** | AI-powered code review assistant (via LLM proxy) |

---

## 9. Non-Functional Requirements

### 9.1 Performance

| Requirement | Target |
|---|---|
| API response time (p95) | < 500ms |
| Database query timeout | 30 seconds |
| Search query timeout | 5 seconds |
| SSE heartbeat interval | 15 seconds |
| SSE idle timeout | 300 seconds |
| Max concurrent SSE connections | 2000 |
| Max concurrent operations | 1000 |
| Database connection pool | 20 + 10 overflow |
| Redis max connections | 100 |
| Cache TTL (reviews) | 1 hour |
| Cache TTL (projects) | 6 hours |
| Cache TTL (users) | 12 hours |

### 9.2 Security

| Requirement | Implementation |
|---|---|
| Authentication | JWT (HS256) + Personal Access Tokens |
| Password Storage | Bcrypt hashing |
| Input Validation | Pydantic v2 schemas |
| SQL Injection | SQLAlchemy ORM (parameterized queries) |
| XSS Protection | Security headers, Vue auto-escaping |
| Rate Limiting | Redis-based sliding window (1000 req/60s) |
| CORS | Configurable allowed origins |
| ID Obfuscation | Hashids with configurable salt |
| API Key Protection | LLM API keys stored in backend only |
| Secret Management | Environment variables + system_settings |

### 9.3 Reliability

| Requirement | Implementation |
|---|---|
| Redis Reconnection | Exponential backoff (1s base, 30s max) with ±20% jitter |
| SSE Broker Health | `is_healthy` property checks dispatch task |
| Auto-start/stop | Broker starts on first client, stops on last disconnect |
| Data Preservation | FK SET NULL on user deletion preserves review history |
| Raw Payload Audit | All incoming reviews stored in raw table before processing |

### 9.4 Monitoring & Observability

| Requirement | Implementation |
|---|---|
| Metrics | Prometheus client (HTTP, DB, Cache, Review, User, Project metrics) |
| Dashboards | Grafana with pre-configured code review dashboard |
| Alerting | AlertManager integration |
| Logging | Structured JSON logging with `extra` context |
| Health Checks | Docker health checks, `/api/health` endpoint |
| Audit Trail | All mutations logged with user, action, timestamp, IP |

### 9.5 Scalability

| Aspect | Design |
|---|---|
| SSE | Single Redis pubsub shared across all clients (1 connection for N users) |
| Caching | Multi-layer: in-memory (L1) + Redis (L2) |
| Database | Connection pooling, indexed queries, batch resolution |
| Async | Full async/await throughout (DB, Redis, HTTP) |
| Provider | Pluggable Git provider abstraction |

### 9.6 Internationalization

| Language | Code | Status |
|---|---|---|
| English | `en` | ✅ Complete |
| Simplified Chinese | `zh-CN` | ✅ Complete |
| Traditional Chinese | `zh-TW` | ✅ Complete |

### 9.7 Timezone Handling

- Database storage: UTC (configurable via `USE_UTC_IN_DB`)
- Application timezone: Configurable (default `Asia/Shanghai`)
- All datetime conversions handled by `src/utils/timezone.py`

---

## 10. Deployment & Infrastructure

### 10.1 Docker Compose Services

| Service | Image/Build | Port | Purpose |
|---|---|---|---|
| `api` | Custom Dockerfile | 8000 | FastAPI application |
| `mysql` | MySQL 8.0 | 3306 | Primary database |
| `redis` | Redis 7 | 6379 | Cache + pub/sub |
| `prometheus` | prom/prometheus | 9090 | Metrics collection |
| `grafana` | grafana/grafana | 3000 | Dashboard visualization |
| `alertmanager` | prom/alertmanager | 9093 | Alert routing |
| `frontend` | Custom Dockerfile + nginx | 80/443 | Vue 3 SPA |

### 10.2 Environment Configuration

Key environment variable groups:
- `DATABASE_*`: MySQL connection (host, port, user, password, name)
- `REDIS_*`: Redis connection (host, port, password, db)
- `SECRET_KEY`: JWT signing key
- `BITBUCKET_*`: Bitbucket Server (URL, user, password, workspace)
- `GITHUB_ENTERPRISE_*`: GitHub Enterprise (URL, token)
- `PROMETHEUS_ENABLED`: Toggle metrics
- `RATE_LIMIT_*`: Rate limiting config
- `CACHE_TTL_*`: Cache TTL config
- `SMTP_*`: Email notifications
- `SLACK_*`: Slack notifications
- `LLM_*`: LLM proxy config
- `TIMEZONE`, `USE_UTC_IN_DB`: Timezone handling

### 10.3 Database Migrations

- Tool: Alembic
- Total migrations: 29 (as of current version)
- Command: `alembic upgrade head`
- Auto-generate: `alembic revision --autogenerate -m "description"`

### 10.4 Monitoring Stack

Standalone `monitoring/` directory with independent Docker Compose:
- Prometheus scrapes API at `http://api:8000/api/metrics` (10s interval)
- Grafana pre-configured with Prometheus datasource + code review dashboard
- AlertManager for notification routing

---

## 11. Glossary

| Term | Definition |
|---|---|
| **PR** | Pull Request — a proposal to merge changes into a code repository |
| **Review** | A code review of a pull request, stored as a record in PRLedger |
| **Assignment** | A reviewer-specific task linked to a review (who reviews, status) |
| **Score** | A quality rating (0–10) given by a reviewer for a review or file |
| **Git User** | A user identity synced from an external Git provider (Bitbucket/GitHub) |
| **Auth User** | A system login account with password and JWT authentication |
| **Project** | A code project identified by `project_key` (e.g., "PROJ-A") |
| **Repository** | A code repository within a project, identified by `repository_slug` |
| **App Name** | A virtual grouping label resolved via project registry |
| **Project Registry** | A mapping table: `(project_key, repository_slug)` → `app_name` |
| **RBAC** | Role-Based Access Control |
| **Delegation** | Temporary transfer of permissions from one user to another |
| **PAT** | Personal Access Token — a long-lived API authentication token |
| **SSE** | Server-Sent Events — a unidirectional real-time push technology |
| **SSEBroker** | Singleton service that multiplexes 1 Redis pubsub across all SSE clients |
| **Auto-Assignment Rule** | A priority-ordered rule for automatically assigning reviewers |
| **ID Obfuscation** | Encoding numeric IDs to opaque strings using hashids |
| **PageAgent** | AI-powered code review assistant integrated via LLM proxy |
| **Upsert** | Create-or-update operation based on composite key matching |
| **Soft Delete** | Marking a record as deleted without physical removal |

---

*End of Product Requirements Document*
