import { createRoot } from 'react-dom/client'
import { RouterProvider, createBrowserRouter } from 'react-router-dom'
import { routes } from './App.jsx'
import { APP_BASE } from './config.js'
import { AuthProvider } from './auth.jsx'
import { I18nProvider } from './i18n.jsx'
import { ToastProvider } from './components/Toast.jsx'
import { ConfirmProvider } from './components/ConfirmDialog.jsx'
import ErrorBoundary from './components/ErrorBoundary.jsx'

// El basename sale del `base` con el que se construyó el bundle (config.js), no
// de un literal: así montar doction en otra subruta o en la raíz es configurar y
// no editar código.
// Usamos el "data router" (createBrowserRouter) en vez de <BrowserRouter> porque
// useBlocker —el guard de cambios sin guardar del editor— solo funciona con él.
// I18nProvider va por fuera para que toda la app (incluida la pantalla de carga)
// tenga acceso a las traducciones; toasts y confirm son globales (login incluido).
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
