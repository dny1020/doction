import { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react'
import { useI18n } from '../i18n.jsx'

// Diálogo de confirmación propio (reemplaza a window.confirm). Usa <dialog> nativo
// (showModal ya atrapa el foco y lo devuelve al cerrar) con las clases
// `.confirm-dialog` del design system. Uso:
//   const confirm = useConfirm()
//   if (await confirm(t('confirm_purge'), { confirmLabel: t('delete'), danger: true })) …

const ConfirmContext = createContext(() => Promise.resolve(false))

export function ConfirmProvider({ children }) {
  const { t } = useI18n()
  const dialogRef = useRef(null)
  const [request, setRequest] = useState(null) // { message, confirmLabel, danger, resolve }

  const confirm = useCallback(
    (message, { confirmLabel, danger = false } = {}) =>
      new Promise((resolve) => {
        setRequest({ message, confirmLabel, danger, resolve })
      }),
    [],
  )

  useEffect(() => {
    if (request && dialogRef.current && !dialogRef.current.open) {
      dialogRef.current.showModal()
    }
  }, [request])

  function close(result) {
    if (request) request.resolve(result)
    setRequest(null)
    if (dialogRef.current && dialogRef.current.open) dialogRef.current.close()
  }

  return (
    <ConfirmContext.Provider value={confirm}>
      {children}
      <dialog
        ref={dialogRef}
        className="confirm-dialog"
        onCancel={() => close(false)} /* Esc */
      >
        {request && (
          <>
            <p className="confirm-dialog-msg">{request.message}</p>
            <div className="confirm-dialog-actions">
              <button className="btn" type="button" onClick={() => close(false)}>
                {t('cancel')}
              </button>
              <button
                className={'btn ' + (request.danger ? 'btn-danger' : 'btn-primary')}
                type="button"
                autoFocus
                onClick={() => close(true)}
              >
                {request.confirmLabel || t('save')}
              </button>
            </div>
          </>
        )}
      </dialog>
    </ConfirmContext.Provider>
  )
}

export function useConfirm() {
  return useContext(ConfirmContext)
}
