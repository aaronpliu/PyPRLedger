# Publishing Releases to Confluence

An optional integration: when a release note is published, it is also written to
Confluence as a page. This is written for whoever enables it, and for whoever has
to answer why a release did not appear there.

It is an addition to publishing rather than part of it. Nothing in it is required
by the application: with it unconfigured, no code path reaches Confluence and
publishing behaves exactly as it did. A release is published whether or not
Confluence answers, so a failure is recorded on the release rather than raised.

---

## What it does

- **One page per release.** The first sync creates the page; every sync after
  that updates the same one, so syncing a release twice does not leave two.
- **The title identifies the release on its own**:

  ```
  {app_name} — {tag_name}
  ```

  `app_name` is the application the repository is registered under in the project
  registry (System settings → Project Registry). An unregistered repository uses
  its slug instead, so its releases do not all land on one page. Titles are unique
  within a space, and looking one up is what makes a repeat sync an update rather
  than a second page.
- **The body is the release note** — the Markdown the release page shows,
  converted to Confluence storage format: headings, lists, tables, links, and
  fenced code blocks as a `code` macro.

---

## Requirements

| | |
|---|---|
| Confluence | **Server or Data Center** — which is what the `SERVER` in every setting name refers to. The client speaks the v1 content API, and personal access tokens are a Server/Data Center feature |
| Credential | A Personal Access Token (7.9+), or a username and password |
| Rights | An account that may create and update pages in every space that releases are published to |
| Database | Migrations run: the release row carries the Confluence columns from migration `034` |

---

## 1. Credentials, and the instance defaults

Set in `.env` (see `.env.example`). The names carry the edition, as the Bitbucket
ones do: everything here is `CONFLUENCE_SERVER_*`, because the client speaks the
Server/Data Center API. A Cloud edition would be a `CONFLUENCE_CLOUD_*` sibling of
these rather than a rename of them.

| Variable | Default | What it does |
|---|---|---|
| `CONFLUENCE_SERVER_BASE_URL` | *(unset)* | The instance, e.g. `https://confluence.example.com`. Without it nothing is attempted |
| `CONFLUENCE_SERVER_TOKEN` | *(unset)* | A personal access token, sent as a Bearer token. Takes precedence over the pair below |
| `CONFLUENCE_SERVER_USERNAME` / `CONFLUENCE_SERVER_PASSWORD` | *(unset)* | Basic authentication, for instances without tokens |
| `CONFLUENCE_SERVER_SPACE_KEY` | *(unset)* | The **fallback** space: what a repository that names none of its own publishes to |
| `CONFLUENCE_SERVER_PARENT_PAGE_ID` | *(unset)* | The **fallback** parent page. Without one, pages are created at the root of the space |
| `CONFLUENCE_SERVER_SYNC_ENABLED` | `False` | Whether publishing writes to Confluence by itself |
| `CONFLUENCE_SERVER_VERIFY_SSL` | `True` | Turn off for an instance behind an internal CA |
| `CONFLUENCE_SERVER_TIMEOUT_SECONDS` | `15` | Timeout for a single Confluence request |

**What is set here is the instance default, not the whole configuration.** Where a
release actually goes is decided per repository — see the next section — and what
is set above is what every repository that names nothing of its own falls back to.
So `CONFLUENCE_SERVER_SPACE_KEY` may legitimately stay empty: a repository whose space is
set on its project needs nothing at this level.

`CONFLUENCE_SERVER_SYNC_ENABLED` is the master switch for the **automatic** path. While it
is off, publishing does not schedule a sync at all; the manual sync on the release
page still works, as long as the credentials above are set.

---

## 2. Where each release goes: three tiers

Each field resolves on its own, from the most specific level that decides it:

```
space key:       repository target  →  project target  →  instance default
parent page id:  repository target  →  project target  →  instance default
sync on/off:     repository target  →  project target  →  instance default
```

Resolving field by field is what makes the usual arrangement expressible: a space
per project, and a page per repository. Resolved as a whole, the space would have
to be repeated on every repository of a project.

Set on **System settings → Confluence Publishing** (requires the `manage`
permission on `settings`). The page shows, top to bottom:

1. **Instance defaults** — read-only, from the environment above, so the fallback
   floor is visible and the setting that produces it is not duplicated.
2. **Project defaults** — what the repositories of one project share. A project key
   is picked from the registry or typed.
3. **Repositories** — every registered repository with **the target it resolves to
   today and which level decided each part of it**, so the fallback never has to be
   worked out by hand. A repository with no space anywhere is called out; it cannot
   be published.

Add and edit happen in a dialog, one entry at a time, and each action is saved
immediately. Every field has an **Inherit / Override** switch: inheriting means
"not decided here", which is what lets the level below decide. The switch is
**Inherit / Enabled / Disabled** — turning it off keeps that one repository out of
Confluence without touching anything else.

### A worked example

Four projects with several repositories each, one space per project, and a page per
repository:

| Level | Set for | Space | Parent page | Sync |
|---|---|---|---|---|
| Instance | every repository | `DOCS` | *(none)* | on |
| Project | `PAY` | `PAYSPACE` | — | — |
| Repository | `PAY/pay-api` | — | `123456` | — |
| Repository | `TOOL/internal-lib` | — | — | off |

What that resolves to:

| Repository | Space (from) | Parent (from) | Sync (from) |
|---|---|---|---|
| `PAY/pay-api` | `PAYSPACE` (project) | `123456` (repository) | on (instance) |
| `PAY/pay-web` | `PAYSPACE` (project) | none (instance) | on (instance) |
| `ORD/order-api` | `DOCS` (instance) | none (instance) | on (instance) |
| `TOOL/internal-lib` | `DOCS` (instance) | none (instance) | **off (repository)** |

The space was set once per project, the parent page once per repository, and the
internal library was taken out of the integration in one click.

The configuration is one row in `system_settings` (`confluence_targets`), which is
what to copy between environments; the credentials and the base URL stay in the
environment and are never stored there.

---

## 3. What triggers a sync

| Action | Syncs? |
|---|---|
| **Publishing a release** — `POST /release/notes`, or publishing a draft by updating it | Yes, when the integration is configured, the switch is on, the repository is not switched off, and the release ends up published |
| **Editing a published release** — `PUT /release/notes/{id}`, any of title, notes, previous version, pre-release flag | Yes: the page is updated with what the release now says |
| **Writing a draft** — created as `draft`, or an edit that leaves it one | No. Publishing is what puts a release in front of people |
| **Importing releases** — `POST /release/notes/import` | **No.** An import brings in a repository's history at once, and writing all of it to Confluence is not what an import is for. Each imported release is synced by hand when it is wanted |
| **Pushing to the git provider** — `POST /release/notes/{id}/push` | No: it writes to the provider, not to the release's state |
| **Changing a target** — space, parent page or switch, in System settings | No. What is already written stays where it is; the change applies to what is written from then on |
| **The manual action** — release page → **Sync to Confluence** | Yes, always: see below |

The automatic path runs as a background task after the response, so a release is
never delayed by Confluence, and a failure is recorded on the release rather than
raised. Both automatic checkboxes are the `sync_to_confluence` field on the
request and default to `true`; the publish form offers it as **"Write to
Confluence as well"**, shown only where the instance is configured.

### The manual sync

`POST /api/v1/release/notes/{id}/confluence-sync`, offered on the release row as
**Sync to Confluence** (requires `manage` on `release_note`). It is not a second
copy of the automatic path: it is the answer to the cases that path cannot cover.

- the automatic path is off (`CONFLUENCE_SERVER_SYNC_ENABLED=False`), or was off when the
  release was published;
- the release failed, and the cause has been fixed — the retry is also what clears
  the recorded failure;
- the release was published before its repository had a space configured, or before
  the integration existed at all;
- the release was **imported**, which never syncs by itself.

There is **no bulk sync**: releases that were never written are synced one at a
time. A draft is refused with `409` — only a published release is written.

---

## What a repeat sync does

| Situation | What happens |
|---|---|
| The release was synced before | The recorded page is updated in place; no second page |
| The page was deleted in Confluence since | The title is looked up in the target space, and the page is created again if it is gone |
| The space or parent page was changed | **Only pages created from then on follow the new target.** A page already written keeps the space it is in and the parent page it was created under: moving it is a call this integration does not make, and nothing is ever deleted |
| The application name changed in the registry | The page is renamed on the next sync, because it is updated by id rather than by title |

## Where to see what happened

On the release row:

- **View on Confluence** — the page, once it exists.
- **Confluence sync failed** — a badge with the reason on hover, so a failure is
  visible where the release is rather than only in a log.
- **Sync to Confluence** — retry, which clears the recorded failure on success.

Recorded on the release itself:

| Field | Meaning |
|---|---|
| `confluence_page_id` | The page this release is on |
| `confluence_url` | Its URL, which is what the badge links to |
| `confluence_synced_date` | When it last succeeded |
| `confluence_sync_error` | Why it last failed, cleared by the next success |

---

## API

| Endpoint | Permission | Purpose |
|---|---|---|
| `GET /api/v1/release/notes/confluence` | `read` on `release_note` | `{configured, auto_sync}` — whether the controls are offered at all |
| `POST /api/v1/release/notes/{id}/confluence-sync` | `manage` on `release_note` | Sync one release; answers `{synced, page_url, message}`, or `409` for a draft |
| `GET /api/v1/rbac/settings/confluence` | `manage` on `settings` | The configuration, the instance defaults, and what each repository resolves to |
| `PUT /api/v1/rbac/settings/confluence` | `manage` on `settings` | Replace `{projects: [...], repositories: [...]}` wholesale |

---

## Troubleshooting

Every message below appears in the badge on the release row (and in its tooltip),
or as the answer to a manual sync.

| Message | What it means | What to do |
|---|---|---|
| `Not synced: Confluence is not configured` | `CONFLUENCE_SERVER_BASE_URL` or the credentials are unset | Set them and restart the backend |
| `No Confluence space is configured for PROJ/repo` | No space at any of the three levels for that repository | Set one on the repository, on its project, or in the environment |
| `Not synced: sync is switched off for PROJ/repo` | The resolved switch is off: an explicit off on the repository or its project, or the instance switch with nothing overriding it | Turn that repository back on in the Confluence card, or set `CONFLUENCE_SERVER_SYNC_ENABLED=True` |
| `Confluence returned 401: ...` / `403: ...` | The credential is rejected, or that account may not write to the space | Check the token, and the account's rights in the space |
| `Confluence returned 404: ...` | A space key that does not exist, or a parent page that is gone or not visible to that account | Check the space and parent page for that repository |
| `Confluence returned 400: ...` | Confluence refused the payload — most often a parent page in another space, which is not a place a page can be created | Check the parent page id of that repository, and that it belongs to the same space |
| `Confluence could not be reached: ...` | Network, DNS, or TLS | For an internal CA, set `CONFLUENCE_SERVER_VERIFY_SSL=False` |
| `Confluence returned a body that is not JSON` | Something answered instead of the API — a proxy or a login page | Check `CONFLUENCE_SERVER_BASE_URL`: it is the instance, without a path |
| A second page appeared | The release was re-imported (so the recorded page id was gone) **and** its title or space had changed, so the lookup found nothing | Look for the older page by title and delete it there; nothing in this integration deletes pages |

A sync never fails a release: the release is published either way, and the failure
waits on the release row for a retry.

---

## Verifying an installation

### With no instance to point at

`scripts/mock_confluence_api.py` serves the four calls the sync makes, so the whole
path can be exercised without a Confluence to hand:

```bash
uv run python scripts/mock_confluence_api.py --port 8099 --parent-id 123456
```

```
CONFLUENCE_SERVER_BASE_URL=http://127.0.0.1:8099
CONFLUENCE_SERVER_TOKEN=mock-token
CONFLUENCE_SERVER_SYNC_ENABLED=True
```

Publish a release, or sync one by hand, and watch it arrive: every request is
logged as it is served, and http://127.0.0.1:8099/ lists the pages written so far
with their space, title, parent page and version. That page is also the quickest
way to see that a second sync updated the first page rather than adding another.

It refuses the three mistakes worth catching, as an instance would:

- no credential → `401`, so the token is part of what is under test;
- a parent page id it was not told about → `400` (start it with `--parent-id <id>`
  to stand in for a page that exists);
- an update that does not move the version on → `409`.

Pages live in memory only, so restarting it forgets them.

### Against a real instance

1. `GET /api/v1/release/notes/confluence` answers `{"configured": true, ...}`.
   `configured` is about the base URL and the credentials; it says nothing about a
   particular repository.
2. Open **System settings → Confluence Publishing** and check the instance block
   shows the base URL and **Credentials ready**.
3. In the repository table, every repository that should publish shows a space — no
   **no space configured** — and the level that decided it looks right.
4. Sync one release from the release row and confirm **View on Confluence** appears,
   then open the page: it should sit under the parent page of that repository, with
   the notes as the release page shows them.

Working without a target for a repository that needs one is reported on the release
row (`No Confluence space is configured for PROJ/repo`), which is how a missing
target is noticed in the first place.
