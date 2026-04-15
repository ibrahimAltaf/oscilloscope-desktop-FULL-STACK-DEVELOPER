import { fileURLToPath } from "node:url";
import path from "node:path";
import { app, BrowserWindow, ipcMain, shell } from "electron";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

process.env.APP_ROOT = path.join(__dirname, "..");

const VITE_DEV_SERVER_URL = process.env.VITE_DEV_SERVER_URL;
const RENDERER_DIST = path.join(process.env.APP_ROOT, "dist");

const isDev = !!VITE_DEV_SERVER_URL;

const defaultApiBase = () =>
  process.env.OSCILLOSCOPE_API_BASE?.replace(/\/$/, "") ??
  "http://127.0.0.1:8765";

async function fetchJson(
  method: "GET" | "POST",
  pathname: string,
): Promise<{ ok: boolean; data: unknown; status: number; error?: string }> {
  const base = defaultApiBase();
  const url = `${base}${pathname.startsWith("/") ? pathname : `/${pathname}`}`;
  try {
    const res = await fetch(url, { method });
    const text = await res.text();
    let data: unknown = text;
    try {
      data = text ? JSON.parse(text) : null;
    } catch {
      /* keep text */
    }
    return { ok: res.ok, data, status: res.status };
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e);
    return { ok: false, data: null, status: 0, error: msg };
  }
}

function createWindow() {
  const win = new BrowserWindow({
    width: 1280,
    height: 800,
    minWidth: 960,
    minHeight: 600,
    backgroundColor: "#0a0a0a",
    show: false,
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  });

  win.once("ready-to-show", () => win.show());

  if (isDev) {
    win.loadURL(VITE_DEV_SERVER_URL!);
    win.webContents.openDevTools({ mode: "detach" });
  } else {
    win.loadFile(path.join(RENDERER_DIST, "index.html"));
  }

  win.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: "deny" };
  });
}

app.whenReady().then(() => {
  ipcMain.handle("capture:start", () => fetchJson("POST", "/start"));
  ipcMain.handle("capture:stop", () => fetchJson("POST", "/stop"));
  ipcMain.handle("capture:status", () => fetchJson("GET", "/status"));
  ipcMain.handle("config:get", () => ({
    apiBase: defaultApiBase(),
    wsUrl:
      process.env.OSCILLOSCOPE_WS_URL ??
      defaultApiBase().replace(/^http/, "ws") + "/ws/signal",
  }));

  createWindow();

  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") app.quit();
});
