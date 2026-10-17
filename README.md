# mondonorm

Interactively **validate and normalise the disease terms** in GA4GH
phenopacket / family JSON files against the **MONDO** disease ontology.

If your tool currently emits disease terms with an empty `id` and a free-text
label:

```json
"diseases": [ { "term": { "id": "", "label": "sickle cell" } } ]
```

`mondonorm` walks the file, finds every disease term, suggests the most likely
MONDO terms for each label, lets you pick one (or type a MONDO id yourself), and
writes a normalised copy:

```json
"diseases": [ { "term": { "id": "MONDO:0011382", "label": "sickle cell disease" } } ]
```

## How suggestions are sourced

Two interchangeable backends; pick with `--backend`:

| Backend | What it uses | Network |
|---------|--------------|---------|
| `ols`   | EBI Ontology Lookup Service v4 (live MONDO) | required |
| `local` | A local `mondo.obo` / `mondo.json`, downloaded + cached on first use | only for the one-time download |
| `auto`  | OLS if reachable, otherwise local (the default) | preferred |

The official ontology file can be fetched automatically (from
`https://purl.obolibrary.org/obo/mondo.obo`) or supplied with `--mondo-file`.
A tiny **illustrative** offline sample (`mondonorm/data/mondo-sample.obo`,
9 terms, copied from the Mondo release of 2026-10-06) ships with the package so
you can try the tool with no network — it is **not** a substitute for the real
ontology. In Python its path is `mondonorm.SAMPLE_OBO`.

If OLS does not answer (no connection, a time-out, or an error from EBI's
server), mondonorm says so, rather than showing "no suggestions" as if the name
had no match. In `auto` mode, when a copy of MONDO is already on the computer,
the suggestions then come from that copy, and mondonorm says that too.

## How suggestions are scored

Both backends score a suggestion in the same way, from 0 to 100:

* **100**: the name is the term's label, once case, accents, possessives and
  punctuation are set aside ("Huntington's disease" and "Huntington disease"
  are the same name);
* **98**: the name is one of the term's synonyms;
* **97**: the same words in another order ("diabetes type 2");
* **96 or less**: otherwise, how closely the name matches the label or the
  closest synonym. This is the mean of how alike they are letter by letter and
  the share of their words they have in common, where a plural, a word with an
  ending or a close spelling of a longer word ("anaemia", "anemia") counts as
  nearly the same word. So "sickle cell anaemia" scores 96 against *sickle cell
  disease*, whose synonym is "sickle cell anemia", "breast and ovarian cancer"
  puts *hereditary breast ovarian cancer syndrome* (84) before *breast cancer*,
  and a name inside a longer one is not taken for it: "breast cancer in a man"
  scores 77 against *breast cancer*.

OLS returns its results in its own order of relevance; mondonorm scores each of
them as above and shows the closest first. (Version 1.0 scored OLS's results
by their place in that order, 100, 96, 92 and so on, so the first always looked
like an exact match.) A threshold, such as the default of 0.9 (90 here) in
[phenopacket-toolkit](https://pypi.org/project/phenopacket-toolkit/)'s
`phenotk normalise`, therefore means the same whichever backend found the term.

The local backend finds the names that share a word with the one searched for,
or a word spelt nearly the same, and scores those: well under a second per name
for the whole of MONDO, with or without `rapidfuzz`. With `rapidfuzz` installed
it also looks at names that are alike letter by letter but share no word (a
name written as one word, say); a term found either way gets the same score.

## Install

```bash
pip install -e .                 # installs the `mondonorm` command
pip install -e ".[recommended]"  # + rapidfuzz (better matching) and rich (nicer UI)
```

Both extras are optional: without `rapidfuzz` the local search uses only its
own word index and the standard library's `difflib`; without `rich` it prints
plain text.

## Quick start

```bash
# Online (auto-detects OLS):
mondonorm autosomal-dominant-colours_phenopackets.json

# Fully offline against a downloaded ontology:
mondonorm myfile.json --backend local --mondo-file /path/to/mondo.obo

# Try it offline with the bundled sample (diabetes / sickle cell only):
mondonorm myfile.json --backend local --mondo-file mondonorm/data/mondo-sample.obo

# Equivalent without installing:
python -m mondonorm myfile.json
```

## The interactive review

Each **distinct** label is reviewed once and the decision is applied to every
occurrence (so "diabetes" appearing 8 times is one question, not eight). For
each label you see a ranked table and a prompt:

```
Select [#, s words, m MONDO:id, r, k, x, ?, q]:
  <number>     select that suggestion
  s <words>    search again with different words
  m MONDO:id   enter a MONDO id manually (validated, canonical label fetched)
  r            reuse a decision remembered from earlier in this session
  k            keep the current term unchanged
  x            skip this label (leave it unmapped)
  ?            help
  q            finish now: apply decisions made so far and save
```

If a term already has an `id`, it is validated: the tool reports whether the id
resolves in MONDO and whether its canonical label matches the existing label
(or, if OLS did not answer, that the id could not be checked).

## Output

For `input.json` (unless you pass `--out` or `--in-place`):

* `input.normalized.json` — the normalised phenopacket (only `term.id` /
`term.label` are changed; everything else, including the pedigree, is left
exactly as-is).
* `input.normalized.json.mapping.json` — a decision log (label → MONDO id, count).

## Useful options

```
--out PATH            output path (single input file only)
--in-place            overwrite the input file(s)
--backend {auto,ols,local}
--mondo-file PATH     local mondo.obo or mondo.json
--cache-dir DIR       where the downloaded MONDO + parsed index are cached
--update              re-download / re-parse MONDO
--no-download         never download (local backend must find a file)
--no-online           never use OLS, even in auto mode
--limit N             suggestions shown per label (default 8)
--mapping FILE        load/save remembered label->term decisions across runs
--auto-remembered     auto-apply remembered labels without prompting
--no-color            plain text output
--version             the version of mondonorm
```

Process several files in one go; remembered decisions carry across them:

```bash
mondonorm *.json --mapping team-mondo-map.json
# next time, reuse without re-typing:
mondonorm new/*.json --mapping team-mondo-map.json --auto-remembered
```

### The mapping file

The mapping file is a JSON object of names and the terms chosen for them.
mondonorm writes each new entry as `"sickle cell": {"id": "MONDO:0011382",
"label": "sickle cell disease"}`, and since version 1.1 it reads the names
without regard to case, so you can write one by hand as you like:

```json
{
  "Sickle cell anaemia": {"id": "MONDO:0011382", "label": "sickle cell disease"},
  "Breast cancer": "MONDO:0007254",
  "Deafness": "HP:0000365"
}
```

An entry may give the id alone (mondonorm then looks up its label), and entries
for other ontologies are left as they are, so the same file can serve
`hponorm`, studio2ga4gh's `--terms` and `phenotk normalise --mapping`. A
decision log from `phenotk normalise --log` (`{"resolved": {...}}`) can be read
too. When mondonorm saves its decisions, an entry already in the file keeps its
own form; and a file it cannot read is left untouched.

## Use as a library

```python
from mondonorm import MondoIndex, OlsClient, Suggester
from mondonorm import phenopackets as pp

sug = Suggester(OlsClient(), name="ols")          # or Suggester(MondoIndex.load(...))
for c in sug.suggest("sickle cell", limit=5):
    print(c.id, c.label, c.score, c.matched_on)
if sug.last_error:                                 # e.g. "EBI's Ontology Lookup Service did not answer in time"
    print(sug.last_error)

data = pp.load("myfile.json")
for ref in pp.find_disease_terms(data):
    print(ref.path, ref.label, ref.id)
```

## Getting the full MONDO ontology

* Browser / search: https://mondo.monarchinitiative.org
* Direct files: `https://purl.obolibrary.org/obo/mondo.obo` or `.../mondo.json`
* Releases: https://github.com/monarch-initiative/mondo/releases

Phenopackets reference: https://phenopacket-schema.readthedocs.io
(disease terms use MONDO `OntologyClass` values).

## Development

```bash
pip install -e ".[test]"
pytest
```

The tests never go online: they use the bundled sample, a few terms copied
from MONDO into `tests/data`, and a stand-in for OLS that answers with JSON
written for the tests.

## Licence

MIT. The sample and test ontologies are excerpts of Mondo, which is released
under CC BY 4.0.
