import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createI18n } from 'vue-i18n'
import CommitTable from '@/components/release/CommitTable.vue'
import type { CommitInfo } from '@/api/releaseDiff'
import enMessages from '@/locales/en.json'

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

describe('CommitTable', () => {
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
