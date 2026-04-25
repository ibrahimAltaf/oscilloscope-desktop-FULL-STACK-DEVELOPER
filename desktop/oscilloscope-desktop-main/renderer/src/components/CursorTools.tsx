type Props = {
  cursorA: number;
  cursorB: number;
  setCursorA: (v: number) => void;
  setCursorB: (v: number) => void;
  minY: number;
  maxY: number;
};

export function CursorTools({ cursorA, cursorB, setCursorA, setCursorB, minY, maxY }: Props) {
  const dt = Math.abs(cursorB - cursorA);
  const dv = Math.abs(maxY - minY);
  return (
    <section className="panel">
      <h3>Cursor Tools</h3>
      <div className="grid2">
        <label>Time Cursor A</label>
        <input type="number" value={cursorA} onChange={(e) => setCursorA(Number(e.target.value))} />
        <label>Time Cursor B</label>
        <input type="number" value={cursorB} onChange={(e) => setCursorB(Number(e.target.value))} />
      </div>
      <div className="mono">Delta Time: {dt.toFixed(2)} samples</div>
      <div className="mono">Delta Voltage (raw ADC span): {dv.toFixed(2)}</div>
    </section>
  );
}
