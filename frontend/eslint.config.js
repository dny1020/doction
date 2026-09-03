import js from '@eslint/js'
import globals from 'globals'
import react from 'eslint-plugin-react'
import reactHooks from 'eslint-plugin-react-hooks'

// Config plana (eslint 9). El formato lo maneja prettier, así que aquí solo van
// reglas que detectan errores, no estilo.
export default [
  { ignores: ['node_modules/**'] },
  js.configs.recommended,
  {
    files: ['**/*.{js,jsx}'],
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: 'module',
      globals: {
        ...globals.browser,
        // Los cargan los scripts de static/vendor/, no un import.
        mermaid: 'readonly',
        hljs: 'readonly',
        // Lo sustituye vite (define) con la ruta configurada del servidor MCP.
        __DOCTION_MCP_PATH__: 'readonly',
      },
      parserOptions: { ecmaFeatures: { jsx: true } },
    },
    plugins: { react, 'react-hooks': reactHooks },
    settings: { react: { version: 'detect' } },
    rules: {
      ...react.configs.flat.recommended.rules,
      ...react.configs.flat['jsx-runtime'].rules, // el runtime automático: no hace falta importar React
      // Las dos reglas clásicas de hooks. El preset `recommended` de react-hooks 7
      // añade además las del React Compiler, que esta app (React 18) no usa: marcan
      // patrones deliberados y documentados, como escribir un ref en el render.
      'react-hooks/rules-of-hooks': 'error',
      'react-hooks/exhaustive-deps': 'warn',
      // Sin PropTypes a propósito: son una dependencia más y un validador en runtime
      // para un proyecto que ya decidió no tipar (JSX plano, sin TypeScript).
      'react/prop-types': 'off',
    },
  },
  {
    // vite.config.js y los scripts de build corren en node, no en el navegador.
    files: ['vite.config.js', 'scripts/**/*.js'],
    languageOptions: { globals: globals.node },
  },
]
