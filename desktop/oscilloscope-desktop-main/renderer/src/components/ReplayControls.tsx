type Props = {
  replayEnabled: boolean;
  replayIndex: number;
  replayMax: number;
  onReplayToggle: () => void;
  onReplayIndex: (v: number) => void;
  onLiveMode: () => void;
};

export function ReplayControls(props: Props) {
  return (
    <section className="panel">
      <h3>Replay</h3>
      <div className="row">
        <button onClick={props.onReplayToggle}>{props.replayEnabled ? "Disable Replay" : "Enable Replay"}</button>
        <button onClick={props.onLiveMode}>Resume Live</button>
      </div>
      <input
        type="range"
        min={0}
        max={Math.max(0, props.replayMax)}
        value={Math.min(props.replayIndex, Math.max(0, props.replayMax))}
        onChange={(e) => props.onReplayIndex(Number(e.target.value))}
        disabled={!props.replayEnabled}
      />
      <div className="mono">Replay index: {props.replayIndex}</div>
    </section>
  );
}
