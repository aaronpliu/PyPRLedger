# Dependency API Contract

The interface a third-party **dependency database** must satisfy for the two
release pages that read it:

- **Release Dependency Graph** — `/releases/dependency-graph`
- **App Diff** — `/releases/apps`

It is written for whoever implements (or proxies) that endpoint.

The reference response is `src/services/dependency_mock_data.py`: the canned data
the application answers with while `DEPENDENCY_API_MOCK` is true, and the data
`scripts/mock_dependency_api.py` serves over HTTP. **An endpoint is compatible
when it answers the same shape as that file.**

---

## Where it is called from

```
project_key + repository_slug
        │  (project registry)
        ▼
     app_name
        │
        ▼
POST /api/v1/release/dependency-graph/read      src/api/v1/endpoints/release_dependency_graph.py
        │
        ▼
   DependencyGraphService                       src/services/dependency_graph_service.py
        │  (one question, one endpoint)
        ▼
   DependencyApiClient ──────►  third-party dependency database
                                src/services/dependency_api_client.py
        │
        ├─► the drawn graph (canvas)
        └─► App Version Diff                    src/services/app_version_diff_service.py
```

Two things to keep in mind:

- The **application name is what the record is keyed by**, and the application a
  repository belongs to is resolved through the project registry. A repository
  that is not registered resolves to `Unknown` (and has no record).
- Nothing on this side walks a dependency graph. **One call answers for one
  application ref**: the modules the application declared, and what each of those
  modules pulls in. That is why the endpoint must answer with the *closure it
  built*, not with a pointer to build one.

---

## Request

```
GET {DEPENDENCY_API_BASE_URL}{DEPENDENCY_API_RELEASE_PATH}?app_name=<app>&tagOrBranch=<ref>
Authorization: Bearer <DEPENDENCY_API_TOKEN>     (sent only when the token is configured)
```

| Parameter | Value |
|---|---|
| `app_name` | The application the repository resolved to (project registry) |
| `tagOrBranch` | The tag or branch the user picked on the page |

| Client behaviour | Value |
|---|---|
| Method | `GET`, query parameters only |
| Default path | `/api/v1/appReleaseInfo` (`DEPENDENCY_API_RELEASE_PATH`) |
| Timeout | 15 s (`REQUEST_TIMEOUT`) |
| TLS | Certificate verification is disabled (`verify=False`) |
| Auth | `Authorization: Bearer …`, only when `DEPENDENCY_API_TOKEN` is set |

---

## Response

### Shape

```json
{
  "app_name": "MyApp",
  "tagOrBranch": "1.0.0_10000",
  "created_at": "2026-09-30 10:30:00",
  "dependencies": {
    "packageA": "1.0.0",
    "packageB": "1.0.0",
    "packageC": "1.1.0"
  },
  "packages": [
    {
      "package_name": "packageA",
      "version": "1.0.0",
      "dependencies": { "packageD": ">=1.0.0 <1.9.0" }
    },
    {
      "package_name": "packageB",
      "version": "1.0.0",
      "dependencies": { "packageE": ">=1.0.0 <1.9.0" }
    },
    {
      "package_name": "packageC",
      "version": "1.1.0",
      "dependencies": {
        "packageD": ">=1.0.0 <1.9.0",
        "packageE": ">=1.0.0 <1.9.0"
      }
    },
    {
      "package_name": "packageD",
      "version": "1.5.0",
      "dependencies": { "packageA": ">=1.0.0 <2.0.0" }
    }
  ]
}
```

### Fields

| Field | Type | Meaning | Read as |
|---|---|---|---|
| `dependencies` | `{module: exactVersion}` | What the **application declared** — the modules it ships | The root node's outgoing edges, which are the only ones carrying an exact version |
| `packages` | array | One entry per package the database knows about | Nodes of the graph |
| `packages[].package_name` | string | Package name | Node id |
| `packages[].version` | string | Version of that package in this build | Node label |
| `packages[].dependencies` | `{package: range}` | What that package declared for its own dependencies | That node's outgoing edges |
| `created_at` | string | When the record was taken | `generated_at` on the page, and the datetime the **App Diff** orders releases by |
| `tagOrBranch` | string | **The application's own version** | The root node's version — the "application itself" row of App Diff |
| `app_name` | string | Informational | Not read (the caller already holds the name) |

### How the shape is interpreted

Three categories are derived from the two maps, and they decide how a node is
drawn and how the comparison reads it:

| The node is… | Category | Consequence |
|---|---|---|
| named in `dependencies` | shipped module (`2`) | Drawn as part of what the application ships |
| present in `packages[]` but **not** in `dependencies` | external (`1`) | Transitively pulled in — **a package like this may carry its own `dependencies`**, which is how a source expresses a deeper chain or a cycle |
| named inside a `dependencies` map but with **no entry** in `packages[]` | leaf (`1`) | The relationship alone is known; the box is a leaf |

Constraints and versions:

- A value in `packages[].dependencies` is a **constraint**. Only a bare version of
  the form `x.y.z` becomes a version on a leaf node; a range (`>=1.0.0 <1.9.0`)
  is kept as the declared constraint, and the leaf is left without a version,
  because a range cannot be ordered.
- Application versions may carry a build suffix — `1.0.0_10000` is understood
  (the App Diff compares `1.0.0_10000` < `1.0.1_10001` correctly).
- A record with more than **500** nodes is truncated before it is drawn, and the
  truncation is logged.

---

## Aligning a two-level source with this shape

A common source answers in two levels, with the module maps keyed by module name
at the top level of the same object:

```json
{
  "app_name": "MyApp",
  "version": "1.0.0_10000",
  "branch": "1.0.0-Build10000",
  "module_names": [{ "packageA": "1.0.0" }, { "packageB": "1.0.0" }, { "packageC": "1.0.1" }],
  "packageA": { "packageA1": ">=1.0.0 <=1.9.0", "packageA2": ">=1.0.0 <=1.9.0" },
  "packageB": { "packageB1": ">=1.0.0 <=1.9.0", "packageB2": ">=1.0.0 <=1.9.0" },
  "packageC": { "packageC1": ">=1.0.0 <=1.9.0", "packageC2": ">=1.0.0 <=1.9.0" },
  "created": "2026-10-08 12:00:00"
}
```

**The endpoint does the folding** — the application deliberately does not, so that
what the database calls its fields stays in one place. Three moves:

| Source | Target |
|---|---|
| `module_names: [{"packageA": "1.0.0"}, …]` | `dependencies: {"packageA": "1.0.0", …}` |
| each top-level dynamic key `"packageA": {…}` | one `packages[]` entry: `{"package_name": "packageA", "version": <the version from `module_names`>, "dependencies": {…}}` |
| `version` | `tagOrBranch` |
| `created` | `created_at` |

The source above is therefore answered as:

```json
{
  "app_name": "MyApp",
  "tagOrBranch": "1.0.0_10000",
  "created_at": "2026-10-08 12:00:00",
  "dependencies": { "packageA": "1.0.0", "packageB": "1.0.0", "packageC": "1.0.1" },
  "packages": [
    { "package_name": "packageA", "version": "1.0.0",
      "dependencies": { "packageA1": ">=1.0.0 <=1.9.0", "packageA2": ">=1.0.0 <=1.9.0" } },
    { "package_name": "packageB", "version": "1.0.0",
      "dependencies": { "packageB1": ">=1.0.0 <=1.9.0", "packageB2": ">=1.0.0 <=1.9.0" } },
    { "package_name": "packageC", "version": "1.0.1",
      "dependencies": { "packageC1": ">=1.0.0 <=1.9.0", "packageC2": ">=1.0.0 <=1.9.0" } }
  ]
}
```

`packageA1` and its like are named and described by nothing, so they become leaves
— which is exactly right for a source that has no third level. A sub-dependency
that should show an exact version must be declared as one (`"packageA1": "1.5.0"`).

### What the reader ignores

- Any top-level key other than `dependencies` and `packages` — module maps left at
  the top level are **not** read, and neither is `branch`.
- `app_name` (the caller already knows it).
- Key order, and any field not listed above.

---

## Status codes

| Situation | Answer | What the pages show |
|---|---|---|
| Record found | `200` + the JSON above | The graph, and the version comparison |
| No record for `(app_name, ref)` | `404` | "No record" for that ref; App Diff marks the release **unknown** rather than reporting it as unchanged |
| Any other error | any non-2xx | Reported to the page as a failure |
| Unreachable | — | Reported to the page as a failure |

`404` is meaningful, so use it narrowly: it is the difference between *"this build
has nothing recorded"* and *"the database is broken"*.

---

## Configuration

```bash
DEPENDENCY_API_MOCK=False                      # True answers from canned data
DEPENDENCY_API_BASE_URL=https://dependency.example.com
DEPENDENCY_API_TOKEN=                          # optional; sent as a Bearer token
DEPENDENCY_API_RELEASE_PATH=/api/v1/appReleaseInfo
```

The answer is cached in Redis for `CACHE_TTL_DEPENDENCY_GRAPH` (one hour by
default), keyed by `(project_key, repository_slug, app_name, ref)`. While
verifying a new endpoint, expect up to that long before a changed record is read
again — flush the key or lower the TTL.

---

## Verifying an implementation

1. **Against the canned data** — no third-party service required:

   ```bash
   uv run python scripts/mock_dependency_api.py --port 9091
   ```

   ```bash
   DEPENDENCY_API_MOCK=False
   DEPENDENCY_API_BASE_URL=http://127.0.0.1:9091
   ```

   Open `/releases/dependency-graph`, pick a registered repository and a ref, and
   confirm the canvas draws.

2. **Against the real endpoint** — point `DEPENDENCY_API_BASE_URL` at it, with
   `DEPENDENCY_API_MOCK=False`.

3. **Checklist for the same `app_name` + `ref`** — the answer must satisfy:

   - [ ] `dependencies` is a **map** (`{"name": "1.0.0"}`), not a list
   - [ ] every module appears in `packages[]` with `package_name`, `version` and a
         `dependencies` map
   - [ ] `tagOrBranch` carries the **application's own version** (`1.0.0_10000`),
         not the ref that was asked about — otherwise the "application itself" row
         of App Diff shows the ref
   - [ ] `created_at` is a datetime the page can order (`2026-09-30 10:30:00` and
         ISO-8601 both work)
   - [ ] an unknown `app_name`, or a ref with no record, answers `404`

4. **Cross-check the pages** — the graph canvas draws the modules and their
   leaves, and `/releases/apps` compares two refs of the same application: the
   application's own version first, then one row per declared module.

---

## Reference

| Concern | File |
|---|---|
| Canned data (the reference response) | `src/services/dependency_mock_data.py` |
| HTTP mock of the endpoint | `scripts/mock_dependency_api.py` |
| The outbound call | `src/services/dependency_api_client.py` |
| Consolidation into the drawn graph | `src/services/dependency_graph_service.py` |
| App Diff over several refs | `src/services/app_version_diff_service.py` |
| Read endpoint | `src/api/v1/endpoints/release_dependency_graph.py` |
| Client tests | `tests/test_dependency_api_client.py` |
| Graph tests | `tests/test_dependency_graph_service.py` |
