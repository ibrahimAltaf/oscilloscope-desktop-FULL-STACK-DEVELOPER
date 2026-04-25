import { app, BrowserWindow, shell } from "electron";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { PythonBridge } from "./pythonBridge";
import { registerIpcHandlers } from "./ipcHandlers";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const VITE_DEV_SERVER_URL = process.env.VITE_DEV_SERVER_URL;
const RENDERER_DIST = path.join(__dirname, "..", "..", "dist");
const PRELOAD_PATH = path.join(__dirname, "..", "preload", "preload.js");

let mainWindow: BrowserWindow | null = null;
const bridge = new PythonBridge();

function createWindow(): BrowserWindow {
  const win = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 1100,
    minHeight: 700,
    backgroundColor: "#121212",
    webPreferences: {
      preload: PRELOAD_PATH,
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  });

  if (VITE_DEV_SERVER_URL) {
    void win.loadURL(VITE_DEV_SERVER_URL);
    win.webContents.openDevTools({ mode: "detach" });
  } else {
    void win.loadFile(path.join(RENDERER_DIST, "index.html"));
  }

  win.webContents.setWindowOpenHandler(({ url }) => {
    void shell.openExternal(url);
    return { action: "deny" };
  });

  return win;
}

app.whenReady().then(() => {
  bridge.start();
  mainWindow = createWindow();
  registerIpcHandlers(mainWindow, bridge);
  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      mainWindow = createWindow();
      registerIpcHandlers(mainWindow, bridge);
    }
  });
});

app.on("before-quit", async () => {
  await bridge.stop();
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") app.quit();
});
