type ExportMap = {
  initialize: string;
  open_device: string;
  close_device: string;
  start_capture: string;
  stop_capture: string;
  read_data: string;
};

type Props = {
  dllPath: string;
  onPickDll: () => void;
  onInspect: () => void;
  onConnect: () => void;
  onStart: () => void;
  onStop: () => void;
  onDisconnect: () => void;
  onPauseToggle: () => void;
  onLiveMode: () => void;
  paused: boolean;
  exportMap: ExportMap;
  onExportMapChange: (next: ExportMap) => void;
};

export function ControlPanel(props: Props) {
  const { exportMap } = props;
  return (
    <section className="panel">
      <h3>Hardware Controls</h3>
      <div className="row">
        <button onClick={props.onPickDll}>Select DLL</button>
        <button onClick={props.onInspect}>Inspect DLL</button>
        <button onClick={props.onConnect}>Connect Device</button>
        <button onClick={props.onStart}>▶ Start Capture</button>
        <button onClick={props.onStop}>■ Stop Capture</button>
        <button onClick={props.onDisconnect}>Disconnect</button>
        <button onClick={props.onPauseToggle}>{props.paused ? "▷ Resume" : "⏸ Pause"}</button>
        <button onClick={props.onLiveMode}>Live Mode</button>
      </div>
      <div className="mono">Selected DLL: {props.dllPath || "Not selected"}</div>
      <div className="grid2">
        <label>initialize</label>
        <input value={exportMap.initialize} onChange={(e) => props.onExportMapChange({ ...exportMap, initialize: e.target.value })} />
        <label>open_device</label>
        <input value={exportMap.open_device} onChange={(e) => props.onExportMapChange({ ...exportMap, open_device: e.target.value })} />
        <label>close_device</label>
        <input value={exportMap.close_device} onChange={(e) => props.onExportMapChange({ ...exportMap, close_device: e.target.value })} />
        <label>start_capture</label>
        <input value={exportMap.start_capture} onChange={(e) => props.onExportMapChange({ ...exportMap, start_capture: e.target.value })} />
        <label>stop_capture</label>
        <input value={exportMap.stop_capture} onChange={(e) => props.onExportMapChange({ ...exportMap, stop_capture: e.target.value })} />
        <label>read_data</label>
        <input value={exportMap.read_data} onChange={(e) => props.onExportMapChange({ ...exportMap, read_data: e.target.value })} />
      </div>
    </section>
  );
}
