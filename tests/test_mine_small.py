from pathlib import Path

from strausforge.cert import make_certificate, to_jsonl
from strausforge.coverage import coverage_report
from strausforge.erdos_straus import find_solution_fast
from strausforge.mine import mine_identities


def _write_fixture_certs(path: Path, start: int = 2, end: int = 200) -> None:
    lines: list[str] = []
    for n in range(start, end + 1):
        solution = find_solution_fast(n)
        assert solution is not None
        x, y, z = solution
        cert = make_certificate(n=n, x=x, y=y, z=z, method="fixture", elapsed_ms=0.0)
        lines.append(to_jsonl(cert))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_mine_small_finds_symbolic_identity(tmp_path: Path) -> None:
    certs_file = tmp_path / "certs.jsonl"
    out_file = tmp_path / "identities.jsonl"
    _write_fixture_certs(certs_file)

    identities = mine_identities(certs_file, out_file, max_identities=20)

    assert out_file.exists()
    assert len(identities) >= 1
    assert any("symbolic" in identity.notes for identity in identities)


def test_mine_small_breaks_mod4_wall(tmp_path: Path) -> None:
    certs_file = tmp_path / "certs.jsonl"
    out_file = tmp_path / "identities.jsonl"
    _write_fixture_certs(certs_file, end=260)

    identities = mine_identities(certs_file, out_file, max_identities=30)
    report = coverage_report(identities, modulus=16)

    assert report["covered_pct"] > 75.0
    assert any(residue % 4 == 1 for residue in report["covered_residues"])
