import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import ElementPlus, { ElMessage, ElMessageBox } from 'element-plus'
import { createI18n } from 'vue-i18n'
import dayjs from 'dayjs'
import SystemSettingsView from '@/views/admin/SystemSettingsView.vue'
import {
  rbacApi,
  type BannerItem,
  type ConfluenceResolvedTarget,
  type ConfluenceSettings,
  type ConfluenceTargetsPayload,
} from '@/api/rbac'
import enMessages from '@/locales/en.json'

// `createBanner` is a real helper the view uses, so the module is only partly faked.
vi.mock('@/api/rbac', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/api/rbac')>()
  return {
    ...actual,
    rbacApi: {
      getRegistrationEnabled: vi.fn(),
      updateRegistrationEnabled: vi.fn(),
      getLlmConfig: vi.fn(),
      updateLlmConfig: vi.fn(),
      getBanner: vi.fn(),
      updateBanner: vi.fn(),
      getConfluenceTargets: vi.fn(),
      updateConfluenceTargets: vi.fn(),
    },
  }
})

/* eslint-disable @typescript-eslint/no-explicit-any */
type AnyWrapper = any

const messages = enMessages.admin.systemSettings
const mountedWrappers: AnyWrapper[] = []
const START = '2026-10-01T00:00:00+08:00'

function banner(patch: Partial<BannerItem> = {}): BannerItem {
  return {
    id: 'b1',
    enabled: true,
    content: 'A notice',
    start_date: '',
    end_date: '',
    level: 'info',
    link_url: '',
    link_label: '',
    priority: 0,
    ...patch,
  }
}

async function mountView(banners: BannerItem[], confluence: ConfluenceSettings = noTargets()) {
  vi.mocked(rbacApi.getRegistrationEnabled).mockResolvedValue({ registration_enabled: true })
  vi.mocked(rbacApi.getLlmConfig).mockResolvedValue({
    enabled: false,
    model: '',
    base_url: '',
    has_api_key: false,
  })
  vi.mocked(rbacApi.getBanner).mockResolvedValue({ banners })
  vi.mocked(rbacApi.getConfluenceTargets).mockResolvedValue(confluence)
  // Answer the way the endpoint does, so the list the view keeps is the list it sent.
  vi.mocked(rbacApi.updateBanner).mockImplementation(async (data) => ({
    message: 'ok',
    banners: data.banners,
  }))
  vi.mocked(rbacApi.updateConfluenceTargets).mockImplementation(async (data) => ({
    message: 'ok',
    ...confluence,
    projects: data.projects,
    repositories: data.repositories,
  }))

  const i18n = createI18n({ legacy: false, locale: 'en', messages: { en: enMessages } })
  const wrapper = mount(SystemSettingsView, { global: { plugins: [ElementPlus, i18n] } })
  mountedWrappers.push(wrapper)
  await flushPromises()
  return {
    wrapper,
    dialog: () => wrapper.findComponent({ name: 'ElDialog' }),
    // The second dialog on the page: the banner card's comes first.
    targetDialog: () => wrapper.findAllComponents({ name: 'ElDialog' })[1],
  }
}

function lastSent(): BannerItem[] {
  const calls = vi.mocked(rbacApi.updateBanner).mock.calls
  return calls.length ? calls[calls.length - 1][0].banners : []
}

/** A repository as the server resolves it, with the level each value came from. */
function resolvedRow(patch: Partial<ConfluenceResolvedTarget> = {}): ConfluenceResolvedTarget {
  return {
    project_key: 'PROJ',
    repository_slug: 'my-repo',
    app_name: 'My App',
    space_key: 'DOC',
    parent_page_id: '',
    enabled: true,
    space_source: 'instance',
    parent_source: 'instance',
    enabled_source: 'instance',
    configured: false,
    ...patch,
  }
}

/** An instance with credentials and a space of its own, and nothing configured yet. */
function noTargets(patch: Partial<ConfluenceSettings> = {}): ConfluenceSettings {
  return {
    instance: {
      space_key: 'DOC',
      parent_page_id: '',
      enabled: true,
      base_url: 'https://confluence.local',
      has_credentials: true,
    },
    projects: [],
    repositories: [],
    resolved: [],
    ...patch,
  }
}

function lastTargets(): ConfluenceTargetsPayload {
  const calls = vi.mocked(rbacApi.updateConfluenceTargets).mock.calls
  return calls.length ? calls[calls.length - 1][0] : { projects: [], repositories: [] }
}

describe('SystemSettingsView banner management', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  afterEach(() => {
    mountedWrappers.splice(0).forEach((wrapper) => wrapper.unmount())
    vi.restoreAllMocks()
  })

  it('lists every stored banner with the state that matters', async () => {
    const { wrapper } = await mountView([
      banner({
        id: 'a',
        content: 'Freeze on Friday',
        level: 'warning',
        priority: 4,
        enabled: false,
        start_date: START,
      }),
      banner({ id: 'b', content: 'Shipped', level: 'success' }),
    ])

    const rows = wrapper.findAll('.el-table__row')
    expect(rows).toHaveLength(2)

    expect(rows[0].text()).toContain('Freeze on Friday')
    expect(rows[0].text()).toContain(messages.bannerLevelWarning)
    expect(rows[0].text()).toContain(enMessages.common.disabled)
    expect(rows[0].text()).toContain(dayjs(START).format('YYYY-MM-DD HH:mm'))
    expect(rows[0].text()).toContain('4')

    expect(rows[1].text()).toContain(messages.bannerLevelSuccess)
    // No bound at all reads as always on.
    expect(rows[1].text()).toContain(messages.bannerAlways)
  })

  it('says so when there is nothing to manage', async () => {
    const { wrapper } = await mountView([])

    expect(wrapper.findAll('.el-table__row')).toHaveLength(0)
    expect(wrapper.text()).toContain(messages.bannerEmpty)
  })

  it('adds a banner from the dialog', async () => {
    const { wrapper, dialog } = await mountView([])

    await wrapper.find('[data-test="banner-add"]').trigger('click')
    await dialog().find('textarea').setValue('New notice')
    await dialog().find('[data-test="banner-save"]').trigger('click')
    await flushPromises()

    expect(lastSent()).toHaveLength(1)
    expect(lastSent()[0]).toMatchObject({ content: 'New notice' })
    // The saved banner is on the page now, without reopening anything.
    expect(wrapper.findAll('.el-table__row')).toHaveLength(1)
  })

  it('opens one banner for editing and saves it back', async () => {
    const { wrapper, dialog } = await mountView([banner({ id: 'a', content: 'Before' })])

    await wrapper.find('[data-test="banner-edit"]').trigger('click')
    const textarea = dialog().find('textarea')
    expect((textarea.element as HTMLTextAreaElement).value).toBe('Before')

    await textarea.setValue('After')
    await dialog().find('[data-test="banner-save"]').trigger('click')
    await flushPromises()

    expect(lastSent()).toHaveLength(1)
    expect(lastSent()[0]).toMatchObject({ id: 'a', content: 'After' })
  })

  it('deletes the banner that was asked for, once confirmed', async () => {
    const confirm = vi.spyOn(ElMessageBox, 'confirm').mockResolvedValue('confirm' as any)
    const { wrapper } = await mountView([
      banner({ id: 'a', content: 'Keep' }),
      banner({ id: 'b', content: 'Drop' }),
    ])

    await wrapper.findAll('[data-test="banner-remove"]')[1].trigger('click')
    await flushPromises()

    expect(confirm).toHaveBeenCalled()
    expect(lastSent().map((item) => item.content)).toEqual(['Keep'])
    expect(wrapper.findAll('.el-table__row')).toHaveLength(1)
  })

  it('leaves everything alone when the delete is dismissed', async () => {
    vi.spyOn(ElMessageBox, 'confirm').mockRejectedValue('dismissed')
    const { wrapper } = await mountView([banner({ id: 'a', content: 'Still here' })])

    await wrapper.find('[data-test="banner-remove"]').trigger('click')
    await flushPromises()

    expect(rbacApi.updateBanner).not.toHaveBeenCalled()
    expect(wrapper.findAll('.el-table__row')).toHaveLength(1)
  })

  it('flips one banner on or off from the list, leaving the others alone', async () => {
    const { wrapper } = await mountView([
      banner({ id: 'a', content: 'Notice', enabled: true }),
      banner({ id: 'b', content: 'Other', enabled: true }),
    ])

    await wrapper.findAll('[data-test="banner-enabled"] input')[0].setValue(false)
    await flushPromises()

    expect(lastSent().map((item) => [item.id, item.enabled])).toEqual([
      ['a', false],
      ['b', true],
    ])
  })

  it('leaves the switch where it was when the write fails', async () => {
    // The view logs the failure; that noise is not what this test is about.
    vi.spyOn(console, 'error').mockImplementation(() => {})
    const { wrapper } = await mountView([banner({ id: 'a', content: 'Notice', enabled: true })])
    vi.mocked(rbacApi.updateBanner).mockRejectedValue(new Error('nope'))

    await wrapper.find('[data-test="banner-enabled"] input').setValue(false)
    await flushPromises()

    // The switch reports the stored state, not the click that failed to save.
    expect(wrapper.findComponent({ name: 'ElSwitch' }).props('modelValue')).toBe(true)
  })

  it('will not save a banner without a message', async () => {
    const { wrapper, dialog } = await mountView([])

    await wrapper.find('[data-test="banner-add"]').trigger('click')
    await dialog().find('[data-test="banner-save"]').trigger('click')
    await flushPromises()

    expect(rbacApi.updateBanner).not.toHaveBeenCalled()
  })
})

describe('SystemSettingsView Confluence publishing targets', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  afterEach(() => {
    mountedWrappers.splice(0).forEach((wrapper) => wrapper.unmount())
    vi.restoreAllMocks()
  })

  it('shows what each repository resolves to and which level decided it', async () => {
    const { wrapper } = await mountView(
      [],
      noTargets({
        projects: [
          { project_key: 'PROJ', space_key: 'PROJSPACE', parent_page_id: '', enabled: null },
        ],
        repositories: [
          {
            project_key: 'PROJ',
            repository_slug: 'api',
            space_key: '',
            parent_page_id: '555',
            enabled: null,
          },
        ],
        resolved: [
          resolvedRow({
            repository_slug: 'api',
            app_name: 'API',
            space_key: 'PROJSPACE',
            parent_page_id: '555',
            space_source: 'project',
            parent_source: 'repository',
            configured: true,
          }),
          resolvedRow({ repository_slug: 'web', app_name: 'Web' }),
          resolvedRow({
            repository_slug: 'unset',
            app_name: 'Unset',
            space_key: '',
            configured: true,
          }),
        ],
      })
    )

    // The instance defaults are on the page, so the fallback has a visible floor.
    expect(wrapper.text()).toContain('https://confluence.local')
    expect(wrapper.text()).toContain(messages.confluenceCredentialsReady)

    const rows = wrapper.findAll('[data-test="confluence-repositories"] .el-table__row')
    expect(rows).toHaveLength(3)

    // The value in use, and the level it came from, side by side.
    expect(rows[0].text()).toContain('PROJSPACE')
    expect(rows[0].text()).toContain(messages.confluenceSourceProject)
    expect(rows[0].text()).toContain('555')
    expect(rows[0].text()).toContain(messages.confluenceSourceRepository)
    expect(rows[1].text()).toContain(messages.confluenceSourceInstance)
    // A repository with no space anywhere is called out rather than left blank.
    expect(rows[2].text()).toContain(messages.confluenceNoSpace)
  })

  it('lists the project defaults and what each of them decides', async () => {
    const { wrapper } = await mountView(
      [],
      noTargets({
        projects: [
          { project_key: 'PROJ', space_key: 'PROJSPACE', parent_page_id: '', enabled: null },
          { project_key: 'OTHER', space_key: '', parent_page_id: '', enabled: false },
        ],
      })
    )

    const rows = wrapper.findAll('[data-test="confluence-projects"] .el-table__row')
    expect(rows).toHaveLength(2)
    expect(rows[0].text()).toContain('PROJSPACE')
    // A field the project says nothing about reads as inherited, not as empty.
    expect(rows[0].text()).toContain(messages.confluenceInherit)
    expect(rows[1].text()).toContain(enMessages.common.disabled)
  })

  it('says so when no project has a default of its own', async () => {
    const { wrapper } = await mountView([], noTargets())

    expect(wrapper.text()).toContain(messages.confluenceProjectsEmpty)
  })

  it('adds a project default, sending only what the dialog decided', async () => {
    const { wrapper, targetDialog } = await mountView([], noTargets({ resolved: [resolvedRow()] }))

    await wrapper.find('[data-test="confluence-project-add"]').trigger('click')
    await targetDialog().findComponent({ name: 'ElSelect' }).setValue('PROJ')
    await targetDialog().find('[data-test="confluence-target-space-override"] input').setValue(true)
    await targetDialog().find('[data-test="confluence-target-space"]').setValue('PROJSPACE')
    await targetDialog().find('[data-test="confluence-target-save"]').trigger('click')
    await flushPromises()

    // The parent page is left out of the entry entirely, which is exactly what
    // makes it fall through to the instance.
    expect(lastTargets()).toEqual({
      projects: [{ project_key: 'PROJ', space_key: 'PROJSPACE', parent_page_id: '', enabled: null }],
      repositories: [],
    })
    expect(wrapper.findAll('[data-test="confluence-projects"] .el-table__row')).toHaveLength(1)
  })

  it('overrides one repository without touching its project', async () => {
    const { wrapper, targetDialog } = await mountView(
      [],
      noTargets({
        projects: [
          { project_key: 'PROJ', space_key: 'PROJSPACE', parent_page_id: '', enabled: null },
        ],
        resolved: [resolvedRow({ space_key: 'PROJSPACE', space_source: 'project' })],
      })
    )

    await wrapper.find('[data-test="confluence-repository-edit"]').trigger('click')
    await targetDialog()
      .find('[data-test="confluence-target-parent-override"] input')
      .setValue(true)
    await targetDialog().find('[data-test="confluence-target-parent"]').setValue('555')
    await targetDialog().find('[data-test="confluence-target-save"]').trigger('click')
    await flushPromises()

    expect(lastTargets()).toEqual({
      projects: [
        { project_key: 'PROJ', space_key: 'PROJSPACE', parent_page_id: '', enabled: null },
      ],
      repositories: [
        {
          project_key: 'PROJ',
          repository_slug: 'my-repo',
          space_key: '',
          parent_page_id: '555',
          enabled: null,
        },
      ],
    })
  })

  it('reopens a stored target with its switches where they were left', async () => {
    const { wrapper, targetDialog } = await mountView(
      [],
      noTargets({
        projects: [
          { project_key: 'PROJ', space_key: 'PROJSPACE', parent_page_id: '9', enabled: false },
        ],
      })
    )

    await wrapper.find('[data-test="confluence-project-edit"]').trigger('click')

    // Both fields are decisions of this level, so both open filled in. An el-input
    // carries its attributes on the input itself, hence no `input` descendant.
    const space = targetDialog().find('[data-test="confluence-target-space"]')
    const parent = targetDialog().find('[data-test="confluence-target-parent"]')
    expect((space.element as HTMLInputElement).value).toBe('PROJSPACE')
    expect((parent.element as HTMLInputElement).value).toBe('9')
  })

  it('refuses a target that decides nothing', async () => {
    const warn = vi.spyOn(ElMessage, 'warning')
    const { wrapper, targetDialog } = await mountView([], noTargets({ resolved: [resolvedRow()] }))

    await wrapper.find('[data-test="confluence-project-add"]').trigger('click')
    await targetDialog().findComponent({ name: 'ElSelect' }).setValue('PROJ')
    await targetDialog().find('[data-test="confluence-target-save"]').trigger('click')
    await flushPromises()

    expect(warn).toHaveBeenCalledWith(messages.confluenceTargetEmpty)
    expect(rbacApi.updateConfluenceTargets).not.toHaveBeenCalled()
  })

  it('refuses a parent page that is not a number', async () => {
    const warn = vi.spyOn(ElMessage, 'warning')
    const { wrapper, targetDialog } = await mountView([], noTargets({ resolved: [resolvedRow()] }))

    await wrapper.find('[data-test="confluence-project-add"]').trigger('click')
    await targetDialog().findComponent({ name: 'ElSelect' }).setValue('PROJ')
    await targetDialog()
      .find('[data-test="confluence-target-parent-override"] input')
      .setValue(true)
    await targetDialog().find('[data-test="confluence-target-parent"]').setValue('page-1')
    await targetDialog().find('[data-test="confluence-target-save"]').trigger('click')
    await flushPromises()

    expect(warn).toHaveBeenCalledWith(messages.confluenceParentInvalid)
    expect(rbacApi.updateConfluenceTargets).not.toHaveBeenCalled()
  })

  it('removes a project default once confirmed', async () => {
    vi.spyOn(ElMessageBox, 'confirm').mockResolvedValue('confirm' as any)
    const { wrapper } = await mountView(
      [],
      noTargets({
        projects: [
          { project_key: 'PROJ', space_key: 'PROJSPACE', parent_page_id: '', enabled: null },
        ],
      })
    )

    await wrapper.find('[data-test="confluence-project-remove"]').trigger('click')
    await flushPromises()

    expect(lastTargets()).toEqual({ projects: [], repositories: [] })
    expect(wrapper.findAll('[data-test="confluence-projects"] .el-table__row')).toHaveLength(0)
  })

  it('clears a repository override so that it falls back again', async () => {
    vi.spyOn(ElMessageBox, 'confirm').mockResolvedValue('confirm' as any)
    const { wrapper } = await mountView(
      [],
      noTargets({
        repositories: [
          {
            project_key: 'PROJ',
            repository_slug: 'my-repo',
            space_key: 'OWN',
            parent_page_id: '',
            enabled: null,
          },
        ],
        resolved: [resolvedRow({ space_key: 'OWN', space_source: 'repository', configured: true })],
      })
    )

    await wrapper.find('[data-test="confluence-repository-clear"]').trigger('click')
    await flushPromises()

    expect(lastTargets()).toEqual({ projects: [], repositories: [] })
  })

  it('leaves the configuration alone when a removal is dismissed', async () => {
    vi.spyOn(ElMessageBox, 'confirm').mockRejectedValue('dismissed')
    const { wrapper } = await mountView(
      [],
      noTargets({
        projects: [
          { project_key: 'PROJ', space_key: 'PROJSPACE', parent_page_id: '', enabled: null },
        ],
      })
    )

    await wrapper.find('[data-test="confluence-project-remove"]').trigger('click')
    await flushPromises()

    expect(rbacApi.updateConfluenceTargets).not.toHaveBeenCalled()
  })

  it('filters the repository list down to what is typed', async () => {
    const { wrapper } = await mountView(
      [],
      noTargets({
        resolved: [
          resolvedRow({ repository_slug: 'api', app_name: 'API' }),
          resolvedRow({ repository_slug: 'web', app_name: 'Web' }),
        ],
      })
    )

    await wrapper.find('.target-search input').setValue('web')
    await flushPromises()

    const rows = wrapper.findAll('[data-test="confluence-repositories"] .el-table__row')
    expect(rows).toHaveLength(1)
    expect(rows[0].text()).toContain('web')
  })
})
