import { useCallback, useEffect, useState } from "react";
import { DashboardLayout } from "@/components/DashboardLayout";
import { ControlBar } from "@/components/ControlBar";
import { FutureRail } from "@/components/FutureRail";
import { OscilloscopeChart } from "@/components/OscilloscopeChart";
import type { WsState } from "@/hooks/useSignalWebSocket";
import "./App.css";

const DEFAULT_WS = "wss://oscilloscope-desktop-full-stack-dev.vercel.app/ws/signal";

export default function App() {
  const [deviceConnected, setDeviceConnected] = useState(false);
  const [connecting, setConnecting] = useState(false);
  const [connectError, setConnectError] = useState<string | null>(null);
  const [running, setRunning] = useState(false);
  const [busy, setBusy] = useState(false);
  const [wsUrl, setWsUrl] = useState<string | null>(null);
  const [apiBase, setApiBase] = useState<string | null>(null);
  const [wsState, setWsState] = useState<WsState>("idle");
  const [lastError, setLastError] = useState<string | null>(null);
  const [deviceState, setDeviceState] = useState<string>("disconnected");
  const [batchesSent, setBatchesSent] = useState<number>(0);
  const [drops, setDrops] = useState<number>(0);
  const [reconnectFailures, setReconnectFailures] = useState<number>(0);
  const [voltDiv, setVoltDiv] = useState<string>("—");
  const [timeDiv, setTimeDiv] = useState<string>("—");
  const [theme, setTheme] = useState<"dark" | "light">(() => {
    if (typeof localStorage === "undefined") return "dark";
    const saved = localStorage.getItem("scope-theme");
    return saved === "light" ? "light" : "dark";
  });
  const deviceReady = deviceState === "CONNECTED" || deviceState === "CAPTURING";
  const deviceError = deviceState === "ERROR";

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    try {
      localStorage.setItem("scope-theme", theme);
    } catch {
      /* ignore */
    }
  }, [theme]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const cfg = await window.electronAPI.getConfig();
        if (!cancelled) {
          setApiBase(cfg.apiBase);
          setWsUrl(cfg.wsUrl || DEFAULT_WS);
        }
      } catch {
        if (!cancelled) setWsUrl(DEFAULT_WS);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const onStart = useCallback(async () => {
    setBusy(true);
    setLastError(null);
    try {
      const res = await window.electronAPI.startCapture();
      if (!res.ok) {
        const msg =
          typeof res.data === "object" && res.data && "detail" in res.data
            ? String((res.data as { detail?: unknown }).detail)
            : res.error ?? `HTTP ${res.status}`;
        setLastError(msg || "Start failed");
        setRunning(false);
        return;
      }
      setRunning(true);
      setDeviceConnected(true);
    } catch (e) {
      setLastError(e instanceof Error ? e.message : String(e));
      setRunning(false);
    } finally {
      setBusy(false);
    }
  }, []);

  const onStop = useCallback(async () => {
    setBusy(true);
    setLastError(null);
    try {
      const res = await window.electronAPI.stopCapture();
      if (!res.ok) {
        setLastError(res.error ?? `Stop failed (HTTP ${res.status})`);
      }
      setRunning(false);
    } catch (e) {
      setLastError(e instanceof Error ? e.message : String(e));
      setRunning(false);
    } finally {
      setBusy(false);
    }
  }, []);

  useEffect(() => {
    if (!running) setWsState("idle");
  }, [running]);

  const onWsState = useCallback((s: WsState) => {
    setWsState(s);
  }, []);

  useEffect(() => {
    let cancelled = false;
    const tick = async () => {
      try {
        const res = await window.electronAPI.getStatus();
        if (cancelled) return;
        if (res && res.ok && typeof res.data === "object" && res.data) {
          const st = res.data as {
            device_state?: string;
            capture_state?: string;
            batches_sent?: number;
            drops?: number;
            reconnect_failures?: number;
            volt_div?: number;
            time_div_s?: number;
          };
          const ds = (st.capture_state || st.device_state || "disconnected").toUpperCase();
          setDeviceState(ds);
          if (typeof st.batches_sent === "number") setBatchesSent(st.batches_sent);
          if (typeof st.drops === "number") setDrops(st.drops);
          if (typeof st.reconnect_failures === "number") setReconnectFailures(st.reconnect_failures);
          if (typeof st.volt_div === "number") setVoltDiv(`${st.volt_div.toFixed(2)} V/div`);
          if (typeof st.time_div_s === "number") {
            setTimeDiv(
              st.time_div_s >= 1
                ? `${st.time_div_s.toFixed(3)} s/div`
                : `${(st.time_div_s * 1e3).toFixed(1)} ms/div`,
            );
          }
        } else if (res && !res.ok) {
          setDeviceState("ERROR");
          setLastError(res.error ?? `Status HTTP ${res.status}`);
        }
      } catch (e) {
        if (!cancelled) {
          setDeviceState("ERROR");
          setLastError(e instanceof Error ? e.message : String(e));
        }
      }
    };
    if (deviceConnected) {
      tick();
      const id = setInterval(tick, 1000);
      return () => {
        cancelled = true;
        clearInterval(id);
      };
    }
    return () => {
      cancelled = true;
    };
  }, [deviceConnected]);

  const handleConnect = useCallback(async () => {
    setConnecting(true);
    setConnectError(null);
    setLastError(null);
    try {
      const status = await window.electronAPI.getStatus();
      const state =
        status && status.ok && status.data && typeof status.data === "object"
          ? (status.data as { device_state?: string; capture_state?: string })
          : null;
      const ds = state?.capture_state || state?.device_state;
      if (ds && (ds.toUpperCase() === "CONNECTED" || ds.toUpperCase() === "CAPTURING")) {
        setDeviceConnected(true);
        setDeviceState(ds.toUpperCase());
        setRunning(ds.toUpperCase() === "CAPTURING");
        return;
      }
      // try start capture to bring device up
      const start = await window.electronAPI.startCapture();
      if (!start.ok) {
        throw new Error(start.error ?? `Start failed (HTTP ${start.status})`);
      }
      setDeviceConnected(true);
      setRunning(true);
      setDeviceState("CAPTURING");
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      setConnectError(msg);
      setDeviceConnected(false);
    } finally {
      setConnecting(false);
    }
  }, []);

  return (
    <DashboardLayout
      header={
        <ControlBar
          running={running}
          busy={busy}
          onStart={onStart}
          onStop={onStop}
          wsState={wsState}
          lastError={lastError}
          deviceState={deviceState}
          reconnectFailures={reconnectFailures}
          onToggleTheme={() => setTheme(theme === "dark" ? "light" : "dark")}
          theme={theme}
          allowRun={deviceReady && !deviceError}
        />
      }
      main={
        deviceConnected ? (
          <div className="scope-main-panel">
            <OscilloscopeChart
              wsUrl={wsUrl}
              apiBase={apiBase}
              streaming={running && deviceConnected}
              onWsState={onWsState}
              voltDiv={voltDiv}
              timeDiv={timeDiv}
            />
            {!deviceReady && !deviceError && (
              <div className="scope-warning mono">Device not connected. Connect hardware to enable RUN.</div>
            )}
            {deviceError && (
              <div className="scope-warning scope-warning--error mono">
                Device error. Check connections and restart capture.
              </div>
            )}
          </div>
        ) : (
          <div className="connect-screen">
            <div className="connect-card">
              <h1 className="connect-title">Oscilloscope Setup</h1>
              <p className="connect-sub">Connect your Hantek device to begin.</p>
              <button
                type="button"
                className="scope-btn scope-btn--run connect-btn"
                onClick={handleConnect}
                disabled={connecting}
              >
                {connecting ? "CONNECTING..." : "CONNECT DEVICE"}
              </button>
              <div className="connect-status mono">
                Status: {connecting ? "CONNECTING" : deviceState || "NOT CONNECTED"}
              </div>
              {connectError && <div className="scope-warning scope-warning--error mono">{connectError}</div>}
            </div>
          </div>
        )
      }
      rail={
        deviceConnected ? (
          <FutureRail
            deviceState={deviceState}
            reconnectFailures={reconnectFailures}
            batchesSent={batchesSent}
            drops={drops}
            voltDiv={voltDiv}
            timeDiv={timeDiv}
          />
        ) : null
      }
      footer={
        deviceConnected ? (
          <footer className="scope-footer mono">
            <span className="scope-footer__model">HANTEK · HT6000 CLASS · 1CH ACQ</span>
            <span className="scope-footer__hint">
              WS {wsUrl ?? DEFAULT_WS} · API https://oscilloscope-desktop-full-stack-dev.vercel.app · BATCHES{" "}
              {batchesSent} · DROPS {drops}
            </span>
            <button
              type="button"
              className="scope-btn scope-btn--small"
              onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
            >
              {theme === "dark" ? "LIGHT MODE" : "DARK MODE"}
            </button>
          </footer>
        ) : null
      }
    />
  );
}
