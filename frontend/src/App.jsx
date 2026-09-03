import { Navigate, Outlet, useLocation, useParams } from 'react-router-dom'
import { useAuth } from './auth.jsx'
import { wsPath } from './routes.js'
import { useI18n } from './i18n.jsx'
import Layout from './components/Layout.jsx'
import Login from './pages/Login.jsx'
import Register from './pages/Register.jsx'
import Reader from './pages/Reader.jsx'
import Editor from './pages/Editor.jsx'
import History from './pages/History.jsx'
import Settings from './pages/Settings.jsx'
import AccountSection from './pages/settings/Account.jsx'
import PreferencesSection from './pages/settings/Preferences.jsx'
import WorkspacesSection from './pages/settings/Workspaces.jsx'
import TokensSection from './pages/settings/Tokens.jsx'
import WebhooksSection from './pages/settings/Webhooks.jsx'
import SystemSection from './pages/settings/System.jsx'
import Trash from './pages/Trash.jsx'
import Notes from './pages/Notes.jsx'
import NotFound from './pages/NotFound.jsx'
import ErrorPage from './pages/ErrorPage.jsx'

// Envuelve las rutas que requieren sesión. Mientras se comprueba la sesión inicial
// muestra un placeholder; si no hay usuario, redirige al login.
function RequireAuth({ children }) {
  const { user, loading } = useAuth()
  const { t } = useI18n()
  if (loading) return <div className="placeholder">{t('loading')}</div>
  if (!user) return <Navigate to="/login" replace />
  return children
}

// Login/registro: si ya hay sesión, directo a la home.
function GuestOnly({ children }) {
  const { user } = useAuth()
  if (user) return <Navigate to="/" replace />
  return children
}

// El workspace de quien llega sin decir cuál: el último que usó, que el servidor
// recuerda en `active_workspace`.
function useHomeWorkspace() {
  const { user } = useAuth()
  const active = user && user.active_workspace
  if (active) return active.slug
  return user && user.workspaces.length > 0 ? user.workspaces[0].slug : null
}

// `/` no tiene contenido propio: lleva al workspace de la última visita.
function HomeRedirect() {
  const slug = useHomeWorkspace()
  if (!slug) return <NotFound />
  return <Navigate to={wsPath(slug)} replace />
}

// Las URLs del esquema anterior (/p/<slug>, /new, /trash, /notes) siguen siendo
// válidas: se resuelven contra el workspace de la última visita. Un marcador
// viejo abre la página, no un 404.
function LegacyRedirect({ to }) {
  const slug = useHomeWorkspace()
  const params = useParams()
  const location = useLocation()
  if (!slug) return <NotFound />
  const rest = to.replace(':slug', params.slug || '')
  return <Navigate to={wsPath(slug, rest) + location.search} replace />
}

// Árbol de rutas para createBrowserRouter (main.jsx). Una URL desconocida cae en
// el 404 con estilo (antes se redirigía a la home en silencio).
//
// Todo cuelga de una raíz sin contenido propio para poder colgarle el errorElement:
// el router de datos atrapa por su cuenta lo que revienta al pintar una ruta y, sin
// esto, enseñaba su pantalla de error por defecto con el stack a la vista — la
// barrera de errores de main.jsx no llega a verlo.
export const routes = [
  {
    element: <Outlet />,
    errorElement: <ErrorPage />,
    children: [
      {
        path: '/login',
        element: (
          <GuestOnly>
            <Login />
          </GuestOnly>
        ),
      },
      {
        path: '/register',
        element: (
          <GuestOnly>
            <Register />
          </GuestOnly>
        ),
      },
      {
        element: (
          <RequireAuth>
            <Layout />
          </RequireAuth>
        ),
        children: [
          // Contenido: todo cuelga del workspace, así que un enlace lleva a la página
          // que nombra y no a la que tuviera activa quien lo abre.
          { path: '/w/:ws', element: <Reader /> },
          { path: '/w/:ws/new', element: <Editor mode="new" /> },
          { path: '/w/:ws/p/:slug', element: <Reader /> },
          { path: '/w/:ws/p/:slug/edit', element: <Editor mode="edit" /> },
          { path: '/w/:ws/p/:slug/history', element: <History /> },
          { path: '/w/:ws/trash', element: <Trash /> },
          { path: '/w/:ws/notes', element: <Notes /> },
          // Ajustes no son de un workspace: son de la cuenta y del despliegue. El
          // shell usa el de la última visita para pintar el árbol.
          {
            path: '/settings',
            element: <Settings />,
            children: [
              // `/settings` a secas sigue siendo una URL válida: la enlaza la barra
              // lateral y puede estar en marcadores. Redirige en vez de mostrar un
              // índice de seis enlaces que la navegación ya lista.
              { index: true, element: <Navigate to="account" replace /> },
              { path: 'account', element: <AccountSection /> },
              { path: 'preferences', element: <PreferencesSection /> },
              { path: 'workspaces', element: <WorkspacesSection /> },
              { path: 'tokens', element: <TokensSection /> },
              { path: 'webhooks', element: <WebhooksSection /> },
              { path: 'system', element: <SystemSection /> },
              // Una sección inexistente cae en el 404 normal, no en un marco de
              // ajustes vacío sin nada seleccionado.
              { path: '*', element: <NotFound /> },
            ],
          },
          { path: '/', element: <HomeRedirect /> },
          { path: '/p/:slug', element: <LegacyRedirect to="/p/:slug" /> },
          { path: '/p/:slug/edit', element: <LegacyRedirect to="/p/:slug/edit" /> },
          { path: '/p/:slug/history', element: <LegacyRedirect to="/p/:slug/history" /> },
          { path: '/new', element: <LegacyRedirect to="/new" /> },
          { path: '/trash', element: <LegacyRedirect to="/trash" /> },
          { path: '/notes', element: <LegacyRedirect to="/notes" /> },
        ],
      },
      { path: '*', element: <NotFound standalone /> },
    ],
  },
]
