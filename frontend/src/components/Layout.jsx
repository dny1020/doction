import React, { useCallback, useEffect, useState } from 'react'
import { Outlet } from 'react-router-dom'
import { api } from '../api.js'
import Sidebar from './Sidebar.jsx'

// Shell de la app autenticada: barra lateral + contenido. Carga el árbol de
// páginas una vez y lo comparte con las rutas hijas (vía el contexto del Outlet),
// junto con reloadPages() para refrescarlo tras crear/borrar.
export default function Layout() {
  const [pages, setPages] = useState([])

  const reloadPages = useCallback(() => {
    api
      .get('/api/pages')
      .then(setPages)
      .catch(() => setPages([]))
  }, [])

  useEffect(() => {
    reloadPages()
  }, [reloadPages])

  return (
    <div className="layout">
      <Sidebar pages={pages} />
      <main className="content" id="content">
        <div className="content-body">
          <Outlet context={{ pages, reloadPages }} />
        </div>
      </main>
    </div>
  )
}
