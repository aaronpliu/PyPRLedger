/**
 * DOM screenshot helpers shared by the reporting views.
 *
 * The element is cloned off-screen before rendering so the capture is not
 * affected by scroll position, hover state or the surrounding layout.
 */

export interface ScreenshotOptions {
  /** Background applied to the clone (transparent cards otherwise render black). */
  background?: string
  /** Extra padding around the captured content, in pixels. */
  padding?: number
  pixelRatio?: number
}

export async function captureElementToPng(
  element: HTMLElement | null,
  options: ScreenshotOptions = {},
): Promise<string | null> {
  if (!element) return null

  const { background = '#ffffff', padding = 16, pixelRatio = 2 } = options
  const clone = element.cloneNode(true) as HTMLElement

  clone.style.width = `${element.offsetWidth || element.scrollWidth}px`
  clone.style.padding = `${padding}px`
  clone.style.background = background
  clone.style.borderRadius = '8px'
  clone.style.position = 'fixed'
  clone.style.left = '0'
  clone.style.top = '0'
  clone.style.zIndex = '-1000'
  clone.style.pointerEvents = 'none'

  document.body.appendChild(clone)
  try {
    // Two frames so the browser has painted the clone before it is rendered
    await nextFrame()
    await nextFrame()
    // Loaded on demand so the renderer is not part of the route bundle
    const { toPng } = await import('html-to-image')
    return await toPng(clone, { quality: 0.95, pixelRatio, cacheBust: true })
  } finally {
    clone.remove()
  }
}

function nextFrame(): Promise<void> {
  return new Promise((resolve) => requestAnimationFrame(() => resolve()))
}

export function downloadDataUrl(dataUrl: string, filename: string): void {
  const link = document.createElement('a')
  link.download = filename
  link.href = dataUrl
  link.style.display = 'none'
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
}

export async function dataUrlToFile(dataUrl: string, filename: string): Promise<File> {
  const blob = await (await fetch(dataUrl)).blob()
  return new File([blob], filename, { type: blob.type || 'image/png' })
}

export async function copyPngToClipboard(dataUrl: string): Promise<void> {
  const blob = await (await fetch(dataUrl)).blob()
  await navigator.clipboard.write([new ClipboardItem({ 'image/png': blob })])
}

export function canShareImage(): boolean {
  if (typeof navigator === 'undefined' || typeof navigator.share !== 'function') {
    return false
  }
  if (typeof navigator.canShare !== 'function' || typeof File === 'undefined') {
    return false
  }
  try {
    return navigator.canShare({ files: [new File([''], 'probe.png', { type: 'image/png' })] })
  } catch {
    return false
  }
}

/** Share the image through the OS share sheet. Returns false when unsupported. */
export async function sharePng(
  dataUrl: string,
  filename: string,
  title?: string,
): Promise<boolean> {
  if (!canShareImage()) return false
  const file = await dataUrlToFile(dataUrl, filename)
  if (!navigator.canShare?.({ files: [file] })) return false
  await navigator.share({ files: [file], title })
  return true
}

export function screenshotFilename(prefix: string): string {
  const now = new Date()
  const pad = (value: number) => String(value).padStart(2, '0')
  const stamp = `${now.getFullYear()}${pad(now.getMonth() + 1)}${pad(now.getDate())}-${pad(
    now.getHours(),
  )}${pad(now.getMinutes())}${pad(now.getSeconds())}`
  return `${prefix}-${stamp}.png`
}
