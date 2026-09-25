import MarkdownIt from 'markdown-it'
import taskLists from 'markdown-it-task-lists'
import DOMPurify from 'dompurify'
import { APP_BASE } from './config.js'
import { newPageWithTitlePath, pagePath } from './routes.js'

// Rendering happens only here, so this is a security boundary: embedded HTML is on and
// always passes through a whitelist sanitizer. One without the other is stored XSS.

// ── Whitelist ────────────────────────────────────────────────────────────────
// doction's own and not the library's on purpose: what gets rendered is a product
// decision, and inheriting it silently lets the next release of a dependency change it.
const ALLOWED_TAGS = [
  // Document structure.
  'p',
  'br',
  'hr',
  'h1',
  'h2',
  'h3',
  'h4',
  'h5',
  'h6',
  'ul',
  'ol',
  'li',
  'dl',
  'dt',
  'dd',
  'blockquote',
  'pre',
  'code',
  'table',
  'thead',
  'tbody',
  'tfoot',
  'tr',
  'th',
  'td',
  'a',
  'img',
  'figure',
  'figcaption',
  // Inline elements that carry meaning, which is what embedded HTML is opened for.
  'strong',
  'em',
  'del',
  's',
  'ins',
  'mark',
  'sub',
  'sup',
  'small',
  'abbr',
  'kbd',
  'samp',
  'var',
  'q',
  'cite',
  'time',
  'span',
  'div',
  'details',
  'summary',
  // Only for task-list checkboxes; see the hook below.
  'input',
]

const ALLOWED_ATTR = [
  'href',
  'src',
  'alt',
  'title',
  'class',
  'lang',
  'dir',
  'colspan',
  'rowspan',
  'align',
  'start',
  'reversed',
  'datetime',
  'type',
  'checked',
  'disabled',
]

// Allowed URL schemes: http(s), mailto, tel and anything schemeless. `javascript:` and
// `data:` are out — one executes, the other is a whole document inside an attribute.
const ALLOWED_URI = /^(?:(?:https?|mailto|tel):|[^a-z]|[a-z+.-]+(?:[^a-z+.:-]|$))/i

// `input` is whitelisted only for `- [x]`; any other one is removed.
DOMPurify.addHook('uponSanitizeElement', (node, data) => {
  if (data.tagName !== 'input') return
  const checkbox = node.getAttribute('type') === 'checkbox' && node.hasAttribute('disabled')
  if (!checkbox) node.remove()
})

const md = new MarkdownIt('commonmark', {
  html: true,
  linkify: true,
  typographer: true,
})
md.enable(['table', 'strikethrough'])
// Checkboxes render disabled: the reading view reads. A task's state changes by editing
// the markdown, which is where it lives.
md.use(taskLists, { enabled: false, label: false })

// ── Math ─────────────────────────────────────────────────────────────────────
// Marked here, painted by KaTeX (prose.js) only on pages with formulas. Emitted as text,
// so the sanitizer never sees markup.
function mathPlugin(instance) {
  instance.inline.ruler.before('escape', 'doction_math', (state, silent) => {
    const start = state.pos
    if (state.src[start] !== '$') return false
    const block = state.src[start + 1] === '$'
    const fence = block ? '$$' : '$'
    const from = start + fence.length
    const end = state.src.indexOf(fence, from)
    if (end === -1) return false
    const body = state.src.slice(from, end)
    // `$10 and $20` is not math: empty, or opening with a space, passes through as text.
    if (!body.trim() || (!block && /^\s|\s$/.test(body))) return false
    if (!silent) {
      const token = state.push('doction_math', 'span', 0)
      token.content = body
      token.markup = fence
    }
    state.pos = end + fence.length
    return true
  })

  instance.renderer.rules.doction_math = (tokens, idx) => {
    const token = tokens[idx]
    const block = token.markup === '$$'
    const tag = block ? 'div' : 'span'
    const cls = block ? 'math math--block' : 'math'
    return `<${tag} class="${cls}">${instance.utils.escapeHtml(token.content)}</${tag}>`
  }
}
md.use(mathPlugin)

// ── Wikilinks ────────────────────────────────────────────────────────────────
// `[[target]]` and `[[target|label]]` become anchors. Emitted as tokens, never an HTML
// string, so markdown-it escapes the target (splicing it into <a href> is stored XSS). The
// href is a route prefix plus one encoded segment, so `javascript:` stays a relative path.
function wikilinkPlugin(instance) {
  instance.inline.ruler.before('link', 'doction_wikilink', (state, silent) => {
    const start = state.pos
    if (state.src.charCodeAt(start) !== 0x5b || state.src.charCodeAt(start + 1) !== 0x5b) {
      return false
    }
    const end = state.src.indexOf(']]', start + 2)
    if (end === -1) return false

    const inner = state.src.slice(start + 2, end)
    // A wikilink crosses no lines and nests no brackets: without this, a stray `[`
    // would swallow the rest of the paragraph.
    if (inner.includes('\n') || inner.includes('[')) return false

    const bar = inner.indexOf('|')
    const target = (bar === -1 ? inner : inner.slice(0, bar)).trim()
    const label = (bar === -1 ? '' : inner.slice(bar + 1).trim()) || target
    if (!target) return false

    // With no workspace there is no route to build, so it passes through as text.
    const ws = state.env && state.env.ws
    if (!ws) return false

    if (!silent) {
      // `slugs` may be absent while the tree loads; claiming a page is missing when it
      // exists is worse than not marking it at all.
      const slugs = state.env.slugs
      const missing = slugs ? !slugs.has(target) : false
      // APP_BASE goes in front: routes.js returns the path <Link> expects, and the
      // router adds the basename to that. This is a real <a href> inside the document,
      // so without the prefix the browser asks the backend, which does not serve it.
      const href = missing
        ? newPageWithTitlePath(ws, target)
        : pagePath(ws, encodeURIComponent(target))
      const open = state.push('link_open', 'a', 1)
      open.attrs = [
        ['href', APP_BASE + href],
        ['class', missing ? 'wikilink wikilink--missing' : 'wikilink'],
      ]
      const text = state.push('text', '', 0)
      text.content = label
      state.push('link_close', 'a', -1)
    }
    state.pos = end + 2
    return true
  })
}
md.use(wikilinkPlugin)

// ── Table alignment ──────────────────────────────────────────────────────────
// The sanitizer strips inline `style` (a page must not paint over the UI), so markdown-it's
// alignment is translated to a class.
function tableAlignPlugin(instance) {
  for (const rule of ['th_open', 'td_open']) {
    instance.renderer.rules[rule] = (tokens, idx, options, env, self) => {
      const token = tokens[idx]
      const style = token.attrGet('style')
      if (style && style.startsWith('text-align:')) {
        token.attrSet('class', 'align-' + style.slice('text-align:'.length).trim())
        token.attrs = token.attrs.filter(([name]) => name !== 'style')
      }
      return self.renderToken(tokens, idx, options)
    }
  }
}
md.use(tableAlignPlugin)

// Frontmatter is metadata, and markdown-it would read `key: value` + `---` as a heading.
// Stripped here, not on the server, which returns the markdown as stored.
const FRONTMATTER = /^---[ \t]*\r?\n[\s\S]*?\r?\n---[ \t]*(?:\r?\n|$)/

function stripFrontmatter(text) {
  return text.replace(FRONTMATTER, '')
}

// `env` carries what a rule needs and the markdown does not have: the document's
// workspace and the slugs that exist in it.
export function renderMarkdown(text, env = {}) {
  return DOMPurify.sanitize(md.render(stripFrontmatter(text || ''), env), {
    ALLOWED_TAGS,
    ALLOWED_ATTR,
    ALLOWED_URI_REGEXP: ALLOWED_URI,
    // A <script> or <style> body goes with its tag: keeping it would turn the code into
    // a loose paragraph in the middle of the document.
    FORBID_CONTENTS: ['script', 'style', 'template'],
  })
}
