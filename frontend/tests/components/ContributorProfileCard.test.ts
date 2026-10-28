import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createI18n } from 'vue-i18n'
import ContributorProfileCard from '@/components/release/ContributorProfileCard.vue'
import enMessages from '@/locales/en.json'

function mountCard(props: Record<string, unknown> = {}) {
  const i18n = createI18n({ legacy: false, locale: 'en', messages: { en: enMessages } })
  return mount(ContributorProfileCard, {
    props,
    global: { plugins: [ElementPlus, i18n] },
  })
}

describe('ContributorProfileCard', () => {
  it('names the person, their login and the way to their profile', () => {
    const card = mountCard({
      username: 'jdoe',
      displayName: 'John Doe',
      avatarUrl: '/api/v1/users/avatars/77_jd.png',
      profileUrl: 'https://github.local/jdoe',
      commitCount: 3,
    })

    expect(card.find('.contributor-card-name').text()).toBe('John Doe')
    expect(card.find('.contributor-card-login').text()).toBe('@jdoe')
    expect(card.find('.contributor-card-commits').text()).toBe('3 commit(s)')
    // the picture of the account the login is bound to
    expect(card.find('img.avatar-img').attributes('src')).toBe('/api/v1/users/avatars/77_jd.png')

    const link = card.find('a.contributor-card-link')
    expect(link.attributes('href')).toBe('https://github.local/jdoe')
    expect(link.attributes('target')).toBe('_blank')
    expect(link.attributes('rel')).toContain('noopener')
    expect(link.text()).toBe(enMessages.releaseNotes.contributor_profile)
  })

  it('shows what the commits said for an author with no account', () => {
    const card = mountCard({
      displayName: 'Unlinked Author',
      commitCount: 1,
    })

    // the name is all there is: no login to show, nothing to link to
    expect(card.find('.contributor-card-name').text()).toBe('Unlinked Author')
    expect(card.find('.contributor-card-login').exists()).toBe(false)
    expect(card.find('a.contributor-card-link').exists()).toBe(false)
    // and the picture is the initial of that name
    expect(card.find('img.avatar-img').exists()).toBe(false)
    expect(card.find('.avatar-fallback').text()).toBe('U')
  })

  it('stands on the login when the commits carry no name', () => {
    const card = mountCard({ username: 'jroe', commitCount: 2 })

    expect(card.find('.contributor-card-name').text()).toBe('@jroe')
    // the name would only repeat the login under it
    expect(card.find('.contributor-card-login').exists()).toBe(false)
  })
})
