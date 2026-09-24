// vitest setup (PROTECTED; vite.config.mjs test.setupFiles, 02 §4.1). jsdom lacks these; Vuetify's layout
// components call them.
globalThis.ResizeObserver = globalThis.ResizeObserver || class { observe() {} unobserve() {} disconnect() {} }
if (!globalThis.matchMedia) globalThis.matchMedia = () => ({ matches: false, addEventListener() {}, removeEventListener() {}, addListener() {}, removeListener() {} })
