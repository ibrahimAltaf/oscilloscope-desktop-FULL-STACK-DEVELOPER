import { useMemo } from "react";
import type { SampleBatch } from "../types";

type Props = {
  batch: SampleBatch | null;
  sampleRateHz: number;
};

export function FFTChart({ batch, sampleRateHz }: Props) {
  const { path, peakHz } = useMemo(() => {
    if (!batch || batch.samples.length < 4) return { path: "", peakHz: 0 };
    const data = batch.samples.map((v) => v - batch.samples.reduce((a, b) => a + b, 0) / batch.samples.length);
    const n = data.length;
    const half = Math.floor(n / 2);
    const mags: number[] = [];
    for (let k = 0; k < half; k += 1) {
      let re = 0;
      let im = 0;
      for (let t = 0; t < n; t += 1) {
        const angle = (2 * Math.PI * t * k) / n;
        re += data[t] * Math.cos(angle);
        im -= data[t] * Math.sin(angle);
      }
      mags.push(Math.sqrt(re * re + im * im));
    }
    let peakIdx = 0;
    for (let i = 1; i < mags.length; i += 1) if (mags[i] > mags[peakIdx]) peakIdx = i;
    const maxMag = Math.max(1, ...mags);
    const poly = mags
      .map((m, i) => {
        const x = (i / Math.max(1, mags.length - 1)) * 1000;
        const y = 200 - (m / maxMag) * 190;
        return `${x},${y}`;
      })
      .join(" ");
    return { path: poly, peakHz: (peakIdx * sampleRateHz) / n };
  }, [batch, sampleRateHz]);

  return (
    <section className="panel">
      <h3>FFT</h3>
      <svg width="100%" viewBox="0 0 1000 220" className="chart">
        <polyline points={path} />
      </svg>
      <div className="mono">Peak Frequency: {peakHz.toFixed(2)} Hz</div>
    </section>
  );
}
