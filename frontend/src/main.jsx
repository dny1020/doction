import { createRoot } from 'react-dom/client'
import { RouterProvider, createBrowserRouter } from 'react-router-dom'
import { routes } from './App.jsx'
import { APP_BASE } from './config.js'
import { AuthProvider } from './auth.jsx'
import { I18nProvider } from './i18n.jsx'
import { ToastProvider } from './components/Toast.jsx'
import { ConfirmProvider } from './components/ConfirmDialog.jsx'
import ErrorBoundary from './components/ErrorBoundary.jsx'

// The basename comes from the `base` the bundle was built with (config.js) rather than a
// literal, so mounting doction elsewhere is configuration and not a code edit.
//
// The data router (createBrowserRouter) rather than <BrowserRouter>, because the editor's
// useBlocker guard only works with it. I18nProvider sits outside so the whole app, loading
// screen included, has translations; toasts and confirm are global.
const router = createBrowserRouter(routes, { basename: APP_BASE })

createRoot(document.getElementById('root')).render(
  <ErrorBoundary>
    <I18nProvider>
      <ToastProvider>
        <ConfirmProvider>
          <AuthProvider>
            <RouterProvider router={router} />
          </AuthProvider>
        </ConfirmProvider>
      </ToastProvider>
    </I18nProvider>
  </ErrorBoundary>,
)
