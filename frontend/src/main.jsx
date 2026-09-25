import { createRoot } from 'react-dom/client'
import { RouterProvider, createBrowserRouter } from 'react-router-dom'
import { routes } from './App.jsx'
import { APP_BASE } from './config.js'
import { AuthProvider } from './auth.jsx'
import { I18nProvider } from './i18n.jsx'
import { ToastProvider } from './components/Toast.jsx'
import { ConfirmProvider } from './components/ConfirmDialog.jsx'
import ErrorBoundary from './components/ErrorBoundary.jsx'

// The basename comes from the bundle's `base` (config.js). The data router is needed by
// the editor's useBlocker. I18nProvider wraps everything, loading screen included.
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
