# Evaluation

## Method

- **Cases.** 14 fictitious cases (`data/cases/`, 20 documents in DE, FR and IT). Each has an
  `expected.json` written by hand before any run.
- **Command.** `make eval` (or `python -m beneficia.cli eval data/cases`) analyses every case with the live
  model and scores it with `beneficia.evaluate`. No other model is involved in scoring.
- **Metric definitions.** See the technical report, section 5. A case is *correct* when the set of
  beneficial owners matches exactly (name, basis, band and status) and every expected review reason is
  raised.
- **Runs.** Every run below used the same cases and the same model file; only the code changed between
  runs. The final run's results, including every raw model output, are in `data/results/`.
- **Reproduce without the model.** `make replay` (or `python -m beneficia.cli replay data/results`)
  re-runs ingestion, citation checks and rules on the recorded model outputs and recomputes the scores in
  seconds.

## Iterations and what each one fixed

Each failure was traced to its cause by replaying the recorded model outputs, so a code fix could be
checked in seconds before a new live run.

| Run | Main change | Failures it removed |
|---|---|---|
| v1 | First full pipeline: 6 passes, citations by line id, checks with a tolerance of one line | baseline |
| v2 | A total is accepted only from a capital line. A retry pass on register rows that produced no holding. Agreements must have agreement wording near them. Duplicate rows merged. Totals cross-checked against capital lines | wrong totals read from holding rows; forgotten table rows; agreements invented from "actions nominatives" |
| v3 | Numbers and holders must be on the cited line, and an off-by-one citation is re-anchored instead of tolerated. The company of a row is taken from the register heading when the row names none. Postal code guard. Board roles copied from the line | a share count copied from the neighbouring line (500 instead of 325); postal codes read as quantities |
| v4, v5 (subsets) | A capital pass on capital lines with the heading as context. A retry instruction and invented example for company holders. A principal is accepted only after a fiduciary formula ("pour le compte de"). Fiduciary wording always sent to review. A vote-only basis must be written | totals missed by the general pass; "Ltd : 700 actions" rows; a principal set to the name of a contract |
| final | The company of board and capital lines is taken from the line itself or the document title | a board chair attached to a holding company named on the line above |

Two properties held in **every** run, including the first:
- **Zero silent errors.** No beneficial owner was ever settled wrongly. When extraction failed, the
  checks either dropped the fact or turned the finding into "to be reviewed".
- **100 % citation validity.** Every reference shown resolves to a line of the source document.

## Model errors caught by the checks (examples from real runs)

| What Apertus returned | What the code did |
|---|---|
| Share count 500 for a holder whose line says 325 (500 is the total on the line above) | dropped: number not on the cited line |
| Company "Holz Invest GmbH", copied from the prompt's invented example | rejected, then repaired from the row read on the same line |
| Company "Mystère Société", which appears nowhere | dropped |
| Postal code "1630" given as the number of shares | dropped: postal code |
| Principal "convention de fiducie du 3 mars 2024" | rejected: not after a fiduciary formula; the line was sent to review as fiduciary |
| Voting agreement whose "controlled party" is the company itself | dropped: the bound party must be a shareholder |
| Role "Präsident des Verwaltungsrates" for a French line | replaced by the line's own wording |

## Results

**Reference run: final code in the Docker image, started with `--network none`** (`make offline-test`).
It is the last column. The per-case table below is from that run, and its outputs are recorded in
`data/results/`.

| Setup | Runtime |
|---|---|
| v1 to final native | Intel Core i5-8400 (6 cores, AVX2), 32 GB RAM, no GPU, Windows 11, llama.cpp b10549 native build, 6 threads |
| Air-gapped container | Same machine. Docker Desktop on WSL2 with 6 CPUs and 16.7 GB RAM, official llama.cpp server image b10548, 6 threads, no network interface |

- **v1** was stopped after 6 complete cases.
- **The scan (case12)** needs Tesseract. Tesseract is installed only in the image, so the scan fails in the
  native runs and passes in the container (OCR confidence 93).
- **The container is slower** than the native build on this Windows host, because it runs inside the WSL2
  virtual machine.
- **All times** come from a desktop that had been running evaluations for hours.

| Metric | v1 | v2 | v3 | final native | final, air-gapped container |
|---|---|---|---|---|---|
| Cases | 6 | 14 | 14 | 14 | 14 |
| Cases fully correct (owners and review) | 1 / 6 | 6 / 14 | 7 / 14 | 13 / 14 | 14 / 14 |
| Beneficial owners exactly right | 1 / 6 | 6 / 14 | 8 / 14 | 13 / 14 | 14 / 14 |
| Expected review reasons all raised | 6 / 6 | 12 / 14 | 11 / 14 | 14 / 14 | 14 / 14 |
| Silent errors (settled and wrong) | 0 | 0 | 0 | 0 | 0 |
| Citation validity | 100 % | 100 % | 100 % | 100 % | 100 % |
| Holdings precision (all) | 84 % | 86 % | 95 % | 98 % | 98 % |
| Holdings recall (all) | 76 % | 79 % | 81 % | 94 % | 98 % |
| Holdings recall (DE) | 82 % | 83 % | 83 % | 92 % | 100 % |
| Holdings recall (FR) | 67 % | 71 % | 71 % | 94 % | 94 % |
| Holdings recall (IT) | 75 % | 83 % | 100 % | 100 % | 100 % |
| Seconds per case, mean | 124.9 | 110.5 | 148.5 | 174.3 | 246.2 |
| Seconds per case, max | 148.7 | 226.8 | 238.8 | 316.8 | 449.4 |

**Per case (final, air-gapped container)**

| Case | Lang | Docs | Correct | Holdings found | Seconds | Errors |
|---|---|---|---|---|---|---|
| case01_direct_de | DE | 1 | yes | 3/3 (3 predicted) | 249.5 |  |
| case02_indirect_fr | FR | 2 | yes | 4/4 (4 predicted) | 374.4 |  |
| case03_two_level_de | DE | 3 | yes | 5/5 (5 predicted) | 449.4 |  |
| case04_pact_de | DE | 2 | yes | 3/3 (3 predicted) | 292.9 |  |
| case05_fiduciary_fr | FR | 1 | yes | 2/2 (2 predicted) | 206.1 |  |
| case06_below_it | IT | 1 | yes | 4/4 (4 predicted) | 205.0 |  |
| case07_nobody_de | DE | 2 | yes | 5/5 (5 predicted) | 301.7 |  |
| case08_trap_fr | FR | 2 | yes | 4/4 (4 predicted) | 273.8 |  |
| case09_inconsistent_de | DE | 1 | yes | 2/2 (2 predicted) | 137.9 |  |
| case10_foreign_fr | FR | 1 | yes | 2/2 (2 predicted) | 153.3 |  |
| case11_docx_it | IT | 1 | yes | 2/2 (2 predicted) | 186.3 |  |
| case12_scan_de | DE | 1 | yes | 2/2 (2 predicted) | 74.1 |  |
| case13_chain_pact_de | DE | 1 | yes | 4/4 (4 predicted) | 210.9 |  |
| case14_chain_fiduciary_fr | FR | 1 | yes | 4/5 (5 predicted) | 332.1 |  |
