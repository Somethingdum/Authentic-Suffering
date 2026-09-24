// Play UI socket. socketUrl is done; P8 builds createSocket (10_UI.md, socket.spec.js).
export function socketUrl(envUrl) { return envUrl || 'ws://localhost:5050/ws' }
export function createSocket() { throw new Error('P8: createSocket is not built yet') }
