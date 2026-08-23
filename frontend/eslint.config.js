import globals from 'globals';

export default [
  // Rule set for ES modules (e.g., config files, modern source files)
  {
    files: ['eslint.config.js'],
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: 'module',
      globals: {
        ...globals.browser,
      },
    },
  },

  // Rule set strictly for script files
  {
    files: ['src/script.js'],
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: 'script',
      globals: {
        ...globals.browser,
        ...globals.commonjs,
        Atomics: 'readonly',
        SharedArrayBuffer: 'readonly',
      },
    },
    rules: {
      'space-before-function-paren': [
        'error',
        { anonymous: 'always', named: 'never', asyncArrow: 'always' },
      ],
    },
  },
];
