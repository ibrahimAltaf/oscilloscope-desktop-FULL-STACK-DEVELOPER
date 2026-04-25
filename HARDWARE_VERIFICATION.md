# Hardware Verification

Use the **Hardware Verification Report** panel in the Electron app.

Checklist:

1. DLL path selected
2. DLL found = yes
3. DLL architecture matches Python/Electron architecture
4. Export list visible
5. Function mapping set to real exports
6. Device detected = yes
7. Device connected = yes
8. Capture started = yes
9. Real samples received = yes
10. Sample count increases continuously
11. Min/max/variance changes over time
12. Final status = `REAL HARDWARE VERIFIED`

If final status is not verified, export TXT/JSON report and inspect `verification_reason`.
