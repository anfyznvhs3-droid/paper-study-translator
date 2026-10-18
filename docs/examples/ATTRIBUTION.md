# Public example sources and reproduction

The README figures are generated outputs, not mock translations. The application
renders the recorded Codex translations in `translation-map.jsonl` through its
existing offline/agent PDF path, including image OCR and final DUAL composition.
This is a content example, not a live Gemini or agent-CLI benchmark.

## Sources and licenses

| Material | Source | License / modifications |
| --- | --- | --- |
| Paper excerpt | Ouyang, Chu, Xin & Ma (2025), [PDFMathTranslate: Scientific Document Translation Preserving Layouts](https://aclanthology.org/2025.emnlp-demos.71/), p. 918 | CC BY 4.0; first page extracted, translated into Korean and shown beside the original; abstract crops enlarged |
| Penguin measurements | [palmerpenguins](https://github.com/allisonhorst/palmerpenguins), collected by Kristen Gorman and Palmer Station LTER; package by Allison Horst, Alison Hill and Kristen Gorman | CC0; 344 observations, two missing measurement pairs omitted, 342 plotted |
| Chart design | This repository, `render.py` | AGPL-3.0; chart generated from the attributed data and embedded as a raster image for OCR |
| App screen | Paper Study Translator v0.1.0 production frontend | Repository license; captured with isolated mock IPC, no personal data |

The paper's original and translated excerpts in the images, sample PDF and
translation map are provided under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
The [ACL Anthology copyright policy](https://aclanthology.org/faq/copyright/)
covers ACL material published in or after 2016. The sample is an unofficial
translation, not reviewed or endorsed by the paper's authors.

Dataset snapshot: [`8957207b78d6ccd1b4654a9dd9c9041b657478ab`](https://github.com/allisonhorst/palmerpenguins/tree/8957207b78d6ccd1b4654a9dd9c9041b657478ab).
See the dataset's [CC0 license](https://github.com/allisonhorst/palmerpenguins/blob/8957207b78d6ccd1b4654a9dd9c9041b657478ab/LICENSE.md).

## Reproduce the PDFs and images

Use the source environment described in [DEVELOPMENT.md](../DEVELOPMENT.md),
English Tesseract and the font/model from the Windows distribution.
The documentation renderer additionally uses `matplotlib==3.10.8`.

From the repository root:

```powershell
python -m pip install matplotlib==3.10.8
python docs/examples/render.py --assets release/PaperStudyTranslator-0.1.0-windows-x64/runtime/assets
```

The script creates a fresh `.release-work/readme-demo` directory. To run again,
select another new directory with `--work .release-work/readme-demo-2`.
It downloads the two public inputs, verifies their SHA-256 hashes, then blocks
network connections before loading the application renderer. API keys are not
required. Settings and caches use an isolated profile in this work directory.

Outputs:

- `PDF/paper-dual-example.pdf` — one real paper page, English on the left, Korean on the right.
- `PDF/ocr-chart-dual-example.pdf` — raster chart and its actual OCR translation.
- `images/` — unretouched renders of those PDFs and magnified abstract crops.
- `internal/`, `profile/`, `cache/`, `evidence.json` — local reproduction evidence, excluded from Git.

The delivery `PDF` directory contains only PDFs. Source PDFs and caches are not
committed. The two public sample PDFs are separate release assets, outside the
Windows application ZIP.

The committed `docs/assets/app-start.png` is produced by the existing
`scripts/verify-entry-ui.py` frontend capture, not by the PDF renderer.

## Input integrity

| Input | SHA-256 |
| --- | --- |
| `2025.emnlp-demos.71.pdf` | `ee11e6a2301cd980d4d7663d2ed8e4f85df414fe1ea775bc5fbb8cf660c6b187` |
| `penguins.csv` | `f204db2c753b0937caac3cb35258562c14f073e4bbc76be24b4c51ce22767a93` |

The script verifies the two input hashes, the dataset counts, selected Korean
labels and percentages, and the unchanged scatter-plot pixels. Font/layout/OCR
library versions can affect rendering. See [SHOWCASE.md](../SHOWCASE.md) for the
observed output and unresolved review candidates; these examples are not a
general accuracy score.
