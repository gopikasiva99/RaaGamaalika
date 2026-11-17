import shutil

import pytest
from fastapi.testclient import TestClient
from yt_dlp.utils import DownloadError

from conftest import DATA
from fixtures.synth import synth_clip, write_wav
from raaga.api.app import Settings, create_app
from raaga.audio import youtube


class FakeYDL:
    last_opts: dict = {}
    raise_msg: str | None = None
    source = None

    def __init__(self, opts):
        FakeYDL.last_opts = opts

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def download(self, urls):
        if FakeYDL.raise_msg:
            raise DownloadError(FakeYDL.raise_msg)
        out = FakeYDL.last_opts["outtmpl"]["default"].replace("%(ext)s", "wav")
        shutil.copy(FakeYDL.source, out)
        return 0


@pytest.fixture
def fake_ytdl(monkeypatch, tmp_path):
    FakeYDL.raise_msg = None
    FakeYDL.source = write_wav(tmp_path / "src.wav", synth_clip(["S", "R2", "G3", "P", "D2"], 146.8, 30))
    monkeypatch.setattr(youtube.yt_dlp, "YoutubeDL", FakeYDL)
    return FakeYDL


@pytest.fixture
def client(tmp_path):
    return TestClient(create_app(Settings(store_dir=tmp_path / "store", raga_table=DATA / "ragas.json")))


def test_rejects_non_youtube(client, fake_ytdl):
    r = client.post("/api/analyze/youtube", json={"url": "https://evil.example/x"})
    assert (r.status_code, r.json()["error"]) == (422, "bad_url")


def test_blocked_maps_to_502(client, fake_ytdl):
    fake_ytdl.raise_msg = "ERROR: Sign in to confirm you're not a bot"
    r = client.post("/api/analyze/youtube", json={"url": "https://youtu.be/abc"})
    assert (r.status_code, r.json()["error"]) == (502, "youtube_blocked")


def test_segment_analyzed(client, fake_ytdl):
    r = client.post("/api/analyze/youtube", json={"url": "https://www.youtube.com/watch?v=abc", "start": 90})
    assert r.status_code == 200 and "Mohanam" in [c["name"] for c in r.json()["candidates"]]
    ranges = list(fake_ytdl.last_opts["download_ranges"]({}, None))
    assert ranges == [{"start_time": 90, "end_time": 210}]
    assert fake_ytdl.last_opts["noplaylist"] is True


def test_bad_shruti_on_youtube(client, fake_ytdl):
    r = client.post("/api/analyze/youtube", json={"url": "https://youtu.be/abc", "shruti": "Q"})
    assert r.json()["error"] == "bad_shruti"


@pytest.mark.parametrize("url", ["https://m.youtube.com/watch?v=x", "https://music.youtube.com/watch?v=x",
                                 "http://youtube.com/shorts/x"])
def test_accepted_hosts(url):
    youtube.validate_url(url)


@pytest.mark.parametrize("url", ["ftp://youtube.com/x", "https://youtube.com.evil.io/x", "notaurl"])
def test_rejected_hosts(url):
    with pytest.raises(youtube.YouTubeInvalid):
        youtube.validate_url(url)
