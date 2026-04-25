# Setup on Windows

1. Install Python 3.11 x64.
2. Install Node.js 20+.
3. Install Hantek USB driver from official SDK package.
4. Open PowerShell at repo root.
5. Install dependencies:
   - `py -3 -m pip install -r requirements.txt`
   - `npm --prefix desktop/oscilloscope-desktop-main install`
6. Launch app:
   - `npm --prefix desktop/oscilloscope-desktop-main run electron:dev`
7. In app:
   - Select DLL path.
   - Inspect DLL.
   - Map functions.
   - Connect device.
   - Start capture.
