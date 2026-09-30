import { describe, expect, it } from 'vitest'
import fs from 'node:fs'
import path from 'node:path'
import enMessages from '@/locales/en.json'
import zhCnMessages from '@/locales/zh-CN.json'
import zhTwMessages from '@/locales/zh-TW.json'

// the directory vitest was started in, which is where the config and src live
const SOURCE_DIR = path.resolve(process.cwd(), 'src')
const LOCALES = { 'zh-CN': zhCnMessages, 'zh-TW': zhTwMessages }

/** Every leaf key of a locale file, as `section.subsection.key`. */
function keyPaths(value: unknown, prefix = ''): string[] {
  if (typeof value !== 'object' || value === null) return [prefix]
  const paths: string[] = []
  for (const [key, child] of Object.entries(value as Record<string, unknown>)) {
    paths.push(...keyPaths(child, prefix ? `${prefix}.${key}` : key))
  }
  return paths
}

function sourceFiles(dir: string): string[] {
  return fs.readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const full = path.join(dir, entry.name)
    if (entry.isDirectory()) return sourceFiles(full)
    return entry.name.endsWith('.ts') || entry.name.endsWith('.vue') ? [full] : []
  })
}

/** The keys the source asks for, with the file that asks for each. */
function usedKeys(): Map<string, Set<string>> {
  const used = new Map<string, Set<string>>()
  for (const file of sourceFiles(SOURCE_DIR)) {
    const source = fs.readFileSync(file, 'utf-8')
    // `t('some.key')` only: a key built at runtime cannot be checked here
    const pattern = /\bt\(\s*['"]([A-Za-z0-9_.]+)['"]/g
    let match: RegExpExecArray | null
    while ((match = pattern.exec(source)) !== null) {
      const where = used.get(match[1]) ?? new Set<string>()
      where.add(path.relative(SOURCE_DIR, file))
      used.set(match[1], where)
    }
  }
  return used
}

describe('i18n', () => {
  it('defines every key the source asks for', () => {
    const defined = new Set(keyPaths(enMessages))
    const missing = [...usedKeys()]
      .filter(([key]) => !defined.has(key))
      .map(([key, files]) => `${key} (${[...files].join(', ')})`)

    // a key that is not defined renders as the key itself - in the page, and in
    // an exported report that no one can correct afterwards
    expect(missing).toEqual([])
  })

  it.each(Object.keys(LOCALES))('keeps %s in step with en', (locale) => {
    expect(keyPaths(LOCALES[locale as keyof typeof LOCALES]).sort()).toEqual(
      keyPaths(enMessages).sort(),
    )
  })
})
