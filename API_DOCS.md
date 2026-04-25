# API / RPC Documentation

Primary runtime transport is Electron IPC + JSON-RPC over stdin/stdout to Python service.

## RPC Methods

- `select_dll` `{ dll_path }`
- `inspect_dll` `{}`
- `connect_device` `{ device_index, export_map }`
- `disconnect_device` `{}`
- `start_capture` `{ chunk_size }`
- `stop_capture` `{}`
- `get_status` `{}`
- `shutdown` `{}`

## Event Stream

- `status` => full verification/status payload
- `sample_batch` => `{ timestamp_unix, samples, count, min, max, variance }`
- `log` => `{ level, message }`

## HTTP Contract

See:

- `backend/api/main.py`
- `backend/docs/openapi.yaml`
