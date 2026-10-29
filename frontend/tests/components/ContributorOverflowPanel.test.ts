import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createI18n } from 'vue-i18n'
import ContributorOverflowPanel from '@/components/release/ContributorOverflowPanel.vue'
import enMessages from '@/locales/en.json'
import type { ReleaseNoteContributor } from '@/api/releaseNotes'

const people: ReleaseNoteContributor[] = [
  {
    username: 'dev7',
    display_name: 'Developer Seven',
    avatar_url: '/api/v1/users/avatars/7.png',
    profile_url: 'https://github.local/dev7',
    commit_count: 4,
    last_committed: new Date(Date.now() - 2 * 86_400_000).toISOString(),
  },
  { username: 'dev8', display_name: 'Developer Eight', commit_count: 2 },
  { display_name: 'Unlinked Author', commit_count: 1 },
]

function mountPanel(contributors: ReleaseNoteContributor[] = people) {
  const i18n = createI18n({ legacy: false, locale: 'en', messages: { en: enMessages } })
  return mount(ContributorOverflowPanel, {
    props: { contributors },
    global: { plugins: [ElementPlus, i18n] },
  })
}

describe('ContributorOverflowPanel', () => {
  it('lists the people it only counts, one line each', () => {
    const panel = mountPanel()

    expect(panel.find('.contributor-overflow-title').text()).toBe('…and 3 more')

    const rows = panel.findAll('[data-test="contributor-overflow-row"]')
    expect(rows).toHaveLength(3)
    expect(rows.map((row) => row.find('.contributor-overflow-name').text())).toEqual([
      '@dev7',
      '@dev8',
      'Unlinked Author',
    ])
    expect(rows[0].find('.contributor-overflow-commits').text()).toBe('4 commit(s)')

    // a name alone is all the list says: no card is open until one is pointed at
    expect(panel.find('.contributor-overflow-detail').exists()).toBe(false)
  })

  it('describes the person the pointer rests on', async () => {
    const panel = mountPanel()

    await panel.findAll('[data-test="contributor-overflow-row"]')[0].trigger('mouseenter')

    const detail = panel.find('.contributor-overflow-detail')
    expect(detail.exists()).toBe(true)
    expect(detail.find('.contributor-card-name').text()).toBe('Developer Seven')
    expect(detail.find('.contributor-card-login').text()).toBe('@dev7')
    expect(detail.find('.contributor-card-commits').text()).toBe('4 commit(s)')
    expect(detail.find('[data-test="contributor-activity"]').text()).toBe(
      enMessages.releaseNotes.contributor_active_week,
    )
    expect(detail.find('a.contributor-card-link').attributes('href')).toBe(
      'https://github.local/dev7',
    )
  })

  it('moves the card with the pointer and drops it on the way out', async () => {
    const panel = mountPanel()
    const rows = panel.findAll('[data-test="contributor-overflow-row"]')

    await rows[1].trigger('mouseenter')
    expect(panel.find('.contributor-card-login').text()).toBe('@dev8')

    await rows[2].trigger('mouseenter')
    // an author the platform knows only by name is described by that name
    expect(panel.find('.contributor-card-name').text()).toBe('Unlinked Author')
    expect(panel.find('.contributor-card-login').exists()).toBe(false)

    await panel.trigger('mouseleave')
    expect(panel.find('.contributor-overflow-detail').exists()).toBe(false)
  })
})
