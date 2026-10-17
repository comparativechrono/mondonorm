"""The command line, run on a small family with the bundled sample of MONDO."""
import json
import os
import socket
import subprocess
import sys
import urllib.error

import pytest

import mondonorm
from mondonorm import SAMPLE_OBO, cli
from mondonorm import phenopackets as pp

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

FAMILY = {
    "id": "FAM1",
    "proband": {
        "id": "FAM1-II-1",
        "subject": {"id": "II-1", "sex": "MALE"},
        "diseases": [
            {"term": {"id": "", "label": "Diabetes"}},
            {"term": {"id": "", "label": "sickle cell anemia"}},
            {"term": {"id": "", "label": "type 2 diabetes"}, "excluded": True},
        ],
        "phenotypicFeatures": [{"type": {"id": "", "label": "diabetes"}}],
    },
    "relatives": [{
        "id": "FAM1-I-2",
        "subject": {"id": "I-2", "sex": "FEMALE"},
        "diseases": [{"term": {"id": "", "label": "diabetes"}}],
    }],
}


@pytest.fixture
def family(tmp_path):
    path = tmp_path / "family.json"
    path.write_text(json.dumps(FAMILY), encoding="utf-8")
    return path


def answers(monkeypatch, *replies):
    """Answer the questions in turn; after the last, stop (as at the end of input)."""
    queue = list(replies)

    def reply(prompt=""):
        if not queue:
            raise EOFError
        return queue.pop(0)

    monkeypatch.setattr("builtins.input", reply)


def run(*argv, cache):
    return cli.main([*map(str, argv), "--no-color", "--cache-dir", str(cache)])


def diseases(path):
    return [(r.label, r.id) for r in pp.find_disease_terms(pp.load(path))]


def test_a_mapping_file_matches_names_in_any_case(family, tmp_path, monkeypatch):
    mapping = tmp_path / "terms.json"
    mapping.write_text(json.dumps({
        "DIABETES": "MONDO:0005015",                                         # a bare id, as studio2ga4gh reads
        "Sickle Cell Anemia": {"id": "MONDO:0011382", "label": "sickle cell disease"},
        "Deafness": {"id": "HP:0000365", "label": "Hearing impairment", "kind": "phenotype"},
    }), encoding="utf-8")
    answers(monkeypatch)                                                    # "type 2 diabetes" is asked about: stop
    out = tmp_path / "out.json"
    assert run(family, "--backend", "local", "--mondo-file", SAMPLE_OBO, "--mapping", mapping,
               "--auto-remembered", "-o", out, cache=tmp_path / "cache") == 0
    got = diseases(out)
    assert ("diabetes mellitus", "MONDO:0005015") in got                   # the label looked up for the bare id
    assert ("sickle cell disease", "MONDO:0011382") in got
    assert ("type 2 diabetes", "") in got                                  # left as it was
    # phenotypic features are hponorm's: untouched
    assert pp.load(out)["proband"]["phenotypicFeatures"] == FAMILY["proband"]["phenotypicFeatures"]
    saved = json.loads(mapping.read_text(encoding="utf-8"))
    assert saved["Deafness"]["id"] == "HP:0000365"
    assert saved["DIABETES"] == "MONDO:0005015"
    assert saved["Sickle Cell Anemia"] == {"id": "MONDO:0011382", "label": "sickle cell disease"}


def test_a_choice_is_remembered(family, tmp_path, monkeypatch):
    mapping = tmp_path / "terms.json"
    # Diabetes: the first suggestion; sickle cell anemia: skip; type 2 diabetes: the first suggestion;
    # diabetes (another spelling, so asked about again): the decision remembered for it
    answers(monkeypatch, "1", "x", "1", "r")
    assert run(family, "--backend", "local", "--mondo-file", SAMPLE_OBO, "--mapping", mapping,
               cache=tmp_path / "cache") == 0
    normalised = tmp_path / "family.normalized.json"
    got = diseases(normalised)
    assert got.count(("diabetes mellitus", "MONDO:0005015")) == 2
    assert ("type 2 diabetes mellitus", "MONDO:0005148") in got
    assert pp.load(normalised)["proband"]["diseases"][2]["excluded"] is True
    assert ("sickle cell anemia", "") in got
    saved = json.loads(mapping.read_text(encoding="utf-8"))
    assert saved == {"diabetes": {"id": "MONDO:0005015", "label": "diabetes mellitus"},
                     "type 2 diabetes": {"id": "MONDO:0005148", "label": "type 2 diabetes mellitus"}}
    log = json.loads((tmp_path / "family.normalized.json.mapping.json").read_text(encoding="utf-8"))
    assert [d["action"] for d in log["decisions"]] == ["map", "skip", "map", "map"]


def test_ols_not_answering_is_said(family, tmp_path, monkeypatch, capsys):
    class Unreachable(mondonorm.OlsClient):
        def _get_json(self, url):
            raise urllib.error.URLError(socket.timeout("timed out"))

    monkeypatch.setattr(cli, "OlsClient", Unreachable)
    answers(monkeypatch, "x", "x", "x")
    assert run(family, "--backend", "ols", cache=tmp_path / "cache") == 0
    out = capsys.readouterr().out
    assert "did not answer in time, so there are no suggestions" in out
    assert "No suggestions found" not in out


def test_an_unreadable_mapping_file_is_not_overwritten(family, tmp_path, monkeypatch, capsys):
    mapping = tmp_path / "terms.json"
    mapping.write_text("[1, 2, 3]", encoding="utf-8")
    answers(monkeypatch, "1")
    assert run(family, "--backend", "local", "--mondo-file", SAMPLE_OBO, "--mapping", mapping,
               cache=tmp_path / "cache") == 0
    assert mapping.read_text(encoding="utf-8") == "[1, 2, 3]"
    assert "will not be overwritten" in capsys.readouterr().out


def test_mapping_helpers():
    remembered, others = cli.read_mapping({"resolved": {"Diabetes": "MONDO:0005015", "Deafness": "HP:0000365"},
                                           "unresolved": []})
    assert remembered == {"diabetes": {"id": "MONDO:0005015", "label": ""}} and others == 1
    data, notes = cli.update_mapping({"Deafness": "HP:0000365"},
                                     {"deafness": {"id": "MONDO:0005365", "label": "hearing loss disorder"},
                                      "new name": {"id": "MONDO:0011382", "label": "sickle cell disease"}})
    assert data == {"Deafness": "HP:0000365",
                    "new name": {"id": "MONDO:0011382", "label": "sickle cell disease"}}
    assert len(notes) == 1 and "HP:0000365" in notes[0]


def test_the_package_is_importable_as_the_readme_says():
    from mondonorm import MondoIndex, OlsClient, Suggester  # noqa: F401
    from mondonorm import phenopackets  # noqa: F401
    assert mondonorm.__version__ == "1.1.0"


def test_python_dash_m(tmp_path):
    env = dict(os.environ, PYTHONPATH=ROOT)
    done = subprocess.run([sys.executable, "-m", "mondonorm", "--version"], capture_output=True, text=True,
                          env=env, cwd=str(tmp_path))
    assert done.returncode == 0 and done.stdout.strip() == "mondonorm " + mondonorm.__version__
