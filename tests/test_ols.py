"""The OLS backend, with EBI's Ontology Lookup Service replaced by a fake: OLS is
never asked. The fake's answers have the shape of OLS4's /api/search and
/api/ontologies/mondo/terms responses; the terms in them are Mondo's."""
import socket
import urllib.error
import urllib.parse

import pytest

from mondonorm import SAMPLE_OBO, MondoIndex, OlsClient, Suggester

SEARCH = {
    "response": {
        "numFound": 5,
        "start": 0,
        "docs": [
            {"iri": "http://purl.obolibrary.org/obo/MONDO_0016669", "obo_id": "MONDO:0016669",
             "short_form": "MONDO_0016669", "label": "sickle cell-hemoglobin c disease syndrome",
             "description": ["A rare, genetic hemoglobinopathy characterized by anemia, reticulocytosis and "
                             "erythrocyte abnormalities including target cells, irreversibly sickled cells and "
                             "crystal-containing cells."],
             "synonym": ["HbSC disease", "sickle cell - haemoglobin C disease", "sickle cell - hemoglobin C disease"],
             "ontology_name": "mondo", "type": "class"},
            {"iri": "http://purl.obolibrary.org/obo/MONDO_0011382", "obo_id": "MONDO:0011382",
             "short_form": "MONDO_0011382", "label": "sickle cell disease",
             "synonym": ["Haemoglobin S disease", "HbS disease", "Hemoglobin S disease", "sickle cell anemia",
                         "Sickle Cell Disease", "sickle cell disease", "sickling disorder due to Hemoglobin S"],
             "ontology_name": "mondo", "type": "class"},
            {"iri": "http://purl.obolibrary.org/obo/MONDO_0011382", "obo_id": "MONDO:0011382",
             "label": "sickle cell disease", "ontology_name": "mondo", "type": "class"},
            {"iri": "http://purl.obolibrary.org/obo/HP_0001878", "obo_id": "HP:0001878",
             "label": "Hemolytic anemia", "ontology_name": "hp", "type": "class"},
            {"iri": "http://purl.obolibrary.org/obo/MONDO_0000000", "obo_id": "MONDO:0000000",
             "label": "obsolete sickle cell anemia", "is_obsolete": True, "ontology_name": "mondo",
             "type": "class"},
        ],
    }
}

TERM = {"_embedded": {"terms": [{
    "iri": "http://purl.obolibrary.org/obo/MONDO_0011382", "label": "sickle cell disease",
    "synonyms": ["HbS disease", "sickle cell anemia", "sickling disorder due to Hemoglobin S"],
    "obo_id": "MONDO:0011382"}]}}


class FakeOls(OlsClient):
    """OlsClient with the requests answered here."""

    def __init__(self, answers=None, error=None):
        super().__init__()
        self.answers = answers or {}
        self.error = error
        self.urls = []

    def _get_json(self, url):
        self.urls.append(url)
        if self.error is not None:
            raise self.error
        path = urllib.parse.urlparse(url).path
        for key, answer in self.answers.items():
            if path.endswith(key):
                return answer
        return {}


def test_results_are_scored_by_how_well_they_match():
    found = FakeOls({"/search": SEARCH}).search("sickle cell anaemia", limit=5)
    # OLS put the HbSC syndrome first; the synonym match comes first here
    assert [c.id for c in found] == ["MONDO:0011382", "MONDO:0016669"]
    best = found[0]
    assert best.matched_on == "synonym: sickle cell anemia" and 90 <= best.score <= 96
    assert best.source == "ols" and "HbS disease" in best.synonyms
    assert found[1].score < 90


def test_the_first_result_is_not_taken_for_a_match():
    """mondonorm 1.0 scored OLS's results by rank (100, 96, 92 ...), so the first looked exact."""
    found = FakeOls({"/search": SEARCH}).search("haemoglobin disorder")
    assert found[0].score < 90
    assert all(c.matched_on != "OLS relevance" for c in found)


def test_other_ontologies_obsolete_terms_and_repeats_are_left_out():
    found = FakeOls({"/search": SEARCH}).search("sickle cell", limit=10)
    assert sorted(c.id for c in found) == ["MONDO:0011382", "MONDO:0016669"]


def test_the_request_asks_for_synonyms_and_enough_results():
    ols = FakeOls({"/search": SEARCH})
    ols.search("sickle cell", limit=8)
    query = urllib.parse.parse_qs(urllib.parse.urlparse(ols.urls[0]).query)
    assert query["q"] == ["sickle cell"] and query["ontology"] == ["mondo"]
    assert "synonym" in query["fieldList"][0].split(",")
    assert int(query["rows"][0]) >= 24


def test_a_term_is_looked_up_by_its_id():
    ols = FakeOls({"/terms": TERM})
    term = ols.get("MONDO:0011382")
    assert (term.id, term.label, term.matched_on) == ("MONDO:0011382", "sickle cell disease", "exact id")
    assert "iri=http%3A%2F%2Fpurl.obolibrary.org%2Fobo%2FMONDO_0011382" in ols.urls[0]
    assert "/ontologies/mondo/terms" in ols.urls[0] and ols.last_error is None
    assert FakeOls({"/terms": {"_embedded": {"terms": []}}}).get("MONDO:9999999") is None


@pytest.mark.parametrize("error, words", [
    (urllib.error.URLError(socket.timeout("timed out")), "did not answer in time"),
    (urllib.error.URLError(ConnectionRefusedError(111, "Connection refused")), "did not answer"),
    (urllib.error.HTTPError("https://www.ebi.ac.uk/ols4/api/search", 429, "Too Many Requests", {}, None),
     "answered with an error (HTTP 429 Too Many Requests)"),
    (ValueError("Expecting value"), "could not be read"),
], ids=["timeout", "refused", "http-429", "not-json"])
def test_a_failure_is_explained(error, words):
    assert words in OlsClient.failure_message(error)
    ols = FakeOls(error=error)
    assert ols.get("MONDO:0011382") is None
    assert words in ols.last_error


def test_a_term_ols_does_not_have_is_not_a_failure():
    ols = FakeOls(error=urllib.error.HTTPError("u", 404, "Not Found", {}, None))
    assert ols.get("MONDO:9999999") is None and ols.last_error is None


def test_the_suggester_says_when_ols_did_not_answer():
    sug = Suggester(FakeOls(error=urllib.error.URLError(socket.timeout("timed out"))), name="ols")
    assert sug.suggest("sickle cell anaemia") == []
    assert "did not answer in time" in sug.last_error
    sug.backend = FakeOls({"/search": SEARCH})
    assert sug.suggest("sickle cell anaemia") and sug.last_error is None


def test_the_fallback_answers_and_the_failure_is_still_reported(tmp_path):
    local = MondoIndex.load(SAMPLE_OBO, cache_dir=tmp_path)
    sug = Suggester(FakeOls(error=urllib.error.URLError("no route to host")), fallback=local, name="ols")
    found = sug.suggest("sickle cell anemia")
    assert found[0].id == "MONDO:0011382" and found[0].source == "mondo-local"
    assert "did not answer" in sug.last_error
    assert sug.resolve("MONDO:0011382").label == "sickle cell disease"
    assert "did not answer" in sug.last_error


def test_resolve_without_an_answer():
    sug = Suggester(FakeOls(error=urllib.error.URLError("no route to host")), name="ols")
    assert sug.resolve("MONDO:0011382") is None and "did not answer" in sug.last_error
    sug = Suggester(FakeOls({"/terms": {"_embedded": {"terms": []}}}), name="ols")
    assert sug.resolve("MONDO:9999999") is None and sug.last_error is None


def test_an_opposite_term_from_ols_is_not_a_match():
    """OLS may offer hypotensive disorder, whose synonym is "hypotension", for "Hypertension"."""
    answer = {"response": {"numFound": 1, "start": 0, "docs": [
        {"iri": "http://purl.obolibrary.org/obo/MONDO_0005468", "obo_id": "MONDO:0005468",
         "short_form": "MONDO_0005468", "label": "hypotensive disorder",
         "synonym": ["hypotension", "hypotension (disease)"], "ontology_name": "mondo", "type": "class"}]}}
    found = FakeOls({"/search": answer}).search("Hypertension", limit=5)
    assert [c.id for c in found] == ["MONDO:0005468"] and found[0].score < 50
