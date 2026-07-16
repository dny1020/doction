import { createContext, useCallback, useContext, useRef, useState } from 'react'

// Toasts globales (avisos breves abajo a la derecha). Reusa las clases `.toasts`
// y `.toast--ok/--error` del design system. Uso: const toast = useToast();
// toast('Guardado') o toast('Algo falló', 'error'). Se descartan solos.

const ToastContext = createContext(() => {})

const SHOW_MS = 4000 // visible
const FADE_MS = 300 // transición de salida antes de quitarlo del DOM

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([])
  const nextId = useRef(1)

  const toast = useCallback((text, tone = 'ok') => {
    const id = nextId.current++
    setToasts((list) => [...list, { id, text, tone, show: false }])
    // El `.show` entra un instante después para que la transición CSS se dispare.
    setTimeout(() => {
      setToasts((list) => list.map((item) => (item.id === id ? { ...item, show: true } : item)))
    }, 20)
    setTimeout(() => {
      setToasts((list) => list.map((item) => (item.id === id ? { ...item, show: false } : item)))
    }, SHOW_MS)
    setTimeout(() => {
      setToasts((list) => list.filter((item) => item.id !== id))
    }, SHOW_MS + FADE_MS)
  }, [])

  return (
    <ToastContext.Provider value={toast}>
      {children}
      <div className="toasts" role="status" aria-live="polite">
        {toasts.map((item) => (
          <div key={item.id} className={'toast toast--' + item.tone + (item.show ? ' show' : '')}>
            {item.text}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  )
}

export function useToast() {
  return useContext(ToastContext)
}
