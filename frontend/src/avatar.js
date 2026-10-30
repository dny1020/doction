// Avatar helpers, shared by the sidebar and settings.
//
// With no colour chosen, a stable one is derived from the email.

// The same palette as AVATAR_COLORS in app/avatar.py, where the reasoning lives.
export const AVATAR_COLORS = [
  '#B8523B',
  '#3B73B8',
  '#347F50',
  '#895AC2',
  '#926A2F',
  '#2D7B8C',
  '#C04669',
  '#5E7A37',
]

// A stable index into a list of `size` entries, the same for the same text everywhere.
export function stableIndex(text, size) {
  const source = text || ''
  let hash = 0
  for (let i = 0; i < source.length; i++) {
    hash = (hash * 31 + source.charCodeAt(i)) & 0xfffffff
  }
  return hash % size
}

export function autoColor(email) {
  return AVATAR_COLORS[stableIndex(email, AVATAR_COLORS.length)]
}

export function avatarColor(user) {
  if (!user) return AVATAR_COLORS[0]
  return user.avatar_color || autoColor(user.email)
}

export function avatarLetter(name, email) {
  const source = (name || email || '?').trim()
  return source ? source.charAt(0).toUpperCase() : '?'
}
