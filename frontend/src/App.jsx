import { Navigate } from 'react-router-dom'
import { useAuth } from './auth.jsx'
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

// Árbol de rutas para createBrowserRouter (main.jsx). Una URL desconocida cae en
// el 404 con estilo (antes se redirigía a la home en silencio).
export const routes = [
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
      { path: '/', element: <Reader /> },
      { path: '/new', element: <Editor mode="new" /> },
      { path: '/p/:slug', element: <Reader /> },
      { path: '/p/:slug/edit', element: <Editor mode="edit" /> },
      { path: '/p/:slug/history', element: <History /> },
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
      { path: '/trash', element: <Trash /> },
      { path: '/notes', element: <Notes /> },
    ],
  },
  { path: '*', element: <NotFound /> },
]
