import { useCallback, useEffect, useMemo, useRef } from "react";
import uPlot from "uplot";
import "uplot/dist/uPlot.min.css";
import { RollingXY } from "@/lib/rollingBuffers";
import { useSignalWebSocket, type WsState } from "@/hooks/useSignalWebSocket";
import { isSignalBatch, type SignalBatch } from "@/types/signal";

type Props = {
  wsUrl: string | null;
  apiBase: string | null;
  streaming: boolean;
  onWsState?: (s: WsState) => void;
  voltDiv?: string;
  timeDiv?: string;
};

function makeOpts(
  width: number,
  height: number,
  theme: {
    bg: string;
    gridMajor: string;
    gridMinor: string;
    axisLine: string;
    axisText: string;
    ch1: string;
  },
): uPlot.Options {
  return {
    width,
    height,
    ms: 1,
    scales: {
      x: { time: true },
      y: {
        auto: true,
        range: (_u, min, max) => {
          const span = max - min;
          const pad = Math.max(span * 0.06, 1e-9);
          return [min - pad, max + pad];
        },
      },
    },
    axes: [
      {
        stroke: theme.axisLine,
        ticks: { stroke: theme.axisText, width: 1 },
        border: { stroke: theme.axisLine, width: 1 },
        grid: { stroke: theme.gridMajor, width: 1 },
        font: "11px Share Tech Mono, ui-monospace, monospace",
        label: "TIME",
        labelSize: 11,
        labelFont: "10px Share Tech Mono, ui-monospace, monospace",
        gap: 5,
        space: 50,
      },
      {
        stroke: theme.axisLine,
        ticks: { stroke: theme.axisText, width: 1 },
        border: { stroke: theme.axisLine, width: 1 },
        grid: { stroke: theme.gridMinor, width: 1 },
        font: "11px Share Tech Mono, ui-monospace, monospace",
        label: "V",
        labelSize: 11,
        labelFont: "10px Share Tech Mono, ui-monospace, monospace",
        side: 3,
        gap: 5,
        space: 54,
      },
    ],
    series: [
      {},
      {
        label: "CH1",
        stroke: theme.ch1,
        width: 2,
        spanGaps: false,
      },
    ],
    cursor: {
      drag: { x: true, y: true },
      points: { show: false },
    },
    legend: { show: false },
    hooks: {
      drawClear: [
        (u) => {
          const { ctx } = u;
          const { left, top, width, height } = u.bbox;
          if (width < 8 || height < 8) return;
          ctx.save();
          ctx.strokeStyle = "rgba(0, 255, 80, 0.055)";
          ctx.lineWidth = 1;
          const nx = 10;
          const ny = 8;
          for (let i = 1; i < nx; i++) {
            const x = left + (width * i) / nx;
            ctx.beginPath();
            ctx.moveTo(x, top);
            ctx.lineTo(x, top + height);
            ctx.stroke();
          }
          for (let j = 1; j < ny; j++) {
            const y = top + (height * j) / ny;
            ctx.beginPath();
            ctx.moveTo(left, y);
            ctx.lineTo(left + width, y);
            ctx.stroke();
          }
          ctx.restore();
        },
      ],
      init: [
        (u) => {
          u.root.style.background = theme.bg;
        },
      ],
    },
  };
}

export function OscilloscopeChart({ wsUrl, apiBase, streaming, onWsState, voltDiv, timeDiv }: Props) {
  const faceRef = useRef<HTMLDivElement>(null);
  const plotRef = useRef<uPlot | null>(null);
  const bufferRef = useRef(new RollingXY());
  const rafDrawRef = useRef<number | null>(null);
  const lastModeRef = useRef("—");
  const lastRateRef = useRef("—");
  const lastSeqRef = useRef("—");
  const lastRmsRef = useRef("—");
  const lastPtpRef = useRef("—");
  const lastDropsRef = useRef("0");
  const lastVoltDivRef = useRef("—");
  const lastTimeDivRef = useRef("—");
  const lastSampleCountRef = useRef("0");

  const readoutPtsRef = useRef<HTMLSpanElement>(null);
  const readoutRateRef = useRef<HTMLSpanElement>(null);
  const readoutModeRef = useRef<HTMLSpanElement>(null);
  const readoutSeqRef = useRef<HTMLSpanElement>(null);
  const readoutRmsRef = useRef<HTMLSpanElement>(null);
  const readoutPtpRef = useRef<HTMLSpanElement>(null);
  const readoutDropsRef = useRef<HTMLSpanElement>(null);
  const readoutVoltDivRef = useRef<HTMLSpanElement>(null);
  const readoutTimeDivRef = useRef<HTMLSpanElement>(null);
  const readoutSampleCountRef = useRef<HTMLSpanElement>(null);
  const lastReadoutUpdateRef = useRef(0);
  useEffect(() => {
    if (voltDiv) lastVoltDivRef.current = voltDiv;
  }, [voltDiv]);
  useEffect(() => {
    if (timeDiv) lastTimeDivRef.current = timeDiv;
  }, [timeDiv]);

  const themeColors = useMemo(() => {
    const cs = getComputedStyle(document.documentElement);
    return {
      bg: cs.getPropertyValue("--scope-bg").trim() || "#0a0a0a",
      gridMajor: cs.getPropertyValue("--scope-line").trim() || "rgba(0,255,0,0.2)",
      gridMinor: cs.getPropertyValue("--scope-line").trim() || "rgba(0,255,0,0.2)",
      axisLine: cs.getPropertyValue("--scope-edge").trim() || "rgba(0,255,0,0.32)",
      axisText: cs.getPropertyValue("--scope-text").trim() || "rgba(210,255,210,0.72)",
      ch1: cs.getPropertyValue("--ch1").trim() || "#b8ff00",
    };
  }, []);

  const drawPlot = useCallback(() => {
    rafDrawRef.current = null;
    const u = plotRef.current;
    if (!u) return;
    const { xs, ys } = bufferRef.current.view();
    const n = xs.length;

    u.batch(() => {
      if (n === 0) {
        u.setData([[], []]);
      } else {
        u.setData([xs, ys]);
      }
    });

    const now = performance.now();
    if (now - lastReadoutUpdateRef.current >= 200) {
      lastReadoutUpdateRef.current = now;
      readoutPtsRef.current && (readoutPtsRef.current.textContent = n.toLocaleString());
      readoutRateRef.current && (readoutRateRef.current.textContent = lastRateRef.current);
      readoutModeRef.current && (readoutModeRef.current.textContent = lastModeRef.current);
      readoutSeqRef.current && (readoutSeqRef.current.textContent = lastSeqRef.current);
      readoutRmsRef.current && (readoutRmsRef.current.textContent = lastRmsRef.current);
      readoutPtpRef.current && (readoutPtpRef.current.textContent = lastPtpRef.current);
      readoutDropsRef.current && (readoutDropsRef.current.textContent = lastDropsRef.current);
      readoutVoltDivRef.current && (readoutVoltDivRef.current.textContent = lastVoltDivRef.current);
      readoutTimeDivRef.current && (readoutTimeDivRef.current.textContent = lastTimeDivRef.current);
      readoutSampleCountRef.current && (readoutSampleCountRef.current.textContent = lastSampleCountRef.current);
    }
  }, []);

  const scheduleDraw = useCallback(() => {
    if (rafDrawRef.current != null) return;
    rafDrawRef.current = requestAnimationFrame(drawPlot);
  }, [drawPlot]);

  const onBatches = useCallback(
    (batches: SignalBatch[]) => {
      if (batches.length === 0) return;
      bufferRef.current.appendBatches(batches);
      const b = batches[batches.length - 1]!;
      lastModeRef.current = b.mode ?? "—";
      lastRateRef.current =
        b.sample_rate_hz >= 1e6
          ? `${(b.sample_rate_hz / 1e6).toFixed(3)} MS/s`
          : `${(b.sample_rate_hz / 1e3).toFixed(1)} kS/s`;
      lastSeqRef.current = b.batch_seq != null ? String(b.batch_seq) : "—";
      lastRmsRef.current = b.rms != null ? `${b.rms.toFixed(3)} V` : "—";
      lastPtpRef.current = b.ptp != null ? `${b.ptp.toFixed(3)} V` : "—";
      lastDropsRef.current = b.drops != null ? String(b.drops) : "0";
      lastVoltDivRef.current = b.volt_div != null ? `${b.volt_div.toFixed(2)} V/div` : "—";
      lastTimeDivRef.current =
        b.time_div_s != null
          ? b.time_div_s >= 1 ? `${b.time_div_s.toFixed(3)} s/div` : `${(b.time_div_s * 1e3).toFixed(1)} ms/div`
          : "—";
      lastSampleCountRef.current = b.sample_count != null ? String(b.sample_count) : "0";
      scheduleDraw();
    },
    [scheduleDraw],
  );

  const useHttpPolling = Boolean(apiBase?.includes("vercel.app"));

  useSignalWebSocket({
    url: wsUrl,
    enabled: streaming && !!wsUrl && !useHttpPolling,
    onBatches,
    onConnectionChange: (s) => onWsState?.(s),
  });

  useEffect(() => {
    if (!streaming || !useHttpPolling) return;
    let cancelled = false;
    onWsState?.("open");
    const tick = async () => {
      try {
        const res = await window.electronAPI.getSignalBatch();
        if (cancelled) return;
        if (res.ok && isSignalBatch(res.data)) {
          onBatches([res.data]);
        } else {
          onWsState?.("error");
        }
      } catch {
        if (!cancelled) onWsState?.("error");
      }
    };
    tick();
    const id = setInterval(tick, 120);
    return () => {
      cancelled = true;
      clearInterval(id);
      onWsState?.("idle");
    };
  }, [streaming, useHttpPolling, onBatches, onWsState]);

  useEffect(() => {
    if (!streaming) {
      bufferRef.current.clear();
      scheduleDraw();
    }
  }, [streaming, scheduleDraw]);

  useEffect(() => {
    const el = faceRef.current;
    if (!el) return;

    const ro = new ResizeObserver((entries) => {
      const cr = entries[0]?.contentRect;
      if (!cr) return;
      const w = Math.max(320, Math.floor(cr.width));
      const h = Math.max(280, Math.floor(cr.height));
      plotRef.current?.setSize({ width: w, height: h });
    });
    ro.observe(el);

    const w = Math.max(320, el.clientWidth);
    const h = Math.max(280, el.clientHeight);
    const u = new uPlot(makeOpts(w, h, themeColors), [[], []], el);
    plotRef.current = u;

    return () => {
      ro.disconnect();
      if (rafDrawRef.current != null) cancelAnimationFrame(rafDrawRef.current);
      u.destroy();
      plotRef.current = null;
    };
  }, []);

  return (
    <div className="crt-stack">
      <div className="crt-bezel">
        <div className="crt-face">
          <div className="crt-grid-overlay" aria-hidden />
          <div className="crt-plot-host" ref={faceRef} />
        </div>
        <div className="crt-readout mono" aria-live="polite">
          <span className="crt-readout__label">POINTS</span>
          <span className="crt-readout__value" ref={readoutPtsRef}>
            0
          </span>
          <span className="crt-readout__sep" />
          <span className="crt-readout__label">SAMPLES</span>
          <span className="crt-readout__value" ref={readoutSampleCountRef}>
            0
          </span>
          <span className="crt-readout__sep" />
          <span className="crt-readout__label">RATE</span>
          <span className="crt-readout__value" ref={readoutRateRef}>
            —
          </span>
          <span className="crt-readout__sep" />
          <span className="crt-readout__label">SRC</span>
          <span className="crt-readout__value crt-readout__value--ch1" ref={readoutModeRef}>
            —
          </span>
          <span className="crt-readout__sep" />
          <span className="crt-readout__label">SEQ</span>
          <span className="crt-readout__value crt-readout__value--ch2" ref={readoutSeqRef}>
            —
          </span>
          <span className="crt-readout__sep" />
          <span className="crt-readout__label">RMS</span>
          <span className="crt-readout__value" ref={readoutRmsRef}>
            —
          </span>
          <span className="crt-readout__sep" />
          <span className="crt-readout__label">PTP</span>
          <span className="crt-readout__value" ref={readoutPtpRef}>
            —
          </span>
          <span className="crt-readout__sep" />
          <span className="crt-readout__label">V/DIV</span>
          <span className="crt-readout__value" ref={readoutVoltDivRef}>
            —
          </span>
          <span className="crt-readout__sep" />
          <span className="crt-readout__label">T/DIV</span>
          <span className="crt-readout__value" ref={readoutTimeDivRef}>
            —
          </span>
          <span className="crt-readout__sep" />
          <span className="crt-readout__label">DROPS</span>
          <span className="crt-readout__value" ref={readoutDropsRef}>
            0
          </span>
        </div>
      </div>
    </div>
  );
}
