import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createApp, h } from 'vue'
import ElementPlus from 'element-plus'
import { createI18n } from 'vue-i18n'
import CommitTable from '@/components/release/CommitTable.vue'
import { rbacApi } from '@/api/rbac'
import { resetJiraSettings } from '@/composables/useJira'
import type { CommitInfo } from '@/api/releaseDiff'
import enMessages from '@/locales/en.json'

vi.mock('@/api/rbac', () => ({
  rbacApi: { getJiraSettings: vi.fn() },
}))

function commits(count: number): CommitInfo[] {
  return Array.from({ length: count }, (_, index) => ({
    id: String(index + 1).padStart(40, '0'),
    display_id: String(index + 1).padStart(7, '0'),
    author_name: `dev${index}`,
    author_timestamp: 1_690_000_000_000 + index,
    message: `feat: change ${index}`,
  }))
}

/* eslint-disable @typescript-eslint/no-explicit-any */
type AnyWrapper = any

function mountTable(list: CommitInfo[]) {
  const i18n = createI18n({ legacy: false, locale: 'en', messages: { en: enMessages } })
  return mount(CommitTable, {
    props: { commits: list },
    global: { plugins: [ElementPlus, i18n] },
  })
}

function tableData(wrapper: AnyWrapper): CommitInfo[] {
  return wrapper.findComponent({ name: 'ElTable' }).props('data')
}

/**
 * Render one cell of a column.
 * el-table keeps its rows out of the DOM in jsdom, so the scoped slot itself is
 * mounted instead.
 */
function renderCell(wrapper: AnyWrapper, label: string, row: CommitInfo): HTMLElement {
  const column = wrapper
    .findAllComponents({ name: 'ElTableColumn' })
    .find((candidate: AnyWrapper) => candidate.props('label') === label)
  const container = document.createElement('div')
  createApp({ render: () => h('div', column.vm.$slots.default({ row })) }).mount(container)
  return container
}

describe('CommitTable', () => {
  beforeEach(() => {
    vi.mocked(rbacApi.getJiraSettings).mockReset()
    vi.mocked(rbacApi.getJiraSettings).mockResolvedValue({ base_url: '', project_keys: [] })
    resetJiraSettings()
  })

  it('renders every commit without pagination for a short list', () => {
    const wrapper = mountTable(commits(5))

    expect(wrapper.findAllComponents({ name: 'ElPagination' })).toHaveLength(0)
    expect(tableData(wrapper)).toHaveLength(5)
  })

  it('pages long commit sets so the DOM stays small', async () => {
    const wrapper = mountTable(commits(45))
    const pagination = wrapper.findComponent({ name: 'ElPagination' })

    expect(pagination.exists()).toBe(true)
    expect(pagination.props('total')).toBe(45)
    expect(tableData(wrapper)).toHaveLength(20)

    await pagination.vm.$emit('update:currentPage', 3)
    await wrapper.vm.$nextTick()

    // last page holds the remaining five commits
    expect(tableData(wrapper)).toHaveLength(5)
    expect(tableData(wrapper)[0].display_id).toBe('0000041')
  })

  it('links the provider account of a commit author to its profile', () => {
    const wrapper = mountTable(commits(1))
    const cell = renderCell(wrapper, enMessages.releaseDiff.col_author, {
      id: '1'.repeat(40),
      display_id: '1111111',
      author_name: 'Aaron Liu',
      author_username: 'aaronpliu',
      author_url: 'https://git.local/users/aaronpliu',
      message: 'feat: add login page',
    })

    const link = cell.querySelector('a.commit-author')
    expect(link).not.toBeNull()
    expect(link!.textContent!.trim()).toBe('@aaronpliu')
    expect(link!.getAttribute('href')).toBe('https://git.local/users/aaronpliu')
    expect(link!.getAttribute('title')).toBe('Aaron Liu')
  })

  it('links the JIRA ticket key of a commit subject', async () => {
    vi.mocked(rbacApi.getJiraSettings).mockResolvedValue({
      base_url: 'https://jira.local',
      project_keys: [],
    })
    const wrapper = mountTable(commits(1))
    await flushPromises()

    const cell = renderCell(wrapper, enMessages.releaseDiff.col_message, {
      id: '1'.repeat(40),
      display_id: '1111111',
      message: 'feat: fix login PRL-123',
    })

    const link = cell.querySelector('a.commit-ticket')
    expect(link).not.toBeNull()
    expect(link!.textContent!.trim()).toBe('PRL-123')
    expect(link!.getAttribute('href')).toBe('https://jira.local/browse/PRL-123')
    expect(cell.textContent).toContain('fix login')
  })

  it('keeps the subject plain while JIRA is not configured', async () => {
    const wrapper = mountTable(commits(1))
    await flushPromises()

    const cell = renderCell(wrapper, enMessages.releaseDiff.col_message, {
      id: '1'.repeat(40),
      display_id: '1111111',
      message: 'feat: fix login PRL-123',
    })

    expect(cell.querySelector('a.commit-ticket')).toBeNull()
    expect(cell.textContent).toContain('fix login PRL-123')
  })

  it('falls back to the display name when the provider reports no account', () => {
    const wrapper = mountTable(commits(1))
    const cell = renderCell(wrapper, enMessages.releaseDiff.col_author, {
      id: '1'.repeat(40),
      display_id: '1111111',
      author_name: 'Aaron Liu',
      message: 'feat: add login page',
    })

    expect(cell.querySelector('a.commit-author')).toBeNull()
    expect(cell.textContent).toContain('Aaron Liu')
  })

  it('returns to the first page when the commit list is replaced', async () => {
    const wrapper = mountTable(commits(45))
    const pagination = wrapper.findComponent({ name: 'ElPagination' })

    await pagination.vm.$emit('update:currentPage', 3)
    await wrapper.vm.$nextTick()
    expect(tableData(wrapper)).toHaveLength(5)

    await wrapper.setProps({ commits: commits(50) })
    await wrapper.vm.$nextTick()

    expect(pagination.props('currentPage')).toBe(1)
    expect(tableData(wrapper)).toHaveLength(20)
  })
})
