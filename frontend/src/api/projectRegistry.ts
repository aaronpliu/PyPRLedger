import request from '@/utils/request'

export interface ProjectRegistry {
  id?: number
  app_name: string
  project_key: string
  repository_slug: string
  description?: string | null
  created_date?: string
  updated_date?: string
}

export interface AppInfo {
  app_name: string
  project_count: number
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

  async getAppName(projectKey: string, repositorySlug: string): Promise<{ app_name: string }> {
    return request.get(`/projects/${projectKey}/${repositorySlug}/app-name`)
  },

  // Admin endpoints (require system_admin role)
  async registerProject(
    appName: string,
    projectKey: string,
    repositorySlug: string,
    description?: string
  ): Promise<{
    message: string
    app_name: string
    project_key: string
    repository_slug: string
    description?: string
  }> {
    return request.post('/admin/registry/register', null, {
      params: {
        app_name: appName,
        project_key: projectKey,
        repository_slug: repositorySlug,
        ...(description && { description }),
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
