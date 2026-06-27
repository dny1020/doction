// Tema claro/oscuro. El tema se aplica con el atributo data-theme en <html>
// (el CSS usa [data-theme="dark"]) y se recuerda en localStorage. El valor
// inicial lo fija un script en index.html antes de pintar, para evitar parpadeo.

export function getTheme() {
  return document.documentElement.getAttribute('data-theme') || 'light'
}

export function toggleTheme() {
  const next = getTheme() === 'dark' ? 'light' : 'dark'
  document.documentElement.setAttribute('data-theme', next)
  try {
    localStorage.setItem('theme', next)
  } catch (e) {
    // localStorage puede fallar (modo privado); el tema igual cambia en esta sesión.
  }
  return next
}
