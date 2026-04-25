import { BrowserWindow, dialog, ipcMain, shell } from "electron";
import { PythonBridge } from "./pythonBridge";

export function registerIpcHandlers(mainWindow: BrowserWindow, bridge: PythonBridge): void {
  bridge.onEvent((evt) => mainWindow.webContents.send("python:event", evt));

  ipcMain.handle("python:pickDll", async () => {
    const result = await dialog.showOpenDialog(mainWindow, {
      properties: ["openFile"],
      filters: [{ name: "DLL", extensions: ["dll"] }],
    });
    if (result.canceled || result.filePaths.length === 0) return { ok: false, error: "DLL selection cancelled" };
    return { ok: true, result: { dllPath: result.filePaths[0] } };
  });

  ipcMain.handle("python:rpc", async (_event, payload: { method: string; params: Record<string, unknown> }) => {
    try {
      const res = await bridge.request(payload.method, payload.params ?? {});
      return res;
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      return { ok: false, error: message };
    }
  });

  ipcMain.handle("app:systemInfo", async () => {
    return {
      ok: true,
      result: {
        electronArch: process.arch === "x64" ? "x64" : "x86",
      },
    };
  });

  ipcMain.handle("app:openExternal", async (_event, url: string) => {
    await shell.openExternal(url);
  });
}
