import numpy as np
import pytest

from fixtures.synth import encode, synth_clip, write_wav
from raaga.audio.decode import AudioDecodeError, decode_audio


@pytest.mark.parametrize("ext", ["wav", "m4a", "webm", "mp4"])
def test_decodes_phone_formats(tmp_path, ext):  # Review Focus 3
    wav = write_wav(tmp_path / "c.wav", synth_clip(["S", "R2", "G3", "P", "D2"], 146.8, 12))
    a = decode_audio(wav if ext == "wav" else encode(wav, ext))
    assert a.dtype == np.float32
    assert abs(len(a) / 44100 - 12) < 0.2
    assert np.max(np.abs(a)) > 0.05


def test_window_and_offset(tmp_path):
    wav = write_wav(tmp_path / "c.wav", synth_clip(["S", "P"], 146.8, 200))
    assert abs(len(decode_audio(wav, start_s=30, max_s=120)) / 44100 - 120) < 0.1


def test_garbage_raises(tmp_path):
    p = tmp_path / "x.mp3"
    p.write_bytes(b"not audio")
    with pytest.raises(AudioDecodeError):
        decode_audio(p)


def test_synth_is_deterministic():
    a = synth_clip(["S", "G3", "P"], 146.8, 3, seed=1)
    b = synth_clip(["S", "G3", "P"], 146.8, 3, seed=1)
    assert np.array_equal(a, b) and a.dtype == np.float32


def test_synth_leading_silence():
    a = synth_clip(["S", "P"], 146.8, 10, leading_silence_s=4, drone=False)
    assert np.max(np.abs(a[: 44100 * 3])) == 0.0
    assert abs(len(a) / 44100 - 10) < 0.01
