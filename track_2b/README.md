# Beneficia

**Offline drafts of Swiss beneficial owner declarations, built with Apertus.**

Since 1 October 2026, Swiss companies must report their beneficial owners to the federal transparency
register (TJPG / LTPM, SR 955.3, and its ordinance TJPV / OTPM, AS 2026 364). Fiduciaries prepare these
reports for many clients from confidential documents (share registers, articles, shareholder agreements,
fiduciary agreements), often scanned, in German, French or Italian. Those documents are covered by
professional secrecy and must not leave the office.

Beneficia runs entirely on the fiduciary's own machine, inside one Docker container, with no network at
runtime. Apertus v1.5 8B reads the case folder and extracts facts with line citations. Deterministic,
tested code applies the law. Everything the law does not settle is sent to a human.

| | |
|---|---|
| Track | 2B, Own Project |
| Target architecture | **b) Air-gapped** (also runs on premise) |
| Model | `swiss-ai/Apertus-v1.5-8B`, text-only GGUF Q4_K_M, llama.cpp, CPU |
| Interface | German and French |
| Input | One folder per company: PDF (text or scan), PNG/JPG/TIFF, DOCX, TXT |
| Output | Draft declaration, ownership diagram with clickable sources, justification note, review list, documents to request, JSON |

## How it works

```
case folder ──► numbered lines ──► Apertus: 8 narrow extraction passes ──► code checks every citation
 (PDF, scan,     (OCR for scans,    companies, capital, holdings (table,    (name and number must be on
  DOCX, TXT)      Tesseract)        prose, retry), agreements, board,       the cited line, or dropped)
                                    persons
                                                                                     │
draft + diagram + note + review list ◄── rules engine (TJPG art. 4, TJPV art. 1 to 4, 12, 13, 15) ◄┘
```

1. **Apertus extracts, code decides.** The model never computes a percentage. It copies names and numbers
   and cites line ids. A JSON schema grammar restricts each citation to the ids of the lines it was shown.
2. **No source, no line.** Every name and number is checked against the cited line. Facts that do not
   check out are dropped and counted. The quoted text is produced by code, never typed by the model.
3. **Law cited, never invented.** Each rule carries its article. Indirect control follows TJPV art. 2:
   more than 50 percent of an intermediate entity that holds at least 25 percent. Percentages are never
   multiplied along a chain.
4. **Unclear means human.** The following are never decided silently:
   - voting agreements, fiduciary holdings, trusts, special holders;
   - undocumented or foreign holders;
   - inconsistent figures and poor scans;
   - the default manager rule (TJPG art. 4 para. 2).

## Run

Requirements: Docker, 8 GB RAM minimum (16 GB recommended), about 12 GB of free disk space, and internet
access during the build only.

```bash
make run          # builds the image (downloads the 5.06 GB model once), then opens http://127.0.0.1:8080
make test         # unit and integration tests, inside the container, without network
make eval         # runs the fictitious evaluation set, writes data/output/eval/summary.json
make offline-test # same pipeline in a container started with --network none
```

`make` works from the repository root and from `track_2b/`.

Without `make` (for example on Windows), run the same commands from `track_2b/`:

```bash
docker build --load -t beneficia:latest .
docker run --rm -p 127.0.0.1:8080:8080 -v "$PWD/data:/data" beneficia:latest web
docker run --rm --network none beneficia:latest test
docker run --rm --network none -v "$PWD/data:/data" beneficia:latest offline-check
docker run --rm --network none -v "$PWD/data:/data" beneficia:latest replay
```

The first start of a fresh image takes a few minutes while Docker unpacks it. After that, the model loads
in under a minute.

The model file comes from the Hugging Face repository
`Colby/apertus-v1.5-8b-text-Q4_K_M-GGUF` at a pinned revision and is checked against its SHA256. This
repository is not gated, so judges need no account or token. Lineage, licence and the acceptable use
policy are described in the [technical report](technical_report.md#3-use-of-apertus).

Environment variables (template convention): `LLM_NAME`, `LLM_BASE_URL`, `LLM_API_KEY`. By default they
point to the model server inside the container. `LLM_THREADS` and `LLM_CTX` tune the CPU server.

## Measured speed

See [docs/evaluation.md](docs/evaluation.md). All figures there were measured on the hardware stated
next to them. No figure in this repository is estimated.

## Privacy

Documents, intermediate files and drafts stay in `data/` on the host. The container makes no outbound
connection at runtime, and `make offline-test` proves it. Beneficia never connects to EasyGov and never
files anything. Its output is a draft for the fiduciary to verify, not legal advice.

## Repository

```
track_2b/
├── Makefile, Dockerfile, docker/entrypoint.sh
├── src/beneficia/       ingest/, extract/, rules/, report/, web/, pipeline.py, evaluate.py, cli.py
├── src/tests/           unit tests (rules first) and an integration test on recorded model outputs
├── data/cases/          14 fictitious evaluation cases with expected.json; data/tools/make_cases.py
├── docs/                evaluation results, design notes, architecture
└── technical_report.md
```

## Licence

Code: Apache 2.0 (see `LICENSE` at the repository root). Report and evaluation data: CC BY 4.0.
Fonts: IBM Plex (SIL Open Font License). Icons: Phosphor (MIT). All cases are fictitious.

---

## Hack Apertus challenge text (from the template)


Bring your own idea and build a working Apertus prototype that tackles a problem you care about — any domain, any use case. The project must be new, started within the hackathon period.

Submissions must use the Apertus model family.
For Track 2 this means that submitted solutions must be built with Apertus. Other open-weights models can be used to support development, e.g. as automatic judges during evaluation. Their role must be clearly described in the submission report.

💬 In case you have questions, join the conversation on [Discord](https://discord.gg/hack-apertus) or send an email to “hello@hackapertus.ch”

---

### 🔧 Resources & Tools

Check our resources & tools page for detailed information:
https://hackapertus.notion.site/resources-tools

| Models           | URL                                      |
|------------------|------------------------------------------|
| Apertus v1.5 8B  | [huggingface.co/swiss-ai/Apertus-v1.5-8B](https://huggingface.co/swiss-ai/Apertus-v1.5-8B)  |
| Apertus v1.5 70B | [huggingface.co/swiss-ai/Apertus-v1.5-70B](https://huggingface.co/swiss-ai/Apertus-v1.5-70B) |


### Target architecture (mandatory)

Whatever you build in Track 2B must be deployable in one of these three architectures:

- **a) On-premise** — on the organisation's own infrastructure, under its own administration.
- **b) Air-gapped** — with no external network connection at runtime.
- **c) Sovereign Swiss cloud** — on a cloud platform operated in Switzerland, under Swiss jurisdiction, with Swiss data residency.

---

### Data

The `data/` directory must not exceed 100 MB.

---

### 📦 Submission Requirements & Deliverables

❗️ Submissions are not handled on Devpost but via this URL only:
http://hackapertus.ch/online-hack/submissions

The submission must: 
1. follow the template repo and include all prerequisite files and definitions
2. follow the specified input/output formats
3. run in a Docker container, launched with `make run` from the root of the project
4. run end-to-end when judges try to run it

### Git repo (URL)
- Create your repo from this template (**Use this template**) and work in the `track_2b/` challenge directory. Delete the other track challenge directories.
- Keep `track_2b/` as it is: don't rename it or move its files.
- Set the repo to PUBLIC (Settings --> Collaborators --> Manage Visibility)
- Submit the URL of YOUR Git repo.

### Technical Report (pdf)
- Update [technical_report.md](technical_report.md) in this repository with all the details for your submission.
- Upload a pdf of your technical report to this directory, named as `TeamName_Report.pdf`.
- Format: pdf, max. 6 pages
- Submit the pdf of the technical report.

### Demo video (URL)
- Max. 2 min demo video of your prototype

### Dataset (URL) - optional, depending on your project
Submitted datasets must comply with our guidelines for responsibly sourced datasets.

- Create a user account on Hugging Face
- Clone our dataset template on Hugging Face: https://huggingface.co/datasets/HackApertus/online_hack_template
- Complete the dataset card with all required information
- Upload your dataset. It should consist of the following components:
    - evaluation dataset (i.e. individual test cases)
    - model response dataset (i.e. the model response to each test case)
    - metadata file (i.e. additional information about each test case; where relevant, this file must contain instance-level licensing information) 
- Make sure your dataset access control is set to PUBLIC
- Provide the URL of _your_ data set


---

### ⚖️ Judging Criteria

1. Purposeful use of AI
2. Technical rigour
3. Value, cost & scalability
4. Sovereign deployability
5. Implementation feasibility

Judges use a Scale 0–5 per dimension.

---

### Support

**Licensing requirements**
Please check our Terms & Conditions (6. What you build is open source):
https://hackapertus.ch/terms-and-conditions

### FAQ
💡 https://hackapertus.ch/faq

### Contact
💬 In case you have questions, join the conversation on Discord or send an email to “hello@hackapertus.ch”
