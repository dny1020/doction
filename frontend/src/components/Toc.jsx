import { useEffect, useState } from 'react'
import { useI18n } from '../i18n.jsx'

// The "On this page" index, built from the h1/h2/h3 of the painted prose.
//
// Rather than toggling each heading separately, which could leave two active at once in
// short sections, it tracks the set of headings visible in the top band and activates only
// the last of them in document order.
export default function Toc({ proseRef, wrapRef, content }) {
  const { t } = useI18n()
  const [items, setItems] = useState([])
  const [activeId, setActiveId] = useState(null)

  useEffect(() => {
    const prose = proseRef.current
    const wrap = wrapRef.current
    if (!prose || !wrap) return undefined

    const heads = Array.from(prose.querySelectorAll('h1, h2, h3'))
    if (heads.length < 2) {
      setItems([])
      setActiveId(null)
      wrap.classList.remove('has-toc')
      return undefined
    }

    const used = {}
    const built = heads.map((h) => {
      const base =
        h.textContent
          .trim()
          .toLowerCase()
          .replace(/[^a-z0-9]+/g, '-')
          .replace(/^-+|-+$/g, '') || 'heading'
      let id = base
      if (id in used) {
        used[id]++
        id = base + '-' + used[id]
      } else {
        used[id] = 0
      }
      h.id = id
      return { id, text: h.textContent, level: h.tagName.toLowerCase() }
    })
    setItems(built)
    setActiveId(built[0].id)
    wrap.classList.add('has-toc')

    if (!('IntersectionObserver' in window)) return undefined

    const order = built.map((item) => item.id)
    const visible = new Set()
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) visible.add(entry.target.id)
          else visible.delete(entry.target.id)
        })
        const current = order.filter((id) => visible.has(id))
        if (current.length > 0) setActiveId(current[current.length - 1])
      },
      { rootMargin: '0px 0px -66% 0px', threshold: 0 },
    )
    heads.forEach((h) => observer.observe(h))

    return () => {
      observer.disconnect()
      wrap.classList.remove('has-toc')
    }
  }, [content, proseRef, wrapRef])

  if (items.length === 0) return null

  return (
    <aside className="toc" aria-label="Table of contents">
      <div className="eyebrow">{t('on_this_page')}</div>
      <nav id="toc-nav">
        {items.map((item) => (
          <a
            key={item.id}
            href={'#' + item.id}
            className={'toc-item toc-' + item.level + (item.id === activeId ? ' active' : '')}
          >
            {item.text}
          </a>
        ))}
      </nav>
    </aside>
  )
}
