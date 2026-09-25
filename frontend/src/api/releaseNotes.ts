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
  previous_version?: string | null
  max_commits?: number
  include_authors?: boolean
}

export interface PreviewCommit {
  id: string
  display_id?: string | null
  author_name?: string | null
  message?: string | null
  url?: string | null
}

export interface ReleaseNotePreviewResponse {
  version: string
  previous_version?: string | null
  suggested_name: string
  body: string
  commit_count: number
  commits: PreviewCommit[]
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
}
