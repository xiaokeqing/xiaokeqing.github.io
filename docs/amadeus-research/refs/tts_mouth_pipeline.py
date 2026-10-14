<!-- VERBATIM EXCERPT - do not edit.
     source: github.com/Code-Amadeus/Amadeus @ d8fc3690387dd1022d8e9940e86639203d27097a
     file:   tts/playback.py
     quoted: L80-L90, L180-L245
     every quoted line below is byte-identical to upstream; blank separator lines between spans were added by this slicer. -->

/* ---- volume_multiplier / send_interval defaults  [tts/playback.py L80-L90] ---- */
# ---------------------------------------------------------------------------
class StreamPlayer:
    def __init__(self, mouth_sink: MouthSignalSink):
        self.mouth_sink = mouth_sink
        self.volume_multiplier = 3.75
        # PCM-time envelope windows, not a wall-clock send throttle. A 50ms RMS
        # window can straddle and erase a whole short pause between syllables.
        self.send_interval = 0.01
        self.is_playing = False
        self.pyaudio_instance = None
        self.stream = None

/* ---- RMS envelope per 10 ms window -> publish_mouth_value  [tts/playback.py L180-L245] ---- */
        would reintroduce scheduling gaps/underruns. This orders submissions; it
        does not claim to measure when the speaker or display presents them.
        """
        if _is_tensor_like(audio_chunk):
            audio_chunk = audio_chunk.cpu().detach().numpy()
        audio_chunk = np.asarray(audio_chunk, dtype=np.float32)
        rate = int(sample_rate or getattr(self, "_current_rate", None) or 24000)
        window_samples = (
            max(1, int(round(rate * self.send_interval)))
            if mouth_envelope else max(1, len(audio_chunk))
        )
        for offset in range(0, len(audio_chunk), window_samples):
            if is_current is not None and not is_current():
                break
            chunk = audio_chunk[offset : offset + window_samples]
            with self._stream_lock:
                if not self.is_playing or (is_current is not None and not is_current()):
                    break
                if self.stream is None:
                    raise RuntimeError("audio stream is not initialized")
                if before_window is not None:
                    before_window(chunk)
                if not self.is_playing or (is_current is not None and not is_current()):
                    break
                if mouth_envelope:
                    minimum = first_mouth_minimum if offset == 0 else None
                    self._emit_mouth_value_for_audio(chunk, minimum=minimum)
                if not self.is_playing or (is_current is not None and not is_current()):
                    break
                try:
                    self.stream.write(chunk.tobytes())
                except Exception:
                    if mouth_envelope and (is_current is None or is_current()):
                        self.mouth_sink.publish_mouth_value(0.0)
                    raise
            if after_first_write is not None:
                after_first_write()
                after_first_write = None

    def _stop_audio_writer(self) -> None:
        if self._audio_writer_thread is not None and self._audio_writer_thread.is_alive():
            self._audio_write_queue.put(None)
            self._audio_writer_thread.join(timeout=1.0)
        self._audio_writer_thread = None

    def _mouth_value_for_audio(self, audio_chunk, minimum: float | None = None) -> float:
        if audio_chunk is None:
            return 0.0
        if _is_tensor_like(audio_chunk):
            audio_chunk = audio_chunk.cpu().detach().numpy()
        audio_chunk = np.asarray(audio_chunk)
        if audio_chunk.size == 0:
            return 0.0
        if audio_chunk.dtype != np.float32:
            audio_chunk = audio_chunk.astype(np.float32)

        rms = float(np.sqrt(np.mean(audio_chunk ** 2)))
        mouth_value = min(1.0, rms * self.volume_multiplier)
        if minimum is not None and mouth_value > 0.0:
            mouth_value = max(float(minimum), mouth_value)
        return mouth_value

    def _emit_mouth_value_for_audio(self, audio_chunk, minimum: float | None = None) -> float:
        mouth_value = self._mouth_value_for_audio(audio_chunk, minimum=minimum)
        self.mouth_sink.publish_mouth_value(mouth_value)
        return mouth_value
