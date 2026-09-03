import { useEffect, useState } from 'react'
import { AlertTriangle, WifiOff } from 'lucide-react'
import { MCP_PATH } from '../config.js'
import { useI18n } from '../i18n.jsx'

// Estado de las dos superficies de máquina de doction: la API REST y el servidor
// MCP. Fallan por separado —el agente puede quedarse mudo con la API perfecta— así
// que se comprueban y se informan por separado.
//
// Callado cuando todo va: una insignia verde permanente es ruido. Esto se gana el
// sitio apareciendo solo cuando algo pasa.
const INTERVAL = 30000

async function probe() {
  // /health es anónimo y ya dice si la base de datos responde; `initialize` de MCP
  // es el único método abierto sin token, así que sondear no necesita credenciales.
  const [api, mcp] = await Promise.all([
    fetch('/health', { credentials: 'same-origin' })
      .then(async (r) => ((await r.json()).db === 'ok' ? 'ok' : 'degraded'))
      .catch(() => 'down'),
    fetch(MCP_PATH, {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ jsonrpc: '2.0', id: 1, method: 'initialize', params: {} }),
    })
      .then((r) => (r.ok ? 'ok' : 'down'))
      .catch(() => 'down'),
  ])
  return { api, mcp }
}

export default function ConnectionStatus() {
  const { t } = useI18n()
  const [state, setState] = useState({ api: 'ok', mcp: 'ok' })
  const [open, setOpen] = useState(false)

  useEffect(() => {
    let cancelled = false
    let timer = null
    // Volver a la pestaña relanza la comprobación, y puede haber una en vuelo de
    // antes. Sin esta marca las dos seguirían programando la siguiente y a partir
    // de ahí se sondearía el doble de veces, por cada ida y vuelta.
    let generation = 0

    async function check(mine) {
      const next = await probe()
      if (cancelled || mine !== generation) return
      setState(next)
      // El intervalo es fijo aunque algo falle: apretarlo cuando el servidor está
      // caído es pegarle más fuerte justo cuando peor está.
      timer = setTimeout(() => check(mine), INTERVAL)
    }

    function onVisibility() {
      clearTimeout(timer)
      generation += 1
      if (!document.hidden) check(generation)
    }

    check(generation)
    document.addEventListener('visibilitychange', onVisibility)
    return () => {
      cancelled = true
      clearTimeout(timer)
      document.removeEventListener('visibilitychange', onVisibility)
    }
  }, [])

  const healthy = state.api === 'ok' && state.mcp === 'ok'
  if (healthy) return null

  const down = state.api === 'down'
  const label = down
    ? t('conn_server_down')
    : state.api === 'degraded'
      ? t('conn_degraded')
      : t('conn_mcp_down')

  return (
    <div className="conn">
      <button
        className={'conn-badge' + (down ? ' conn-badge--down' : '')}
        type="button"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
      >
        {down ? <WifiOff size={13} /> : <AlertTriangle size={13} />}
        {label}
      </button>
      {open && (
        <div className="conn-detail">
          <div className="conn-row">
            <span>{t('conn_api')}</span>
            <span>{t('conn_' + state.api)}</span>
          </div>
          <div className="conn-row">
            <span>{t('conn_mcp')}</span>
            <span>{t('conn_' + state.mcp)}</span>
          </div>
        </div>
      )}
    </div>
  )
}
