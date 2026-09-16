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

// A stable automatic colour from the email.
export function autoColor(email) {
  const text = email || ''
  let hash = 0
  for (let i = 0; i < text.length; i++) {
    hash = (hash * 31 + text.charCodeAt(i)) & 0xfffffff
  }
  return AVATAR_COLORS[hash % AVATAR_COLORS.length]
}

// The colour to show: the user's choice, or the automatic one.
export function avatarColor(user) {
  if (!user) return AVATAR_COLORS[0]
  return user.avatar_color || autoColor(user.email)
}

// The avatar's initial: from the display name if there is one, otherwise the email.
export function avatarLetter(name, email) {
  const source = (name || email || '?').trim()
  return source ? source.charAt(0).toUpperCase() : '?'
}
