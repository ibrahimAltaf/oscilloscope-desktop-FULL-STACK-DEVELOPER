type Props = {
  running: boolean;
  busy: boolean;
  onStart: () => void;
  onStop: () => void;
  wsState: string;
  lastError: string | null;
  deviceState: string;
  reconnectFailures: number;
  onToggleTheme: () => void;
  theme: "dark" | "light";
  allowRun: boolean;
};

export function ControlBar({
  running,
  busy,
  onStart,
  onStop,
  wsState,
  lastError,
  deviceState,
  reconnectFailures,
  onToggleTheme,
  theme,
  allowRun,
}: Props) {
  const statusTone =
    deviceState === "CAPTURING" || deviceState === "CONNECTED"
      ? "good"
      : deviceState === "ERROR"
        ? "bad"
        : "warn";

  return (
    <header className="scope-topbar scope-topbar--instrument">
      <div className="scope-topbar__cluster">
        <button
          type="button"
          className="scope-btn scope-btn--run"
          onClick={onStart}
          disabled={busy || running || !allowRun}
        >
          RUN
        </button>
        <button
          type="button"
          className="scope-btn scope-btn--stop"
          onClick={onStop}
          disabled={busy || !running}
        >
          STOP
        </button>
      </div>

      <div className="scope-topbar__statuscard">
        <div className={`scope-topbar__status-pill scope-topbar__status-pill--${statusTone}`}>
          <span className="scope-topbar__dot" />
          <span className="scope-topbar__status-text">{deviceState}</span>
        </div>
        <div className="scope-topbar__meta">
          <span className="scope-topbar__tag">RECONNECT</span>
          <span className="scope-topbar__val">{reconnectFailures}</span>
        </div>
      </div>

      <div className="scope-topbar__status">
        <div className="scope-topbar__row scope-topbar__row--ws">
          <span className="scope-topbar__tag">WS</span>
          <span className="scope-topbar__val scope-topbar__val--ws" data-state={wsState}>
            {wsState.toUpperCase()}
          </span>
          <span className="scope-topbar__blip" data-state={wsState} aria-hidden />
        </div>
        <button type="button" className="scope-btn scope-btn--small" onClick={onToggleTheme}>
          {theme === "dark" ? "LIGHT" : "DARK"}
        </button>
        {lastError ? (
          <div className="scope-topbar__err mono" title={lastError}>
            {lastError}
          </div>
        ) : null}
      </div>
    </header>
  );
}
