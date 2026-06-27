import React from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import App from './App.jsx'
import { AuthProvider } from './auth.jsx'

// La SPA se sirve bajo /app, así que React Router usa ese basename.
createRoot(document.getElementById('root')).render(
  <BrowserRouter basename="/app">
    <AuthProvider>
      <App />
    </AuthProvider>
  </BrowserRouter>,
)
