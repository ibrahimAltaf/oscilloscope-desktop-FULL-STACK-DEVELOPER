const MAX_POINTS_DEFAULT = 120_000;

/**
 * Fixed-capacity time-series buffer for uPlot [x, y].
 * Drops oldest points when over capacity.
 */
export class RollingXY {
  readonly maxPoints: number;
  private _len = 0;
  private _xs: Float64Array;
  private _ys: Float64Array;

  constructor(maxPoints = MAX_POINTS_DEFAULT) {
    this.maxPoints = maxPoints;
    this._xs = new Float64Array(maxPoints);
    this._ys = new Float64Array(maxPoints);
  }

  get length(): number {
    return this._len;
  }

  clear(): void {
    this._len = 0;
  }

  appendBatches(batches: readonly { t0: number; sample_rate_hz: number; samples: ArrayLike<number> }[]): void {
    for (const b of batches) {
      this.appendBatch(b.t0, b.sample_rate_hz, b.samples);
    }
  }

  appendBatch(t0: number, sampleRateHz: number, samples: ArrayLike<number>): void {
    if (sampleRateHz <= 0) return;
    const n = samples.length;
    if (n === 0) return;

    const invFs = 1 / sampleRateHz;
    let newTotal = this._len + n;
    if (newTotal > this.maxPoints) {
      const drop = newTotal - this.maxPoints;
      if (drop >= this._len) {
        this._len = 0;
      } else {
        this._xs.copyWithin(0, drop, this._len);
        this._ys.copyWithin(0, drop, this._len);
        this._len -= drop;
      }
      newTotal = this._len + n;
    }

    const base = this._len;
    for (let i = 0; i < n; i++) {
      this._xs[base + i] = t0 + i * invFs;
      this._ys[base + i] = samples[i]!;
    }
    this._len = newTotal;
  }

  view(): { xs: Float64Array; ys: Float64Array } {
    return {
      xs: this._xs.subarray(0, this._len),
      ys: this._ys.subarray(0, this._len),
    };
  }
}
