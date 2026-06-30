import React from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import App from './App.jsx'
import { AuthProvider } from './auth.jsx'
import { I18nProvider } from './i18n.jsx'

// La SPA se sirve bajo /app, así que React Router usa ese basename.
// I18nProvider va por fuera para que toda la app (incluida la pantalla de carga)
// tenga acceso a las traducciones.
createRoot(document.getElementById('root')).render(
  <BrowserRouter basename="/app">
    <I18nProvider>
      <AuthProvider>
        <App />
      </AuthProvider>
    </I18nProvider>
  </BrowserRouter>,
)
