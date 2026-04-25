import { useEffect, useMemo, useState } from "react";
import { ControlPanel } from "./components/ControlPanel";
import { CursorTools } from "./components/CursorTools";
import { DeviceStatus } from "./components/DeviceStatus";
import { FFTChart } from "./components/FFTChart";
import { HardwareVerificationReport } from "./components/HardwareVerificationReport";
import { ReplayControls } from "./components/ReplayControls";
import { WaveformChart } from "./components/WaveformChart";
import { CLOUD_DOCS_URL, CLOUD_HEALTH_URL, CLOUD_RPC_URL } from "./config";
import type { SampleBatch, ServiceStatus, UiLog } from "./types";
import "./styles/app.css";

const MAX_REPLAY_BATCHES = 1200; // ~2 minutes at 100ms batch cadence.

const DEFAULT_STATUS: ServiceStatus = {
  dll_path: "",
  dll_found: false,
  dll_arch: "unknown",
  python_arch: "unknown",
  electron_arch: "unknown",
  dll_loaded: false,
  exports: null,
  device_connected: false,
  device_detected: false,
  capture_running: false,
  capture_started: false,
  real_data_received: false,
  zero_data_warning: false,
  samples_received: 0,
  last_min: null,
  last_max: null,
  last_variance: null,
  last_error: null,
  sdk_error_code: null,
  export_count: 0,
  mapped_functions: null,
  final_status: "REAL HARDWARE NOT VERIFIED",
  verification_reason: "DLL/device not validated yet",
};

export default function App() {
  const [status, setStatus] = useState<ServiceStatus>(DEFAULT_STATUS);
  const [latestBatch, setLatestBatch] = useState<SampleBatch | null>(null);
  const [replay, setReplay] = useState<SampleBatch[]>([]);
  const [replayEnabled, setReplayEnabled] = useState(false);
  const [replayIndex, setReplayIndex] = useState(0);
  const [paused, setPaused] = useState(false);
  const [logs, setLogs] = useState<UiLog[]>([]);
  const [sampleRateHz] = useState(1_000_000);
  const [electronArch, setElectronArch] = useState("unknown");
  const [cursorA, setCursorA] = useState(50);
  const [cursorB, setCursorB] = useState(200);
  const [exportMap, setExportMap] = useState({
    initialize: "HT_Init",
    open_device: "HT_OpenDevice",
    close_device: "HT_CloseDevice",
    start_capture: "HT_StartCapture",
    stop_capture: "HT_StopCapture",
    read_data: "HT_ReadData",
  });

  const pushLog = (level: UiLog["level"], message: string) => {
    setLogs((prev) => [{ ts: Date.now(), level, message }, ...prev].slice(0, 200));
  };

  useEffect(() => {
    const off = window.desktopAPI.onPythonEvent((evt) => {
      if (evt.event === "status") {
        setStatus((evt.payload as unknown as ServiceStatus) ?? DEFAULT_STATUS);
      } else if (evt.event === "sample_batch") {
        const batch = evt.payload as unknown as SampleBatch;
        setReplay((prev) => [...prev, batch].slice(-MAX_REPLAY_BATCHES));
        if (!paused) setLatestBatch(batch);
      } else if (evt.event === "log") {
        const level = (evt.payload.level as UiLog["level"]) || "info";
        pushLog(level, String(evt.payload.message || ""));
      }
    });
    void window.desktopAPI.rpc({ method: "get_status", params: {} });
    return off;
  }, [paused]);

  useEffect(() => {
    void window.desktopAPI.systemInfo().then((res) => {
      if (res.ok && res.result?.electronArch) setElectronArch(res.result.electronArch);
    });
  }, []);

  const visibleBatch = useMemo(() => {
    if (replayEnabled) return replay[Math.min(replayIndex, Math.max(0, replay.length - 1))] ?? null;
    return latestBatch;
  }, [latestBatch, replay, replayEnabled, replayIndex]);

  const minY = visibleBatch?.min ?? 0;
  const maxY = visibleBatch?.max ?? 0;

  async function call(method: string, params: Record<string, unknown>) {
    const res = await window.desktopAPI.rpc({ method, params });
    if (!res.ok) pushLog("error", res.error || `${method} failed`);
    else pushLog("info", `${method} success`);
    return res;
  }

  const openCloud = (url: string) => void window.desktopAPI.openExternal(url);

  return (
    <main className="app">
      <div className="app-header">
        <div>
          <h1>Hantek Real-Time Signal Analyzer</h1>
          <p className="subtitle">Real hardware data only — Hantek DLL + USB required.</p>
        </div>
        <div className="cloud-links">
          <span className="cloud-badge">☁ Cloud</span>
          <button className="btn-cloud" onClick={() => openCloud(CLOUD_DOCS_URL)}>API Docs</button>
          <button className="btn-cloud" onClick={() => openCloud(CLOUD_RPC_URL)}>RPC Reference</button>
          <button className="btn-cloud" onClick={() => openCloud(CLOUD_HEALTH_URL)}>Health Check</button>
        </div>
      </div>

      <ControlPanel
        dllPath={status.dll_path}
        paused={paused}
        exportMap={exportMap}
        onExportMapChange={setExportMap}
        onPickDll={async () => {
          const picked = await window.desktopAPI.pickDll();
          if (!picked.ok || !picked.result?.dllPath) return;
          await call("select_dll", { dll_path: picked.result.dllPath });
        }}
        onInspect={async () => {
          const res = await call("inspect_dll", {});
          if (res.ok && res.result && Array.isArray((res.result as { exports?: unknown[] }).exports)) {
            const count = ((res.result as { exports: unknown[] }).exports || []).length;
            pushLog("info", `Export inspection results: ${count} exports`);
          }
        }}
        onConnect={async () => {
          await call("connect_device", { device_index: 0, export_map: exportMap });
        }}
        onStart={async () => {
          await call("start_capture", { chunk_size: 2048 });
        }}
        onStop={async () => {
          await call("stop_capture", {});
        }}
        onDisconnect={async () => {
          await call("disconnect_device", {});
        }}
        onPauseToggle={() => setPaused((v) => !v)}
        onLiveMode={() => {
          setReplayEnabled(false);
          setPaused(false);
        }}
      />

      <DeviceStatus status={status} />
      <WaveformChart batch={visibleBatch} />
      <FFTChart batch={visibleBatch} sampleRateHz={sampleRateHz} />
      <CursorTools cursorA={cursorA} cursorB={cursorB} setCursorA={setCursorA} setCursorB={setCursorB} minY={minY} maxY={maxY} />
      <ReplayControls
        replayEnabled={replayEnabled}
        replayIndex={replayIndex}
        replayMax={Math.max(0, replay.length - 1)}
        onReplayToggle={() => setReplayEnabled((v) => !v)}
        onReplayIndex={setReplayIndex}
        onLiveMode={() => {
          setReplayEnabled(false);
          setPaused(false);
        }}
      />
      <HardwareVerificationReport status={status} electronArch={electronArch} />

      <section className="panel">
        <h3>Logs</h3>
        <div className="logs">
          {logs.map((entry) => (
            <div key={`${entry.ts}-${entry.message}`} className={`log-${entry.level}`}>
              [{new Date(entry.ts).toLocaleTimeString()}] {entry.level.toUpperCase()}: {entry.message}
            </div>
          ))}
        </div>
      </section>
    </main>
  );
}
