/**
 * Markdown export helpers.
 *
 * The document itself is built by the backend (see the release note export
 * endpoint): a text document has one author, so the page, an API client and CI
 * produce the same file. What is left for the browser is handing the bytes to the
 * user - downloading them, or putting them on the clipboard.
 */

/** Trigger a browser download for a generated markdown document. */
export function downloadMarkdown(content: string, filename: string): void {
  const blob = new Blob([content], { type: 'text/markdown;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.style.display = 'none'
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
}

/**
 * Copy text to the clipboard.
 *
 * Resolves `true` when the platform accepted the write. A refusal - an insecure
 * context, a denied permission, a missing Clipboard API - resolves `false`
 * instead of throwing, so a caller can fall back (offer the download, show the
 * text) without a try/catch of its own. Reporting the outcome is the caller's
 * job: a click that silently did nothing is worse than a visible error.
 */
export async function copyTextToClipboard(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text)
    return true
  } catch {
    return false
  }
}
