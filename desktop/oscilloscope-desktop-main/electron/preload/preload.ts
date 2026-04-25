import { contextBridge, ipcRenderer } from "electron";

type RpcPayload = { method: string; params?: Record<string, unknown> };
type PythonEvent = { event: string; payload: Record<string, unknown> };

contextBridge.exposeInMainWorld("desktopAPI", {
  pickDll: () => ipcRenderer.invoke("python:pickDll"),
  rpc: (payload: RpcPayload) => ipcRenderer.invoke("python:rpc", payload),
  systemInfo: () => ipcRenderer.invoke("app:systemInfo"),
  openExternal: (url: string) => ipcRenderer.invoke("app:openExternal", url),
  onPythonEvent: (cb: (evt: PythonEvent) => void) => {
    const handler = (_: unknown, data: PythonEvent) => cb(data);
    ipcRenderer.on("python:event", handler);
    return () => ipcRenderer.removeListener("python:event", handler);
  },
});
