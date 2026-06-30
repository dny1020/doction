// Utilidades del avatar de usuario, compartidas por la barra lateral y los ajustes.
//
// Cuando el usuario no elige un color, derivamos uno estable a partir de su email
// (mismo hash que usa el frontend Jinja, para que el color no cambie entre vistas).

// Misma paleta que AVATAR_COLORS en app/main.py.
export const AVATAR_COLORS = [
  '#c0604a', '#4a7fc0', '#4aab6e', '#8b5fc0',
  '#c0914a', '#4aabc0', '#c05473', '#7a9c4a',
]

// Color automático y estable a partir del email.
export function autoColor(email) {
  const text = email || ''
  let hash = 0
  for (let i = 0; i < text.length; i++) {
    hash = (hash * 31 + text.charCodeAt(i)) & 0xfffffff
  }
  return AVATAR_COLORS[hash % AVATAR_COLORS.length]
}

// Color a mostrar: el elegido por el usuario, o el automático si no hay ninguno.
export function avatarColor(user) {
  if (!user) return AVATAR_COLORS[0]
  return user.avatar_color || autoColor(user.email)
}

// Primera letra para el avatar: del nombre si lo hay, si no del email.
export function avatarLetter(name, email) {
  const source = (name || email || '?').trim()
  return source ? source.charAt(0).toUpperCase() : '?'
}
