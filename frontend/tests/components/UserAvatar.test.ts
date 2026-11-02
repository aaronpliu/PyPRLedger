import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import UserAvatar from '@/components/user/UserAvatar.vue'

function mountAvatar(props: Record<string, unknown> = {}) {
  return mount(UserAvatar, { props: { username: 'jdoe', size: 32, ...props } })
}

describe('UserAvatar', () => {
  it('draws the initial of a name that has no picture', () => {
    const avatar = mountAvatar({ username: 'jdoe' })

    expect(avatar.find('img.avatar-img').exists()).toBe(false)
    expect(avatar.find('.avatar-fallback').text()).toBe('J')
  })

  it('gives a name the same tone every time', () => {
    const tone = (username: string) => {
      const classes = mountAvatar({ username }).find('.avatar-fallback').classes()
      return classes.find((name) => name.startsWith('avatar-hue-'))
    }

    expect(tone('jdoe')).toBe(tone('jdoe'))
    // one of the twelve the stylesheet names, never a stray value
    expect(tone('jdoe')).toMatch(/^avatar-hue-(?:[0-9]|1[01])$/)
    expect(tone('')).toBe('avatar-hue-0')
  })

  it('leaves the colour to the stylesheet so it can follow the theme', () => {
    const fallback = mountAvatar({ username: 'jdoe' }).find('.avatar-fallback')

    // an inline colour would be the same in both themes; the tone is a class and
    // the light and dark values are named beside it
    expect(fallback.attributes('style') ?? '').not.toContain('background')
    expect(fallback.classes()).toContain('avatar-fallback')
  })

  it('falls back to the initial when the picture cannot be loaded', async () => {
    const avatar = mountAvatar({ avatarUrl: '/api/v1/users/avatars/7_jd.png' })

    expect(avatar.find('img.avatar-img').exists()).toBe(true)
    await avatar.find('img.avatar-img').trigger('error')

    expect(avatar.find('img.avatar-img').exists()).toBe(false)
    expect(avatar.find('.avatar-fallback').text()).toBe('J')
  })
})
