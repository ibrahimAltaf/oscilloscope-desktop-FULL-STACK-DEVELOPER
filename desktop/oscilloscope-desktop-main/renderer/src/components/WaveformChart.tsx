import { useMemo } from "react";
import type { SampleBatch } from "../types";

type Props = {
  batch: SampleBatch | null;
};

export function WaveformChart({ batch }: Props) {
  const points = useMemo(() => {
    if (!batch || batch.samples.length === 0) return "";
    const n = batch.samples.length;
    return batch.samples
      .map((v, i) => {
        const x = (i / Math.max(1, n - 1)) * 1000;
        const y = 200 - ((v + 32768) / 65535) * 380;
        return `${x},${y}`;
      })
      .join(" ");
  }, [batch]);

  return (
    <section className="panel">
      <h3>Waveform</h3>
      <svg width="100%" viewBox="0 0 1000 400" className="chart">
        <polyline points={points} />
      </svg>
      <div className="mono">
        {batch
          ? `count=${batch.count} min=${batch.min} max=${batch.max} variance=${batch.variance.toFixed(2)}`
          : "No real sample batch yet"}
      </div>
    </section>
  );
}
