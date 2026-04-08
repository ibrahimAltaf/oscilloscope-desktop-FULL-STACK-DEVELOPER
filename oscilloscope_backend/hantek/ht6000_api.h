/**
 * HT6000.dll — reference API for Python ctypes bindings.
 *
 * Replace this file with the official Hantek SDK header when yours differs.
 * After updating, align oscilloscope_backend/hantek/sdk.py (argtypes, restype, error codes).
 *
 * Calling convention on Windows: typically __stdcall → use ctypes.WinDLL.
 */

#ifndef HT6000_API_H
#define HT6000_API_H

#ifdef __cplusplus
extern "C" {
#endif

#ifdef _WIN32
#ifndef HT6000_CALL
#define HT6000_CALL __stdcall
#endif
#else
#define HT6000_CALL
#endif

typedef void *HT6000_HANDLE;

/** Open device by index (0 = first unit). *out_handle is written on success. */
int HT6000_CALL HT6000_Open(int device_index, HT6000_HANDLE *out_handle);

/** Release device. handle may be NULL (no-op). */
int HT6000_CALL HT6000_Close(HT6000_HANDLE handle);

/** Start continuous acquisition (single-shot depending on driver config). */
int HT6000_CALL HT6000_StartCapture(HT6000_HANDLE handle);

/** Stop acquisition before close. */
int HT6000_CALL HT6000_StopCapture(HT6000_HANDLE handle);

/**
 * Read raw ADC samples into caller buffer.
 * @param handle       Session from HT6000_Open
 * @param buffer       int16 samples, capacity max_samples
 * @param max_samples  Capacity in samples (not bytes)
 * @param out_count    Filled with number of samples written (may be 0)
 * @return 0 on success, negative error code on failure
 */
int HT6000_CALL HT6000_ReadData(
    HT6000_HANDLE handle,
    short *buffer,
    int max_samples,
    int *out_count
);

#ifdef __cplusplus
}
#endif

#endif /* HT6000_API_H */
