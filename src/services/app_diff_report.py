"""Standalone HTML report for the App Diff comparison, rendered server-side.

The page renders its own view of the comparison; this renderer draws the same
information as one self-contained document a CI pipeline can download, archive
or mail after a build: one version matrix, then one section per adjacent
release pair with the application's own commits and each moved package's
commits. Everything from the providers is escaped, every known commit URL is
emitted as a link, and "not contained" commits are highlighted as the page
highlights them - a defect in red, never a neutral note.

The copy is English on purpose: the report leaves the process for CI systems,
whose tooling reads it unattended.
"""

from __future__ import annotations

from datetime import UTC, datetime
from html import escape
from typing import Any

from src.schemas.app_version_diff import (
    AppVersionDiffCode,
    AppVersionDiffInterval,
    AppVersionDiffResponse,
)


def _e(value: Any) -> str:
    return escape(str(value if value is not None else ""))


def _field(obj: Any, name: str) -> Any:
    """Read a commit field from either a pydantic model or a plain dict."""
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name, None)


def _first_line(message: str | None) -> str:
    if not message:
        return "-"
    return message.split("\n")[0]


_VERDICT_CLASS: dict[str, str] = {
    "contained": "ok",
    "missing": "missing",
    "inconclusive": "warn",
}

_STYLE = """
  :root { color-scheme: light; }
  * { box-sizing: border-box; }
  body { margin: 0; padding: 32px; background: #f5f7fa; color: #1f2937;
         font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; }
  .report { max-width: 1100px; margin: 0 auto; background: #fff; border-radius: 12px; padding: 32px;
            box-shadow: 0 1px 3px rgba(15, 23, 42, 0.12); }
  h1 { margin: 0 0 4px; font-size: 24px; }
  h2 { margin: 32px 0 12px; font-size: 18px; border-bottom: 2px solid #e5e7eb; padding-bottom: 8px; }
  h3 { margin: 24px 0 8px; font-size: 14px; color: #374151; }
  h3.section-missing { color: #b91c1c; }
  .pkg-heading { margin: 20px 0 6px; font-size: 13px; }
  .subtitle { margin: 0 0 20px; color: #6b7280; font-size: 13px; }
  table { border-collapse: collapse; width: 100%; }
  table.meta { margin: 0 0 16px; font-size: 13px; border: 1px solid #e5e7eb; border-radius: 6px; overflow: hidden; }
  table.meta th { width: 200px; text-align: left; vertical-align: top; background: #f3f4f6;
                  color: #374151; font-weight: 600; padding: 8px 12px; border: 1px solid #e5e7eb; white-space: nowrap; }
  table.meta td { padding: 8px 12px; border: 1px solid #e5e7eb; word-break: break-word; }
  table.data { font-size: 13px; margin-bottom: 8px; border: 1px solid #e5e7eb; }
  table.data th { background: #f3f4f6; text-align: left; font-weight: 600; padding: 8px 10px;
                  border-bottom: 1px solid #e5e7eb; white-space: nowrap; }
  table.data td { padding: 8px 10px; border-bottom: 1px solid #f1f5f9; vertical-align: top; }
  table.data tr:nth-child(even) td { background: #fafafa; }
  table.data.matrix td { white-space: nowrap; }
  table.data td.pkg { font-weight: 600; }
  table.data tr.self td.pkg { background: #f0f7ff; }
  a { color: #2563eb; text-decoration: none; }
  a:hover { text-decoration: underline; }
  .mono { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }
  .muted { color: #9ca3af; font-size: 13px; }
  .status { display: inline-block; margin: 0 0 12px; padding: 6px 14px; border-radius: 999px;
            font-size: 13px; font-weight: 600; }
  .status-ok { background: #dcfce7; color: #166534; }
  .status-info { background: #e0e7ff; color: #3730a3; }
  .status-missing { background: #fee2e2; color: #991b1b; box-shadow: inset 0 0 0 1px #fca5a5; }
  .status-warn { background: #fef3c7; color: #92400e; box-shadow: inset 0 0 0 1px #fcd34d; }
  .warning { margin: 0 0 12px; color: #92400e; font-size: 13px; }
  .stats { display: flex; flex-wrap: wrap; gap: 10px; margin: 12px 0 4px; }
  .stat { flex: 1 1 120px; border: 1px solid #e5e7eb; border-radius: 8px; padding: 10px;
          text-align: center; background: #fafafa; }
  .stat-value { display: block; font-size: 20px; font-weight: 700; }
  .stat-label { display: block; font-size: 11px; color: #6b7280; }
  .stat-ok { border-color: #bbf7d0; background: #f0fdf4; }
  .stat-missing { border-color: #fca5a5; border-left: 4px solid #dc2626; background: #fef2f2; }
  .stat-missing .stat-value { color: #dc2626; }
  .stat-warn { border-color: #fcd34d; background: #fffbeb; }
  .cell-ok { color: #15803d; font-weight: 600; }
  .cell-missing { color: #b91c1c; font-weight: 700; }
  .commit-tr.missing td { background: #fef2f2; box-shadow: inset 3px 0 0 #dc2626; }
  footer { margin-top: 32px; color: #9ca3af; font-size: 12px; text-align: center; }
  @media print { body { background: #fff; padding: 0; } .report { box-shadow: none; border-radius: 0; } }
"""


def _meta_row(label: str, value: Any, url: str | None = None) -> str:
    if value is None or value == "":
        return ""
    cell = (
        f'<a href="{_e(url)}" target="_blank" rel="noopener">{_e(value)}</a>'
        if url
        else _e(value)
    )
    return f"<tr><th>{_e(label)}</th><td>{cell}</td></tr>"


def _meta_table(rows: list[str]) -> str:
    body = "\n      ".join(row for row in rows if row)
    if not body:
        return ""
    return f'<table class="meta">\n      {body}\n    </table>'


def _stat(label: str, value: Any, tone: str | None = None) -> str:
    tone_class = f" stat-{tone}" if tone else ""
    return (
        f'<div class="stat{tone_class}"><span class="stat-value">{_e(value)}</span>'
        f'<span class="stat-label">{_e(label)}</span></div>'
    )


def _commit_table(commits: list[dict[str, Any]] | None, missing: bool = False) -> str:
    rows = commits or []
    if not rows:
        return '<p class="muted">No commits.</p>'

    body_parts: list[str] = []
    for commit in rows:
        sha = _e(_field(commit, "display_id") or _field(commit, "id"))
        url = _field(commit, "url")
        sha_cell = (
            f'<a href="{_e(url)}" target="_blank" rel="noopener">{sha}</a>' if url else sha
        )
        author = _field(commit, "author_name") or _field(commit, "author_username") or "-"
        username = _field(commit, "author_username")
        author_cell = (
            f'<span class="muted">@{_e(username)}</span>' if username else _e(author)
        )
        timestamp = _field(commit, "author_timestamp")
        when = (
            datetime.fromtimestamp(timestamp / 1000, tz=UTC).strftime("%Y-%m-%d")
            if timestamp
            else "-"
        )
        message = _e(_first_line(_field(commit, "message")))
        full = _e(_field(commit, "message") or "")
        row_class = "commit-tr missing" if missing else ""
        body_parts.append(
            f'<tr class="{row_class}">'
            f'<td class="mono">{sha_cell}</td>'
            f"<td>{author_cell}</td>"
            f'<td class="mono">{_e(when)}</td>'
            f'<td title="{full}">{message}</td>'
            "</tr>"
        )

    return (
        '<table class="data">'
        "<thead><tr>"
        "<th>Commit</th><th>Author</th><th>Date</th><th>Message</th>"
        "</tr></thead>"
        f"<tbody>{''.join(body_parts)}</tbody>"
        "</table>"
    )


def _code_status(code: AppVersionDiffCode | None) -> str:
    if not code:
        return ""
    if code.deferred:
        return '<p class="warning">Deferred: the comparison of this package is queued.</p>'
    if code.unavailable:
        return f'<p class="warning">Unavailable: {_e(code.unavailable)}</p>'
    badge = (
        f'<span class="status status-{_VERDICT_CLASS[code.verdict]}">'
        f"{_e(code.verdict.replace('_', ' '))}</span>"
    )
    added = f'<span class="cell-ok">{code.added_count} added</span>'
    missing = (
        f'<span class="cell-missing">{code.missing_count} not contained</span>'
        if code.missing_count
        else ""
    )
    return f'<p>{badge} {added}{" · " + missing if missing else ""}</p>'


def _code_commits(code: AppVersionDiffCode | None) -> str:
    if not code or code.deferred or code.unavailable:
        return ""
    parts: list[str] = []
    if code.missing_commits:
        parts.append(
            f'<h3 class="section-missing">Not contained ({len(code.missing_commits)})</h3>'
        )
        parts.append(_commit_table(code.missing_commits, missing=True))
    if code.added_commits:
        parts.append(f"<h3>Added ({len(code.added_commits)})</h3>")
        parts.append(_commit_table(code.added_commits))
    return "\n  ".join(parts)


def _matrix_section(result: AppVersionDiffResponse) -> str:
    head = "".join(f"<th>{_e(release.ref)}</th>" for release in result.releases)
    rows: list[str] = []
    for row in result.rows:
        cells = "".join(
            f'<td class="matrix">{_e(version) if version else "-"}</td>'
            for version in row.versions
        )
        self_class = " self" if row.kind == "application" else ""
        rows.append(f'<tr><td class="pkg{self_class}">{_e(row.name)}</td>{cells}</tr>')

    return (
        '<section class="report-section">'
        f"<h2>1. Version Matrix</h2>"
        '<table class="data matrix">'
        f'<thead><tr><th>Package</th>{head}</tr></thead>'
        f"<tbody>{''.join(rows)}</tbody>"
        "</table>"
        "</section>"
    )


def _package_overview(interval: AppVersionDiffInterval) -> str:
    packages = interval.packages
    if not packages:
        return '<p class="muted">No packages moved.</p>'

    body_parts: list[str] = []
    for pkg in packages:
        if pkg.state == "added":
            move = f"&mdash; &rarr; {_e(pkg.target_version)}"
        elif pkg.state == "removed":
            move = f"{_e(pkg.source_version)} &rarr; &mdash;"
        else:
            move = f"{_e(pkg.source_version)} &rarr; {_e(pkg.target_version)}"
        code = pkg.code
        if not code:
            commits_cell = ""
        elif code.deferred:
            commits_cell = _e("deferred")
        elif code.unavailable:
            commits_cell = _e(f"unavailable: {code.unavailable}")
        else:
            commits_cell = (
                f"{_e(code.verdict.replace('_', ' '))} &middot; {code.added_count}&uarr; / "
                f"{code.missing_count}&#10007;"
            )
        body_parts.append(
            "<tr>"
            f'<td class="pkg">{_e(pkg.name)}</td>'
            f"<td>{_e(pkg.state)}</td>"
            f'<td class="mono">{move}</td>'
            f"<td>{commits_cell}</td>"
            "</tr>"
        )

    return (
        '<table class="data">'
        "<thead><tr>"
        "<th>Package</th><th>State</th><th>Version Move</th><th>Commits</th>"
        "</tr></thead>"
        f"<tbody>{''.join(body_parts)}</tbody>"
        "</table>"
    )


def _interval_section(interval: AppVersionDiffInterval, index: int) -> str:
    summary = interval.summary or {}
    heading = f"{index + 2}. {_e(interval.source_ref)} &rarr; {_e(interval.target_ref)}"
    verdict = "Changed" if interval.dependencies_moved else "Identical"
    completeness = "" if interval.complete else " · incomplete"
    downgrade = summary.get("downgrade") or 0

    package_sections: list[str] = []
    for pkg in interval.packages:
        if not pkg.code or pkg.code.deferred or pkg.code.unavailable:
            continue
        if pkg.code.added_count + pkg.code.missing_count == 0:
            continue
        move = f"{pkg.source_version or '—'} → {pkg.target_version or '—'}"
        package_sections.append(
            f'<h4 class="pkg-heading">{_e(pkg.name)} <span class="muted">{_e(move)}</span></h4>'
        )
        package_sections.append(_code_status(pkg.code))
        package_sections.append(_code_commits(pkg.code))

    return (
        '<section class="report-section">'
        f"<h2>{heading}</h2>"
        f'<p><span class="status status-info">{_e(verdict)}</span>'
        f'{_e(completeness)}</p>'
        '<div class="stats">'
        f"{_stat('Changed', summary.get('changed') or 0)}"
        f"{_stat('Added', summary.get('added') or 0, 'ok')}"
        f"{_stat('Removed', summary.get('removed') or 0, 'warn')}"
        f"{_stat('Downgrade (risk)', downgrade, 'missing' if downgrade else None)}"
        "</div>"
        + _package_overview(interval)
        + "<h3>Commit Details</h3>"
        + (
            f"<h3>Application</h3>{_code_status(interval.code)}{_code_commits(interval.code)}"
            if interval.code
            else ""
        )
        + "\n  ".join(package_sections)
        + "</section>"
    )


def render_app_diff_report(
    result: AppVersionDiffResponse,
    generated_at: datetime | None = None,
) -> str:
    """The full comparison as one self-contained HTML document."""
    generated = (generated_at or datetime.now(UTC)).strftime("%Y-%m-%d %H:%M:%S")

    sections = [
        _matrix_section(result),
        *[_interval_section(interval, index) for index, interval in enumerate(result.intervals)],
    ]

    meta = _meta_table(
        [
            _meta_row("Application", result.app_name),
            _meta_row("Project", result.project_key),
            _meta_row("Repository", result.repository_slug),
            _meta_row("Git provider", result.git_provider),
            _meta_row("Verdict", result.verdict),
            _meta_row("Generated at", generated),
        ]
    )

    title = f"App Diff - {result.app_name or result.repository_slug}"
    body = "\n".join(sections)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_e(title)}</title>
<style>{_STYLE}</style>
</head>
<body>
<div class="report">
  <h1>App Diff</h1>
  <p class="subtitle">{_e(result.project_key)} / {_e(result.repository_slug)} &middot; {_e(result.app_name)}</p>
  {meta}
  {body}
  <footer>PR Ledger</footer>
</div>
</body>
</html>"""
