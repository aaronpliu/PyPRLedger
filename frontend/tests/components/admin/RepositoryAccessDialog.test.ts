import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import RepositoryAccessDialog from '@/components/admin/RepositoryAccessDialog.vue'
import {
  repositoryAccessApi,
  type RepositoryAccessResponse,
} from '@/api/repositoryAccess'

const catalog = [
  { project_key: 'PROJB', repository_slug: 'repo-b2', app_name: null },
  { project_key: 'PROJA', repository_slug: 'repo-1', app_name: 'App One' },
  { project_key: 'PROJB', repository_slug: 'repo-b1', app_name: null },
  { project_key: 'PROJA', repository_slug: 'repo-3', app_name: null },
  { project_key: 'PROJA', repository_slug: 'repo-2', app_name: null },
]

const access: RepositoryAccessResponse = {
  subject_type: 'auth_user',
  subject_id: 7,
  subject_username: 'alice',
  items: [{ project_key: 'PROJA', repository_slug: 'repo-1' }],
  total: 1,
}

vi.mock('@/api/repositoryAccess', () => ({
  repositoryAccessApi: {
    getCatalog: vi.fn(async () => catalog),
    getAccess: vi.fn(async () => access),
    replaceAccess: vi.fn(),
  },
}))

/* eslint-disable @typescript-eslint/no-explicit-any */
type AnyWrapper = any
const mountedWrappers: AnyWrapper[] = []

async function mountDialog() {
  const wrapper = mount(RepositoryAccessDialog, {
    props: {
      modelValue: false,
      subjectType: 'auth_user' as const,
      subjectId: 7,
      username: 'alice',
    },
    global: { plugins: [ElementPlus], stubs: { teleport: true } },
  })
  mountedWrappers.push(wrapper)
  // the dialog renders its body lazily: opening it the way the pages do is
  // what draws the tree
  await wrapper.setProps({ modelValue: true })
  await flushPromises()
  return wrapper
}

const dialog = (wrapper: AnyWrapper) => wrapper.findComponent({ name: 'ElDialog' })

/** The tree's top rows, one per project, in the order the tree shows them. */
const projectNodes = (wrapper: AnyWrapper) =>
  dialog(wrapper).findAll('.el-tree > .el-tree-node > .el-tree-node__content')

const projectNode = (wrapper: AnyWrapper, name: string) =>
  projectNodes(wrapper).find((node: AnyWrapper) => node.text().includes(name))

/** The indented rows beneath one project. */
const repoNodesOf = (wrapper: AnyWrapper, name: string) =>
  dialog(wrapper)
    .findAll('.el-tree-node')
    .find(
      (node: AnyWrapper) => node.find('.node-project').exists() && node.find('.node-project').text() === name
    )
    ?.findAll('.el-tree-node__children .el-tree-node__content') ?? []

beforeEach(() => {
  vi.mocked(repositoryAccessApi.getCatalog).mockClear()
  vi.mocked(repositoryAccessApi.getAccess).mockClear()
  vi.mocked(repositoryAccessApi.replaceAccess).mockClear()
})

afterEach(() => {
  mountedWrappers.forEach((wrapper) => wrapper.unmount())
  mountedWrappers.length = 0
})

describe('RepositoryAccessDialog', () => {
  it('reads the catalog as a tree: projects above, their repositories beneath', async () => {
    const wrapper = await mountDialog()

    // projects are sorted, each visibly the parent of its own repositories
    const tops = projectNodes(wrapper)
    expect(tops).toHaveLength(2)
    expect(tops[0].find('.node-project').text()).toBe('PROJA')
    expect(tops[1].find('.node-project').text()).toBe('PROJB')

    const repos = repoNodesOf(wrapper, 'PROJA')
    expect(repos).toHaveLength(3)
    expect(repos[0].text()).toContain('repo-1')
    // the application name rides along when the record has one
    expect(repos[0].text()).toContain('App One')
    expect(repoNodesOf(wrapper, 'PROJB')).toHaveLength(2)
  })

  it('starts a half-picked project neither checked nor unchecked', async () => {
    const wrapper = await mountDialog()

    const proja = projectNode(wrapper, 'PROJA')
    expect(proja.find('.el-checkbox__input').classes()).toContain('is-indeterminate')
    expect(proja.find('.node-count').text()).toBe('1 / 3')
    // PROJB holds nothing of the reader's
    const projb = projectNode(wrapper, 'PROJB')
    expect(projb.find('.el-checkbox__input').classes()).not.toContain('is-indeterminate')
    expect(textOf(wrapper, '.access-count')).toContain('1 / 5')
  })

  it('takes every repository of a project when its row is checked', async () => {
    const wrapper = await mountDialog()

    await projectNode(wrapper, 'PROJA').find('input[type=checkbox]').setValue(true)
    await flushPromises()

    expect(projectNode(wrapper, 'PROJA').find('.el-checkbox__input').classes()).toContain(
      'is-checked',
    )
    expect(textOf(wrapper, '.access-count')).toContain('3 / 5 repositories')
  })

  it('narrows the tree to the rows the filter names', async () => {
    const wrapper = await mountDialog()

    await dialog(wrapper).find('.access-filter input').setValue('repo-b')
    await flushPromises()

    // PROJA and its rows are hidden; PROJB stays readable
    const hidden = dialog(wrapper)
      .findAll('.el-tree-node')
      .filter((node: AnyWrapper) => node.attributes('style')?.includes('display: none'))
    expect(hidden.length).toBeGreaterThan(0)
    expect(hidden.some((node: AnyWrapper) => node.text().includes('PROJA'))).toBe(true)
    expect(projectNode(wrapper, 'PROJB')?.element.style.display).not.toBe('none')
  })

  it('saves the pairs the reader picked', async () => {
    const wrapper = await mountDialog()

    await projectNode(wrapper, 'PROJA').find('input[type=checkbox]').setValue(true)
    await flushPromises()

    const save = dialog(wrapper)
      .findAll('button')
      .find((button: AnyWrapper) => button.text() === 'Save')
    await save?.trigger('click')
    await flushPromises()

    expect(repositoryAccessApi.replaceAccess).toHaveBeenCalledWith('auth_user', 7, [
      { project_key: 'PROJA', repository_slug: 'repo-1' },
      { project_key: 'PROJA', repository_slug: 'repo-2' },
      { project_key: 'PROJA', repository_slug: 'repo-3' },
    ])
    expect(wrapper.emitted('saved')).toHaveLength(1)
  })
})

function textOf(wrapper: AnyWrapper, selector: string): string {
  return dialog(wrapper).find(selector).text()
}
