type Props = {
  deviceState: string;
  reconnectFailures: number;
  batchesSent: number;
  drops: number;
  voltDiv: string;
  timeDiv: string;
};

export function FutureRail({ deviceState, reconnectFailures, batchesSent, drops, voltDiv, timeDiv }: Props) {
  return (
    <aside className="scope-rail" aria-label="Scope controls">
      <div className="scope-rail__stripe" aria-hidden />
      <div className="scope-rail__inner">
        <header className="scope-rail__hdr mono">DEVICE</header>

        <section className="scope-slot">
          <h3 className="scope-slot__title mono">STATUS</h3>
          <p className="scope-slot__note">State: {deviceState}</p>
          <p className="scope-slot__note">Reconnects: {reconnectFailures}</p>
          <p className="scope-slot__note">Volt/Div: {voltDiv}</p>
          <p className="scope-slot__note">Time/Div: {timeDiv}</p>
        </section>

        <section className="scope-slot">
          <h3 className="scope-slot__title mono">THROUGHPUT</h3>
          <p className="scope-slot__note">Batches: {batchesSent.toLocaleString()}</p>
          <p className="scope-slot__note">Drops: {drops.toLocaleString()}</p>
        </section>

        <section className="scope-slot">
          <h3 className="scope-slot__title mono">FFT</h3>
          <p className="scope-slot__note">Reserved for spectrum view</p>
          <div className="scope-slot__void scope-slot__void--short" />
        </section>

        <section className="scope-slot">
          <h3 className="scope-slot__title mono">CURSORS</h3>
          <p className="scope-slot__note">T1 · T2 · Δt · ΔV</p>
          <div className="scope-slot__void" />
        </section>

        <section className="scope-slot">
          <h3 className="scope-slot__title mono">REPLAY</h3>
          <p className="scope-slot__note">Ring buffer scrub (coming)</p>
          <div className="scope-slot__void" />
        </section>
      </div>
    </aside>
  );
}
