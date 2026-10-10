import request from '@/utils/request'

export interface ProjectRegistry {
  id?: number
  app_name: string
  /**
   * The name the dependency database knows this application as, when that differs
   * from app_name. Empty means the application name is used.
   */
  app_alias?: string | null
  /**
   * What this registration is: `application` for a repository whose releases the
   * dependency database holds, `package` for one that is only a dependency of
   * another. The pages that read an application's releases offer the first alone.
   */
  registry_kind?: string
  project_key: string
  repository_slug: string
  git_provider?: string
  description?: string | null
  created_date?: string
  updated_date?: string
}

export interface ProjectRegistryListResponse {
  items: ProjectRegistry[]
  total: number
  page: number
  page_size: number
}

export interface AppInfo {
  app_name: string
  project_count: number
}

export interface ProjectInfo {
  project_key: string
  project_name: string
}

export interface RepositoryInfo {
  repository_slug: string
  repository_name: string
}

export const projectRegistryApi = {
  // Public endpoints
  async listApps(): Promise<AppInfo[]> {
    return request.get('/apps')
  },

  async listProjectsByApp(appName: string): Promise<ProjectRegistry[]> {
    return request.get(`/apps/${appName}/projects`)
  },

  async listAllRegisteredProjects(): Promise<ProjectRegistry[]> {
    return request.get('/apps/registry/all')
  },

  async listRegistryProjectsPaginated(params: {
    app_name?: string
    search?: string
    page?: number
    page_size?: number
  }): Promise<ProjectRegistryListResponse> {
    return request.get('/admin/registry/projects', { params })
  },

  async getAppName(projectKey: string, repositorySlug: string): Promise<{ app_name: string }> {
    return request.get(`/projects/${projectKey}/${repositorySlug}/app-name`)
  },

  // Admin endpoints (require system_admin role)
  async registerProject(
    appName: string,
    projectKey: string,
    repositorySlug: string,
    description?: string,
    gitProvider?: string,
    appAlias?: string,
    registryKind?: string
  ): Promise<{
    message: string
    app_name: string
    app_alias?: string | null
    registry_kind?: string
    project_key: string
    repository_slug: string
    git_provider?: string
    description?: string
  }> {
    return request.post('/admin/registry/register', null, {
      params: {
        app_name: appName,
        project_key: projectKey,
        repository_slug: repositorySlug,
        ...(description && { description }),
        ...(gitProvider && { git_provider: gitProvider }),
        ...(appAlias && { app_alias: appAlias }),
        ...(registryKind && { registry_kind: registryKind }),
      },
    })
  },

  /**
   * Say whether a registration is an application or a package.
   *
   * This is what takes a repository out of the Release Dependency Graph and App
   * Diff pickers - which read an application's releases, and so offer applications
   * alone - and what puts it back.
   */
  async updateRegistryKind(
    projectKey: string,
    repositorySlug: string,
    registryKind: 'application' | 'package'
  ): Promise<{
    message: string
    project_key: string
    repository_slug: string
    app_name: string
    registry_kind: string
  }> {
    return request.put('/admin/registry/kind', null, {
      params: {
        project_key: projectKey,
        repository_slug: repositorySlug,
        registry_kind: registryKind,
      },
    })
  },

  /**
   * Set or clear the dependency database name of one repository.
   *
   * Only the Releases pages ask the dependency database, and they ask it for this
   * name; an empty value puts the application name back in use.
   */
  async updateAppAlias(
    projectKey: string,
    repositorySlug: string,
    appAlias: string | null
  ): Promise<{
    message: string
    project_key: string
    repository_slug: string
    app_name: string
    app_alias: string | null
    dependency_app_name: string
  }> {
    return request.put('/admin/registry/app-alias', null, {
      params: {
        project_key: projectKey,
        repository_slug: repositorySlug,
        // an explicit empty value clears it, so it is sent rather than left out
        app_alias: appAlias ?? '',
      },
    })
  },

  async updateProjectApp(
    projectKey: string,
    repositorySlug: string,
    newAppName: string
  ): Promise<{
    message: string
    project_key: string
    repository_slug: string
    old_app_name: string
    new_app_name: string
  }> {
    return request.put('/admin/registry/update', null, {
      params: {
        project_key: projectKey,
        repository_slug: repositorySlug,
        new_app_name: newAppName,
      },
    })
  },

  async unregisterProject(
    projectKey: string,
    repositorySlug: string
  ): Promise<{
    message: string
    project_key: string
    repository_slug: string
  }> {
    return request.delete('/admin/registry/unregister', {
      params: {
        project_key: projectKey,
        repository_slug: repositorySlug,
      },
    })
  },
}
