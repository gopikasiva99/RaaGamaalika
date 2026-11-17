"""Tonic (shruti) detection and predominant-melody extraction (Essentia)."""
from __future__ import annotations

import numpy as np

from raaga.config import SAMPLE_RATE
from raaga.melody.line import MelodyLine

FRAME_SIZE = 2048
HOP_SIZE = 128


def _es():
    import essentia
    import essentia.standard as es

    essentia.log.warningActive = False
    essentia.log.infoActive = False
    return es


def detect_tonic(audio: np.ndarray) -> float:
    es = _es()
    return float(es.TonicIndianArtMusic(sampleRate=SAMPLE_RATE)(np.asarray(audio, dtype=np.float32)))


def extract_pitch(audio: np.ndarray) -> tuple[np.ndarray, float]:
    es = _es()
    a = es.EqualLoudness(sampleRate=SAMPLE_RATE)(np.asarray(audio, dtype=np.float32))
    pitch, _conf = es.PredominantPitchMelodia(
        sampleRate=SAMPLE_RATE, frameSize=FRAME_SIZE, hopSize=HOP_SIZE)(a)
    return np.asarray(pitch, dtype=np.float32), HOP_SIZE / SAMPLE_RATE


def melody_line_from_audio(audio: np.ndarray, tonic_hz: float | None = None) -> MelodyLine:
    if tonic_hz is None:
        tonic_hz = detect_tonic(audio)
    hz, hop = extract_pitch(audio)
    cents = np.full(hz.shape, np.nan, dtype=np.float32)
    voiced = hz > 0
    cents[voiced] = 1200.0 * np.log2(hz[voiced] / tonic_hz)
    return MelodyLine(float(tonic_hz), hop, cents)
