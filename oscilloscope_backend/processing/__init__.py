"""
Signal buffering and processing.

Extension points (keep ctypes out of here):
- FFT / spectrum: add ``processing/fft.py`` operating on ``SampleFrame.samples``.
- Cursors: add measurement helpers consuming buffer snapshots.
- Multi-channel: extend ``SampleFrame`` with channel layout or split de-interleave here.
"""

from oscilloscope_backend.processing.buffer import CircularSampleBuffer, SampleFrame

__all__ = ["CircularSampleBuffer", "SampleFrame"]
