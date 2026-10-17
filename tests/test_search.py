"""The local index: exact names first, then the closest names, scored the same
with or without rapidfuzz."""
import os

import pytest

from mondonorm import SAMPLE_OBO, MondoIndex, mondo
from mondonorm.mondo import MondoTerm

EXCERPT = os.path.join(os.path.dirname(__file__), "data", "mondo_excerpt.obo")


@pytest.fixture(params=[False, True], ids=["difflib", "rapidfuzz"])
def matcher(request, monkeypatch):
    """Run a test once with the standard library's matching and once with rapidfuzz (if installed)."""
    if request.param:
        pytest.importorskip("rapidfuzz")
    monkeypatch.setattr(mondo, "_HAVE_RAPIDFUZZ", request.param)
    if request.param:
        from rapidfuzz import fuzz, process
        monkeypatch.setattr(mondo, "fuzz", fuzz, raising=False)
        monkeypatch.setattr(mondo, "process", process, raising=False)
    return request.param


@pytest.fixture
def sample(tmp_path):
    return MondoIndex.load(SAMPLE_OBO, cache_dir=tmp_path)


@pytest.fixture
def excerpt(tmp_path):
    return MondoIndex.load(EXCERPT, cache_dir=tmp_path)


def test_the_sample_ships_with_the_package(sample):
    assert SAMPLE_OBO.exists() and SAMPLE_OBO.parent.name == "data"
    assert len(sample) == 9
    assert sample.get("MONDO:0005015").label == "diabetes mellitus"
    assert sample.get("mondo_0005015").id == "MONDO:0005015"


def test_a_label_scores_100_and_a_synonym_98(sample, matcher):
    top = sample.search("sickle cell disease")[0]
    assert (top.id, top.score, top.matched_on) == ("MONDO:0011382", 100.0, "label")
    top = sample.search("sickle cell anemia")[0]
    assert (top.id, top.score, top.matched_on) == ("MONDO:0011382", 98.0, "synonym: sickle cell anemia")
    # case, hyphens and spacing do not count
    top = sample.search("  Sickle-Cell   ANEMIA ")[0]
    assert (top.id, top.score) == ("MONDO:0011382", 98.0)


def test_possessives_and_spellings(excerpt, sample, matcher):
    top = excerpt.search("Huntington's chorea")[0]
    assert (top.id, top.score, top.matched_on) == ("MONDO:0007739", 98.0, "synonym: Huntington chorea")
    top = sample.search("sickle cell anaemia")[0]               # the UK spelling
    assert top.id == "MONDO:0011382" and 90 <= top.score <= 96


def test_a_misspelt_name_is_found(sample, excerpt, matcher):
    top = sample.search("diabetis mellitus")[0]
    assert top.id == "MONDO:0005015" and 90 <= top.score <= 96
    assert excerpt.search("duchene muscular dystrophy")[0].id == "MONDO:0010679"


def test_shared_words_count(excerpt, matcher):
    ids = [c.id for c in excerpt.search("breast and ovarian cancer")]
    assert ids[0] == "MONDO:0003582"            # hereditary breast ovarian cancer syndrome


def test_a_name_inside_a_longer_one_is_not_taken_for_it(excerpt, matcher):
    top = excerpt.search("breast cancer in a man")[0]
    assert top.id == "MONDO:0007254" and top.score < 90  # phenotk's default threshold: not accepted unasked


def test_scores_do_not_depend_on_rapidfuzz(excerpt, monkeypatch):
    """rapidfuzz may find more names, but a term found both ways has the same score."""
    pytest.importorskip("rapidfuzz")
    for q in ["breast and ovarian cancer", "huntingtons chorea", "muscular dystrophy in boys", "dmd"]:
        found = {}
        for flag in (False, True):
            monkeypatch.setattr(mondo, "_HAVE_RAPIDFUZZ", flag)
            found[flag] = [(c.id, c.score) for c in excerpt.search(q, limit=5)]
        assert found[False][0] == found[True][0], q
        both = dict(found[False]).keys() & dict(found[True]).keys()
        assert all(dict(found[False])[t] == dict(found[True])[t] for t in both), q


def test_obsolete_terms_are_never_suggested():
    idx = MondoIndex({"MONDO:0000002": MondoTerm("MONDO:0000002", "sickle cell", ["drepanocytosis"], obsolete=True),
                      "MONDO:0011382": MondoTerm("MONDO:0011382", "sickle cell disease", ["sickle cell anemia"])},
                     source="test")
    assert [c.id for c in idx.search("sickle cell disease")] == ["MONDO:0011382"]
    assert "MONDO:0000002" not in [c.id for c in idx.search("drepanocytosis")]


def test_candidates_carry_the_terms_synonyms(sample):
    top = sample.search("type 2 diabetes")[0]
    assert top.id == "MONDO:0005148" and "T2D" in top.synonyms


def test_nothing_is_downloaded_unless_allowed(tmp_path):
    with pytest.raises(FileNotFoundError):
        MondoIndex.load(None, allow_download=False, cache_dir=tmp_path)
    assert mondo.MONDO_OBO_URL.startswith("https://") and mondo.MONDO_JSON_URL.startswith("https://")


def test_the_parsed_index_is_cached(tmp_path):
    first = MondoIndex.load(SAMPLE_OBO, cache_dir=tmp_path)
    assert list(tmp_path.glob("*.idx.pkl"))
    again = MondoIndex.load(SAMPLE_OBO, cache_dir=tmp_path)
    assert len(again) == len(first) and again.search("diabetes")[0].id == "MONDO:0005015"


def test_names_are_compared_without_case_accents_or_possessives():
    from mondonorm.suggest import normalise_text, similarity
    assert normalise_text("Huntington's  Disease") == "huntington disease"
    assert normalise_text("Ménière’s disease") == "meniere disease"
    assert similarity("Down's syndrome", "down syndrome") == 100.0
    assert similarity("diabetes type 2", "type 2 diabetes") == 97.0
    assert similarity("type 1 diabetes", "type 2 diabetes") < 90


def test_the_figures_the_readme_gives():
    from mondonorm.suggest import similarity
    assert similarity("sickle cell anaemia", "sickle cell anemia") == 96.0
    assert round(similarity("breast and ovarian cancer", "hereditary breast and ovarian cancer")) == 84
    assert round(similarity("breast cancer in a man", "breast cancer")) == 77
