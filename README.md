# mondonorm

Interactively **validate and normalise the disease terms** in GA4GH
phenopacket / family JSON files against the **MONDO** disease ontology.

If your tool currently emits disease terms with an empty `id` and a free-text
label:

```json
"diseases": \[ { "term": { "id": "", "label": "sickle cell" } } ]
```

`mondonorm` walks the file, finds every disease term, suggests the most likely
MONDO terms for each label, lets you pick one (or type a MONDO id yourself), and
writes a normalised copy:

```json
"diseases": \[ { "term": { "id": "MONDO:0011382", "label": "sickle cell disease" } } ]
```

## How suggestions are sourced

Two interchangeable backends; pick with `--backend`:

|Backend|What it uses|Network|
|-|-|-|
|`ols`|EBI Ontology Lookup Service v4 (live MONDO)|required|
|`local`|A local `mondo.obo` / `mondo.json`, downloaded + cached on first use|only for the one-time download|
|`auto`|OLS if reachable, otherwise local (the default)|preferred|

The official ontology file can be fetched automatically (from
`purl.obolibrary.org/obo/mondo.obo`) or supplied with `--mondo-file`.
A tiny **illustrative** offline sample (`mondonorm/data/mondo-sample.obo`,
9 terms) ships with the package so you can try the tool with no network — it is
**not** a substitute for the real ontology.

## Install

```bash
pip install -e .                 # installs the `mondonorm` command
pip install -e ".\[recommended]"  # + rapidfuzz (better matching) and rich (nicer UI)
```

Both extras are optional: without `rapidfuzz` it falls back to stdlib `difflib`;
without `rich` it prints plain text.

## Quick start

```bash
# Online (auto-detects OLS):
mondonorm autosomal-dominant-colours\_phenopackets.json

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
Select \[#, s words, m MONDO:id, r, k, x, ?, q]:
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
resolves in MONDO and whether its canonical label matches the existing label.

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
```

Process several files in one go; remembered decisions carry across them:

```bash
mondonorm \*.json --mapping team-mondo-map.json
# next time, reuse without re-typing:
mondonorm new/\*.json --mapping team-mondo-map.json --auto-remembered
```

## Use as a library

```python
from mondonorm import MondoIndex, OlsClient, Suggester
from mondonorm import phenopackets as pp

sug = Suggester(OlsClient(), name="ols")          # or Suggester(MondoIndex.load(...))
for c in sug.suggest("sickle cell", limit=5):
    print(c.id, c.label, c.score)

data = pp.load("myfile.json")
for ref in pp.find\_disease\_terms(data):
    print(ref.path, ref.label, ref.id)
```

## Getting the full MONDO ontology

* Browser / search: https://mondo.monarchinitiative.org
* Direct files: `http://purl.obolibrary.org/obo/mondo.obo` or `.../mondo.json`
* Releases: https://github.com/monarch-initiative/mondo/releases

Phenopackets reference: https://phenopacket-schema.readthedocs.io
(disease terms use MONDO `OntologyClass` values).

