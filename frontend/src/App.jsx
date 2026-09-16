import { Suspense, lazy } from 'react'
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
import { ListSkeleton } from './components/Skeleton.jsx'
// Code-split: d3-force and the drawing are only needed on this route.
const Graph = lazy(() => import('./pages/Graph.jsx'))
import NotFound from './pages/NotFound.jsx'
import ErrorPage from './pages/ErrorPage.jsx'

// Wraps the routes that need a session, showing a placeholder while it is checked.
function RequireAuth({ children }) {
  const { user, loading } = useAuth()
  const { t } = useI18n()
  if (loading) return <div className="placeholder">{t('loading')}</div>
  if (!user) return <Navigate to="/login" replace />
  return children
}

// Login and registration: with a session already, go straight home.
function GuestOnly({ children }) {
  const { user } = useAuth()
  if (user) return <Navigate to="/" replace />
  return children
}

// The workspace for someone who did not name one: their last, from `active_workspace`.
function useHomeWorkspace() {
  const { user } = useAuth()
  const active = user && user.active_workspace
  if (active) return active.slug
  return user && user.workspaces.length > 0 ? user.workspaces[0].slug : null
}

// `/` has no content of its own and leads to the last visited workspace.
function HomeRedirect() {
  const slug = useHomeWorkspace()
  if (!slug) return <NotFound />
  return <Navigate to={wsPath(slug)} replace />
}

// Old-scheme URLs (/p/<slug>, /new, /trash, /notes) still resolve, against the last
// visited workspace, so an old bookmark opens its page rather than a 404.
function LegacyRedirect({ to }) {
  const slug = useHomeWorkspace()
  const params = useParams()
  const location = useLocation()
  if (!slug) return <NotFound />
  const rest = to.replace(':slug', params.slug || '')
  return <Navigate to={wsPath(slug, rest) + location.search} replace />
}

// The route tree for createBrowserRouter (main.jsx). Everything hangs off a contentless
// root so the errorElement can hang off it too: the data router catches render errors
// itself, and without this it shows its default screen with the stack visible — the error
// boundary in main.jsx never sees them.
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
          // Content hangs off the workspace, so a link opens the page it names.
          { path: '/w/:ws', element: <Reader /> },
          { path: '/w/:ws/new', element: <Editor mode="new" /> },
          { path: '/w/:ws/p/:slug', element: <Reader /> },
          { path: '/w/:ws/p/:slug/edit', element: <Editor mode="edit" /> },
          { path: '/w/:ws/p/:slug/history', element: <History /> },
          { path: '/w/:ws/trash', element: <Trash /> },
          { path: '/w/:ws/notes', element: <Notes /> },
          {
            path: '/w/:ws/graph',
            element: (
              <Suspense fallback={<ListSkeleton rows={6} />}>
                <Graph />
              </Suspense>
            ),
          },
          // Settings belong to the account and the deployment, not to a workspace; the
          // shell uses the last visited one to paint the tree.
          {
            path: '/settings',
            element: <Settings />,
            children: [
              // Bare `/settings` stays valid; it redirects rather than showing an index
              // of six links the navigation already lists.
              { index: true, element: <Navigate to="account" replace /> },
              { path: 'account', element: <AccountSection /> },
              { path: 'preferences', element: <PreferencesSection /> },
              { path: 'workspaces', element: <WorkspacesSection /> },
              { path: 'tokens', element: <TokensSection /> },
              { path: 'webhooks', element: <WebhooksSection /> },
              { path: 'system', element: <SystemSection /> },
              // An unknown section falls to the normal 404, not an empty settings frame.
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
