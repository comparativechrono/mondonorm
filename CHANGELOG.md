# Changelog

## 1.1.0

- **OLS results are scored by how well they match.** Version 1.0 gave EBI's
  Ontology Lookup Service's results scores from their place in its list (100,
  96, 92 …), so the first result always looked like an exact match, and
  anything that compared the score with a threshold, as phenopacket-toolkit
  0.3 did, accepted it whatever it was. Each result is now scored by how
  closely its label, or one of the synonyms OLS returns with it, matches the
  name: 100 for the label, 98 for a synonym, at most 96 otherwise. The results
  come best first, keep their synonyms (`Candidate.synonyms`), and say what
  matched (`matched_on` is `label` or `synonym: …`, no longer `OLS relevance`).
- **The local search is faster and ranks better without rapidfuzz.** It used to
  compare the name with every label and synonym in MONDO, some 125,000 of them,
  with `difflib`, which took four to six seconds per name and ranked by shared
  letters alone: "bowel cancer" put *bone cancer* second. It now shortlists
  the names that share a word with the one searched for, or a word spelt nearly
  the same, and scores them as OLS's results are scored: well under a second
  per name, with shared words counting (*colorectal carcinoma*, "large bowel
  cancer", now comes second). rapidfuzz, if installed, adds names that are
  alike letter by letter; the scores are the same with or without it, and
  case, punctuation and possessives ("Huntington's disease") no longer lower
  them. An exact synonym now always scores 98, below the label's 100; 1.0
  could give it 100.
- **A failed request to OLS is reported.** The `Suggester` turned a failed
  request into "no suggestions", so an unreachable OLS looked like a name with
  no match. It still returns a list, but now records why in
  `Suggester.last_error` (and `OlsClient.last_error` for `get`), and the
  command says "EBI's Ontology Lookup Service did not answer …" instead of "No
  suggestions found".
- **`--mapping` matches names without regard to case.** A mapping file had to
  have lower-case names. It may now have names in any case, entries that give
  only the id (`"Breast cancer": "MONDO:0007254"`), and entries for other
  ontologies, which are kept as they are, so one terms file can serve
  mondonorm, hponorm, studio2ga4gh and phenotk. An existing entry keeps its own
  form when it is updated, and a mapping file that cannot be read is no longer
  overwritten.
- `python -m mondonorm` and `from mondonorm import MondoIndex, OlsClient,
  Suggester` work, as the README said: the package had no `__init__.py` or
  `__main__.py`. `mondonorm.__version__` and `mondonorm --version` are new.
- The sample ontology the README described, `mondonorm/data/mondo-sample.obo`,
  was missing; it is now included, with nine terms copied from the Mondo
  release of 2026-10-06 (`mondonorm.SAMPLE_OBO`).
- MONDO is downloaded from `https://purl.obolibrary.org/obo/mondo.obo` (it was
  plain http).
- The decision log of an `--auto-remembered` label now records the file's label
  and MONDO's label separately, as for one chosen by hand.
- Packaging: a licence expression, the README as the description on PyPI,
  links to the repository, a `test` extra, and tests (run on Python 3.9 to
  3.14) that never go online.

## 1.0.0

Released on PyPI on 1 June 2026.
