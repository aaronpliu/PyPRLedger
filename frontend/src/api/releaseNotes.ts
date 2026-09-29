import request from '@/utils/request'

export type ReleaseNoteStatus = 'draft' | 'published'

export interface ReleaseNote {
  id: number
  project_key: string
  repository_slug: string
  tag_name: string
  name: string
  body: string
  previous_tag?: string | null
  status: ReleaseNoteStatus
  is_prerelease: boolean
  /** Latest published, non pre-release version of the repository */
  is_latest: boolean
  author?: string | null
  /** Profile picture of the author (only when the account has one) */
  author_avatar_url?: string | null
  published_date?: string | null
  created_date?: string | null
  updated_date?: string | null
  /** Provider side release (set when pushed to / imported from GitHub Enterprise) */
  external_provider?: string | null
  external_id?: string | null
  external_url?: string | null
}

export interface ReleaseNoteListResponse {
  total: number
  items: ReleaseNote[]
}

export interface ReleaseNoteCoordinates {
  project_key: string
  repository_slug: string
  workspace_slug?: string | null
  git_provider?: string | null
}

export interface ReleaseNoteCreateRequest extends ReleaseNoteCoordinates {
  tag_name: string
  name?: string | null
  body?: string
  previous_tag?: string | null
  status?: ReleaseNoteStatus
  is_prerelease?: boolean
}

export interface ReleaseNoteUpdateRequest {
  name?: string | null
  body?: string
  previous_tag?: string | null
  status?: ReleaseNoteStatus
  is_prerelease?: boolean
}

export interface ReleaseNotePushRequest extends ReleaseNoteCoordinates {
  /** Branch/commit the tag is created from when the tag does not exist yet */
  target_commitish?: string | null
  update_existing?: boolean
}

export interface ReleaseNoteImportRequest extends ReleaseNoteCoordinates {
  limit?: number
  overwrite?: boolean
}

export interface ReleaseNoteImportResponse {
  imported: number
  updated: number
  skipped: number
  items: ReleaseNote[]
}

export interface ReleaseNotePreviewRequest extends ReleaseNoteCoordinates {
  version: string
  /** Leave it out to let the server resolve the predecessor from the repository tags */
  previous_version?: string | null
  max_commits?: number
  include_authors?: boolean
  /** Re-resolve the release scope instead of reusing the cached resolution */
  refresh?: boolean
  /** Language of the generated prose (section titles and summary), e.g. 'zh-CN' */
  language?: string
  /** Ask the configured LLM for a summary paragraph and a section per commit */
  summarize?: boolean
}

export interface PreviewCommit {
  id: string
  display_id?: string | null
  author_name?: string | null
  /** Provider login / account slug of the author (when the provider reports one) */
  author_username?: string | null
  /** Web URL of the author profile */
  author_url?: string | null
  message?: string | null
  url?: string | null
}

/** How the release scope base was obtained: proven ('ancestor'), inferred from the tag order, or supplied. */
export type ReleaseScopeSource = 'explicit' | 'ancestor' | 'name_order' | 'none'

/** Why the scope looks the way it does; the last two mean the commits come from the full history. */
export type ReleaseScopeReason = 'provided' | 'resolved' | 'first_release' | 'unresolved'

export interface ReleaseNotePreviewResponse {
  version: string
  /** Scope base: what was supplied, or the predecessor the server resolved */
  previous_version?: string | null
  /** Revision the scope base was pinned to (when known) */
  previous_sha?: string | null
  /** Revision the released ref was pinned to (when known) */
  version_sha?: string | null
  previous_source?: ReleaseScopeSource
  /** True only for a supplied base or one proven to be an ancestor */
  previous_verified?: boolean
  scope_reason?: ReleaseScopeReason
  suggested_name: string
  body: string
  /** Size of the release scope (a lower bound when a scan was capped) */
  commit_count: number
  commits: PreviewCommit[]
  truncated: boolean
  /** Summary paragraph of the release, when one was written for it */
  summary?: string | null
  /** Whether the prose came from the commit subjects alone or from the LLM */
  summary_source?: 'deterministic' | 'llm'
  /** Why the summary stayed deterministic although the AI pass was asked for */
  summary_notice?: 'not_configured' | 'provider_error' | 'unreadable_answer' | 'failed' | null
  /** What the provider answered when it refused the call */
  summary_error?: string | null
}

export interface ReleaseNoteExportRequest extends ReleaseNoteCoordinates {
  /** The releases to export, in any order (the document is ordered newest first) */
  ids?: number[]
  /** Export every release matching `status` instead of naming them */
  select_all?: boolean
  /** Filter for `select_all`; ignored when `ids` is used */
  status?: ReleaseNoteStatus
}

export interface ReleaseNoteExportResponse {
  /** Suggested filename for the document */
  filename: string
  /** The markdown document */
  content: string
  /** Number of releases written into the document */
  count: number
  /** Requested releases that do not exist or belong to another repository */
  skipped_ids: number[]
  /** True when more releases matched than one export holds (only the newest are written) */
  truncated: boolean
}

export const releaseNotesApi = {
  /** List the version releases of a repository (drafts included), newest first. */
  async list(params: {
    project_key: string
    repository_slug: string
    status?: ReleaseNoteStatus
    limit?: number
    offset?: number
  }): Promise<ReleaseNoteListResponse> {
    const response = await request.get('/release/notes', { params })
    return response.data || response
  },

  /** Fetch a single release. */
  async get(noteId: number): Promise<ReleaseNote> {
    const response = await request.get(`/release/notes/${noteId}`)
    return response.data || response
  },

  /** Draft or publish a version release. */
  async create(payload: ReleaseNoteCreateRequest): Promise<ReleaseNote> {
    const response = await request.post('/release/notes', payload)
    return response.data || response
  },

  /** Update a release (title, notes, pre-release flag, state). */
  async update(noteId: number, payload: ReleaseNoteUpdateRequest): Promise<ReleaseNote> {
    const response = await request.put(`/release/notes/${noteId}`, payload)
    return response.data || response
  },

  /** Delete a release. */
  async remove(noteId: number): Promise<{ message: string }> {
    const response = await request.delete(`/release/notes/${noteId}`)
    return response.data || response
  },

  /** Draft release notes (markdown) from the commits of a release scope. */
  async preview(payload: ReleaseNotePreviewRequest): Promise<ReleaseNotePreviewResponse> {
    const response = await request.post('/release/notes/preview', payload)
    return response.data || response
  },

  /** Publish the release on the git provider (GitHub Enterprise Releases). */
  async push(noteId: number, payload: ReleaseNotePushRequest): Promise<ReleaseNote> {
    const response = await request.post(`/release/notes/${noteId}/push`, payload)
    return response.data || response
  },

  /** Import the releases of a repository from the git provider. */
  async importReleases(payload: ReleaseNoteImportRequest): Promise<ReleaseNoteImportResponse> {
    const response = await request.post('/release/notes/import', payload)
    return response.data || response
  },

  /** Export one or more releases as a single markdown document. */
  async exportNotes(payload: ReleaseNoteExportRequest): Promise<ReleaseNoteExportResponse> {
    const response = await request.post('/release/notes/export', payload)
    return response.data || response
  },
}
