/**
 * Preload script — CommonJS only (no `import` / ESM).
 * Exposes a minimal, IPC-based API to the isolated renderer.
 */
const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("electronAPI", {
  startCapture: () => ipcRenderer.invoke("capture:start"),
  stopCapture: () => ipcRenderer.invoke("capture:stop"),
  getStatus: () => ipcRenderer.invoke("capture:status"),
  getSignalBatch: () => ipcRenderer.invoke("signal:batch"),
  getConfig: () => ipcRenderer.invoke("config:get"),
});
