import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import ElementPlus, { ElSelect } from 'element-plus'
import { createI18n } from 'vue-i18n'
import ProjectRegistryManagementView from '@/views/admin/ProjectRegistryManagementView.vue'
import enMessages from '@/locales/en.json'
import { projectRegistryApi } from '@/api/projectRegistry'

// The page's own reads are the stand-ins: what it says about a registration's
// dependency-database name is the whole subject here. What the name is used for -
// and what happens when an administrator changes it - is answered by the API
// tests, where the request reaches the service.
const registry = vi.hoisted(() => ({
  entries: [] as Array<Record<string, unknown>>,
}))

vi.mock('@/api/projectRegistry', () => ({
  projectRegistryApi: {
    listApps: async () => [{ app_name: 'trmyapp', project_count: 2 }],
    listRegistryProjectsPaginated: async () => ({
      items: registry.entries,
      total: registry.entries.length,
      page: 1,
      page_size: 20,
    }),
    registerProject: vi.fn(),
    updateAppAlias: vi.fn(),
    updateRegistryKind: vi.fn(),
  },
}))

vi.mock('@/api/projects', () => ({
  projectsApi: {
    getAllProjects: async () => [{ project_key: 'CORE', project_name: 'Core' }],
    getProjectRepositories: async () => [{ repository_slug: 'app', repository_name: 'App' }],
  },
}))

function registration(patch: Record<string, unknown> = {}) {
  return {
    id: 1,
    app_name: 'trmyapp',
    app_alias: 'myapptr',
    registry_kind: 'application',
    project_key: 'CORE',
    repository_slug: 'app',
    git_provider: 'bitbucket_server',
    description: null,
    created_date: '2026-10-01T00:00:00+00:00',
    updated_date: '2026-10-01T00:00:00+00:00',
    ...patch,
  }
}

async function mountView(entries = [registration()]) {
  registry.entries = entries
  const i18n = createI18n({ legacy: false, locale: 'en', messages: { en: enMessages } })
  const wrapper = mount(ProjectRegistryManagementView, {
    global: { plugins: [ElementPlus, i18n] },
  })
  await flushPromises()
  return wrapper
}

beforeEach(() => {
  registry.entries = []
})

describe('ProjectRegistryManagementView', () => {
  it('shows the name the dependency database knows a registration by', async () => {
    const wrapper = await mountView()

    const row = wrapper.findAll('.el-table__row')[0]
    expect(row.find('[data-test="app-alias"]').text()).toBe('myapptr')
    // and the name is editable, which is what an alias that does not follow needs
    expect(row.findAll('button').map((button) => button.text())).toContain('Edit Alias')
  })

  it('says an empty alias follows the application name', async () => {
    // an empty alias is not a gap in the table: it is the application name in use
    const wrapper = await mountView([registration({ app_alias: null })])

    const row = wrapper.findAll('.el-table__row')[0]
    expect(row.find('[data-test="app-alias"]').exists()).toBe(false)
    expect(row.text()).toContain('Follows trmyapp')
  })

  it('says what a registration is, and lets the kind be set from the row', async () => {
    const wrapper = await mountView([registration({ registry_kind: 'application' })])

    const row = wrapper.findAll('.el-table__row')[0]
    expect(row.find('[data-test="registry-kind"]').text()).toBe('Application')

    // the pages that read an application's releases leave out what is marked as a
    // package, so this is the switch that takes a repository out of their pickers
    const control = row.find('[data-test="kind-select"]')
    expect(control.exists()).toBe(true)

    wrapper
      .findAllComponents(ElSelect)
      .find((select) => select.attributes('data-test') === 'kind-select')!
      .vm.$emit('change', 'package')
    await flushPromises()

    expect(vi.mocked(projectRegistryApi.updateRegistryKind)).toHaveBeenCalledWith(
      'CORE',
      'app',
      'package',
    )
  })

  it('says a registration nobody has classified is not set', async () => {
    const wrapper = await mountView([registration({ registry_kind: null })])

    // an empty kind is not a gap in the table: it is what every registration starts
    // as, and it keeps behaving as it always did
    expect(wrapper.findAll('.el-table__row')[0].find('[data-test="registry-kind"]').text()).toBe(
      'Not set',
    )
  })
})
