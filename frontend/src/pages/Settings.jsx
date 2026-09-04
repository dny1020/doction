import { useEffect, useRef, useState } from 'react'
import { NavLink, Outlet, useLocation, useOutletContext } from 'react-router-dom'
import { Check, ChevronDown } from 'lucide-react'
import { useI18n } from '../i18n.jsx'
import { useDocumentTitle } from '../useDocumentTitle.js'

// Ajustes por secciones: una ruta por sección, una sección en pantalla.
//
// El corte es 1120px, no los 820px del shell: entre 820 y 1120 la barra lateral
// sigue siendo una columna fija, y una segunda columna de navegación dejaría el
// contenido más estrecho que su propio cromo. 1120 ya es el ancho al que el lector
// suelta su tabla de contenidos, así que la interfaz pierde su columna secundaria
// a un solo ancho en vez de a dos.
//
// Ese ancho vive solo en el CSS. Se pintan las dos navegaciones y el media query
// esconde la que sobra: si el corte estuviera también aquí en JS, bastaría con que
// los dos números se separaran para que la lista apareciera sin su rejilla de dos
// columnas, apilada encima del contenido.

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
  // El shell reparte {pages, pagesError, reloadPages} por el contexto del Outlet, y
  // useOutletContext resuelve al proveedor más cercano: sin reenviarlo, las
  // secciones quedarían aisladas de él.
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

// Escritorio: la lista completa al lado del contenido. NavLink pone solo
// aria-current="page" en el activo, y el estado no depende solo del color.
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

// Móvil y tablet: disparador con la sección actual + menú, el mismo patrón que el
// selector de workspace de la barra lateral (no pestañas: empujan secciones fuera
// de pantalla y doction no tiene ese idioma).
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
