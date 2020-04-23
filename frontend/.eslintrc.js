module.exports = {
  env: {
    browser: true,
    es6: true,
    node: false
  },
  extends: [
    'standard'
  ],
  globals: {
    Atomics: 'readonly',
    SharedArrayBuffer: 'readonly'
  },
  parserOptions: {
    ecmaVersion: 6,
    sourceType: 'script'
  },
  rules: {
  }
}
