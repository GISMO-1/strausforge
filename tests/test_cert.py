from strausforge.cert import from_jsonl, make_certificate, to_jsonl


def test_certificate_jsonl_roundtrip() -> None:
    cert = make_certificate(n=17, x=5, y=34, z=170, method="greedy2", elapsed_ms=1.25)
    line = to_jsonl(cert)
    loaded = from_jsonl(line)

    assert loaded == cert
    assert loaded.residue["n_mod_4"] == 1
    assert loaded.residue["n_mod_12"] == 5
    assert loaded.residue["n_mod_24"] == 17
