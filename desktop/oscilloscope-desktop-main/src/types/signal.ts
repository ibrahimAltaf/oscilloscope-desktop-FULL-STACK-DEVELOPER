/**
 * Matches oscilloscope_backend WebSocket JSON batches.
 */
export type SignalBatch = {
  t0: number;
  sample_rate_hz: number;
  samples: number[];
  mode?: string;
  batch_seq?: number;
  ptp?: number;
  rms?: number;
  volt_div?: number;
  time_div_s?: number;
  drops?: number;
   sample_count?: number;
};

/** Future: multiple hardware channels in one frame */
export type SignalBatchMulti = SignalBatch & {
  channels?: number[][];
};

export function isSignalBatch(x: unknown): x is SignalBatch {
  if (!x || typeof x !== "object") return false;
  const o = x as Record<string, unknown>;
  return (
    typeof o.t0 === "number" &&
    typeof o.sample_rate_hz === "number" &&
    Array.isArray(o.samples) &&
    o.samples.every((v) => typeof v === "number")
  );
}
