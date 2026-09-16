// Light and dark theme, applied as data-theme on <html> and remembered in localStorage.
// The initial value is set by a script in index.html before the first paint.

export function getTheme() {
  return document.documentElement.getAttribute('data-theme') || 'light'
}

export function toggleTheme() {
  const next = getTheme() === 'dark' ? 'light' : 'dark'
  document.documentElement.setAttribute('data-theme', next)
  try {
    localStorage.setItem('theme', next)
  } catch {
    // localStorage can fail in private mode; the theme still changes for this session.
  }
  return next
}
