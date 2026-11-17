import tempfile

import pytest
from fastapi.testclient import TestClient

from conftest import DATA
from fixtures.synth import synth_clip, write_wav
from raaga.api.app import Settings, create_app
from raaga.theory.ragas import load_raga_table

TABLE = load_raga_table(DATA / "ragas.json")


@pytest.fixture(scope="module")
def wavs(tmp_path_factory):
    d = tmp_path_factory.mktemp("wavs")
    return {
        "mohanam": write_wav(d / "m.wav", synth_clip(["S", "R2", "G3", "P", "D2"], 146.8, 30)).read_bytes(),
        "short": write_wav(d / "s.wav", synth_clip(["S", "P"], 146.8, 5)).read_bytes(),
    }


def make_client(tmp_path, **kw):
    s = Settings(store_dir=tmp_path / "store", raga_table=DATA / "ragas.json", params_path=None,
                 static_dir=kw.pop("static_dir", None), **kw)
    return TestClient(create_app(s))


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    return make_client(tmp_path_factory.mktemp("c"))


def upload(c, data, name="clip.wav", **form):
    return c.post("/api/analyze", files={"file": (name, data, "audio/wav")}, data=form)


def test_health(client):
    j = client.get("/api/health").json()
    assert j == {"ok": True, "model_version": "v0", "examples": 0}


def test_analyze_ok(client, wavs):
    r = upload(client, wavs["mohanam"])
    assert r.status_code == 200
    j = r.json()
    assert j["kind"] in {"confident", "shortlist"}
    assert "Mohanam" in [c["name"] for c in j["candidates"]]


def test_too_short(client, wavs):  # Review Focus 4
    r = upload(client, wavs["short"])
    assert (r.status_code, r.json()["error"]) == (422, "too_short")


def test_bad_shruti(client, wavs):
    r = upload(client, wavs["mohanam"], shruti="H#")
    assert (r.status_code, r.json()["error"]) == (422, "bad_shruti")


def test_undecodable(client):
    r = upload(client, b"junk", name="x.mp3")
    assert (r.status_code, r.json()["error"]) == (415, "undecodable")


def test_too_large(tmp_path, wavs):
    c = make_client(tmp_path, max_upload_bytes=1000)
    r = upload(c, wavs["mohanam"])
    assert (r.status_code, r.json()["error"]) == (413, "too_large")


def test_rate_limit(tmp_path, wavs):
    c = make_client(tmp_path, analyze_per_min=2)
    codes = [upload(c, wavs["short"]).status_code for _ in range(3)]
    assert codes == [422, 422, 429]
    r = upload(c, wavs["short"], )
    assert r.json()["error"] == "rate_limited"


def test_rate_limit_keyed_by_forwarded_for(tmp_path, wavs):
    c = make_client(tmp_path, analyze_per_min=1)
    a = c.post("/api/analyze", files={"file": ("a.wav", wavs["short"])}, headers={"X-Forwarded-For": "1.1.1.1"})
    b = c.post("/api/analyze", files={"file": ("a.wav", wavs["short"])}, headers={"X-Forwarded-For": "2.2.2.2, 9.9.9.9"})
    assert a.status_code == 422 and b.status_code == 422


def test_no_temp_files_left(client, wavs, tmp_path, monkeypatch):
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    upload(client, wavs["mohanam"])
    upload(client, b"junk", name="x.mp3")
    assert list(tmp_path.iterdir()) == []


def test_ragas_search_and_detail(client):
    ids = [r["id"] for r in client.get("/api/ragas", params={"q": "todi"}).json()]
    assert TABLE.resolve("Thodi").id in ids
    assert len(client.get("/api/ragas", params={"q": "a"}).json()) <= 20
    d = client.get(f"/api/ragas/{TABLE.resolve('Mohanam').id}").json()
    assert d["avarohana"][0] == "S" and d["example_count"] == 0 and d["name"] == "Mohanam"
    assert client.get("/api/ragas/nonexistent").status_code == 404


def test_static_spa_fallback(tmp_path):
    static = tmp_path / "static"
    static.mkdir()
    (static / "index.html").write_text("<html>app</html>")
    (static / "app.js").write_text("js")
    c = make_client(tmp_path, static_dir=static)
    assert c.get("/").text == "<html>app</html>"
    assert c.get("/app.js").text == "js"
    assert c.get("/some/route").text == "<html>app</html>"
    assert c.get("/api/nope").status_code == 404
