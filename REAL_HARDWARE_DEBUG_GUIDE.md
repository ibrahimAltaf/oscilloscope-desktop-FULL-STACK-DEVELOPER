# Real Hardware Debug Guide

If capture does not start, use this sequence.

1. Confirm DLL exists:
   - `python main.py --dll-path "C:\path\HTHardDll(1).dll" --duration-s 5`
2. Confirm architecture:
   - Use 64-bit Python with 64-bit DLL, or 32-bit Python with 32-bit DLL.
3. Check exported names:
   - Run once and inspect log output under "export:" lines.
   - Pass exact names using:
     - `--fn-initialize`
     - `--fn-open`
     - `--fn-close`
     - `--fn-start`
     - `--fn-stop`
     - `--fn-read`
4. Verify driver installation:
   - Confirm vendor USB driver is installed from the official SDK package.
5. Verify USB path:
   - Connect directly to motherboard USB (avoid hub for first test).
6. Check initialization sequence:
   - Required order is `inspect -> bind -> initialize -> open -> start -> read`.
7. Run elevated if needed:
   - Some SDKs require Administrator access.
8. Check dependencies:
   - Install Microsoft VC runtime required by vendor DLL.
9. Check device index:
   - Try `--device-index 0`, then `1`, then `2`.
10. If no samples:
   - The app logs `No real signal data received`.
   - Check input signal, channel enable, and acquisition settings in SDK docs.

## Failure Reasons and Fixes

- DLL architecture mismatch (x86/x64)
  - Fix: match Python interpreter architecture with DLL architecture.
- Missing drivers
  - Fix: install official Hantek USB driver from SDK.
- Device unplugged / loose cable
  - Fix: reconnect device and verify in Device Manager.
- Wrong USB interface
  - Fix: use a direct USB port; avoid unpowered hubs.
- Incorrect SDK function names
  - Fix: map exact export names from log output using CLI flags.
- Wrong initialization sequence
  - Fix: keep strict call order in `main.py`.
- Permission issues
  - Fix: run terminal as Administrator.
- Missing DLL dependencies
  - Fix: install VC++ redistributables and vendor runtimes.
