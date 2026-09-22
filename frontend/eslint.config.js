import js from '@eslint/js'
import globals from 'globals'
import react from 'eslint-plugin-react'
import reactHooks from 'eslint-plugin-react-hooks'

// Flat config (eslint 9). Prettier handles formatting, so only error-detecting rules
// live here.
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
        // Loaded by the static/vendor/ scripts, not by an import.
        mermaid: 'readonly',
        hljs: 'readonly',
        katex: 'readonly',
        // Substituted by vite with the configured MCP server path.
        __DOCTION_MCP_PATH__: 'readonly',
        // The same, with the SPA basename.
        __DOCTION_APP_BASE__: 'readonly',
      },
      parserOptions: { ecmaFeatures: { jsx: true } },
    },
    plugins: { react, 'react-hooks': reactHooks },
    settings: { react: { version: 'detect' } },
    rules: {
      ...react.configs.flat.recommended.rules,
      ...react.configs.flat['jsx-runtime'].rules, // automatic runtime: no React import needed
      // The two classic hooks rules. react-hooks 7's `recommended` preset also adds the
      // React Compiler ones, which this React 18 app does not use: they flag deliberate,
      // documented patterns such as writing a ref during render.
      'react-hooks/rules-of-hooks': 'error',
      'react-hooks/exhaustive-deps': 'warn',
      // No PropTypes on purpose: one more dependency and a runtime validator for a
      // project that already decided not to type.
      'react/prop-types': 'off',
      // Using a variable before declaring it is a ReferenceError as soon as it runs, not
      // a style note. Functions are exempt because they hoist.
      'no-use-before-define': ['error', { functions: false }],
    },
  },
  {
    // vite.config.js and the build scripts run in node, not in the browser.
    files: ['vite.config.js', 'scripts/**/*.js'],
    languageOptions: { globals: globals.node },
  },
]
