import { useEffect, useRef, useState } from 'react'
import { NavLink, Outlet, useLocation, useOutletContext } from 'react-router-dom'
import { Check, ChevronDown } from 'lucide-react'
import { useI18n } from '../i18n.jsx'
import { useDocumentTitle } from '../useDocumentTitle.js'

// Settings by section: one route per section, one section on screen.
//
// The breakpoint is 1120px and not the shell's 820px: between the two the sidebar is still
// a fixed column, and a second navigation column would leave the content narrower than its
// own chrome. 1120 is where the reader drops its table of contents, so the interface loses
// its secondary column at one width rather than two.
//
// That width lives only in the CSS. Both navigations render and the media query hides the
// spare one: a second copy of the number here in JS could drift and leave the list without
// its two-column grid, stacked over the content.

export const SECTIONS = [
  { path: 'account', key: 'sec_account' },
  { path: 'preferences', key: 'sec_preferences' },
  { path: 'workspaces', key: 'sec_workspaces' },
  { path: 'tokens', key: 'sec_tokens' },
  { path: 'webhooks', key: 'sec_webhooks' },
  { path: 'system', key: 'sec_system' },
]

export default function Settings() {
  const { t } = useI18n()
  // The shell shares {pages, pagesError, reloadPages} through the Outlet context, and
  // useOutletContext resolves to the nearest provider: without forwarding it, the sections
  // would be cut off from it.
  const shellContext = useOutletContext()
  useDocumentTitle(t('settings'), null)

  return (
    <div className="settings">
      <h1 className="settings-h1">{t('settings')}</h1>
      <div className="settings-layout">
        <SectionList />
        <SectionSelect />
        <div className="settings-panel">
          <Outlet context={shellContext} />
        </div>
      </div>
    </div>
  )
}

// Desktop: the full list beside the content. NavLink sets aria-current="page" on the
// active one, so the state does not rest on colour alone.
function SectionList() {
  const { t } = useI18n()
  return (
    <nav className="settings-nav" aria-label={t('settings_sections')}>
      {SECTIONS.map((section) => (
        <NavLink
          key={section.path}
          to={section.path}
          className={({ isActive }) =>
            'settings-nav-item' + (isActive ? ' settings-nav-item--active' : '')
          }
        >
          {t(section.key)}
        </NavLink>
      ))}
    </nav>
  )
}

// Mobile and tablet: a trigger showing the current section plus a menu, the same pattern
// as the sidebar's workspace picker. Not tabs: they push sections off screen.
function SectionSelect() {
  const { t } = useI18n()
  const location = useLocation()
  const [open, setOpen] = useState(false)
  const ref = useRef(null)

  const current = SECTIONS.find((s) => location.pathname.endsWith('/' + s.path)) || SECTIONS[0]

  useEffect(() => setOpen(false), [location.pathname])

  useEffect(() => {
    function onDocClick(event) {
      if (ref.current && !ref.current.contains(event.target)) setOpen(false)
    }
    function onKey(event) {
      if (event.key === 'Escape') setOpen(false)
    }
    document.addEventListener('click', onDocClick)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('click', onDocClick)
      document.removeEventListener('keydown', onKey)
    }
  }, [])

  return (
    <div className="settings-select" ref={ref}>
      <button
        className="settings-select-trigger"
        type="button"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label={t('settings_sections')}
        onClick={() => setOpen((v) => !v)}
      >
        <span className="settings-select-label">{t(current.key)}</span>
        <ChevronDown size={16} className="settings-select-icon" />
      </button>
      <div className={'settings-select-menu' + (open ? ' open' : '')} role="menu">
        {SECTIONS.map((section) => (
          <NavLink
            key={section.path}
            to={section.path}
            role="menuitem"
            className={({ isActive }) => 'settings-select-option' + (isActive ? ' active' : '')}
          >
            <span className="settings-select-option-name">{t(section.key)}</span>
            <Check size={14} className="settings-select-option-check" />
          </NavLink>
        ))}
      </div>
    </div>
  )
}
