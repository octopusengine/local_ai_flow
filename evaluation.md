# Local AI Workflow Evaluation

## Summary

The `local_ai_flow` test with a real printed document was successful. The complete document workflow ran locally:

```text
photograph → OCR → translation → speech synthesis
```

Despite a low-quality photograph taken in dim light, OCR produced an almost flawless result. The translation preserved the full meaning of the source, although it would require linguistic and terminology editing before publication. The final two-minute MP3 was created successfully.

Overall practical assessment: **a very good and usable local prototype**.

## Test artifacts

- Reference text: [`project_bwp/real.txt`](project_bwp/real.txt)
- Document photograph: [`project_bwp/camera.png`](project_bwp/camera.png)
- OCR result: [`project_bwp/camera.txt`](project_bwp/camera.txt)
- Czech translation: [`project_bwp/translate.txt`](project_bwp/translate.txt)
- Synthesized speech: [`project_bwp/translate.mp3`](project_bwp/translate.mp3)
- Execution log: [`project_bwp/log.txt`](project_bwp/log.txt)

## Input photograph

The photograph has a resolution of 640 × 480 pixels and a size of approximately 378 kB. It was captured under unfavorable conditions:

- low illumination;
- weak contrast between the paper and text;
- slight blur;
- perspective distortion;
- uneven page lighting.

The entire English passage nevertheless remained readable to the OCR model. This is a substantially more difficult and realistic test input than a clean digital rendering of the PDF.

## OCR accuracy

OCR was performed by `deepseek-ocr:3b` with these parameters:

```json
{
  "temperature": 0.1,
  "num_predict": 4096
}
```

After normalizing the Markdown heading, whitespace, and line breaks, the following results were measured:

| Metric | Result |
| --- | ---: |
| Words in the reference | 269 |
| Words in the OCR output | 269 |
| Word-level edit distance | 1 |
| Word accuracy | 99.63% |
| Character-level edit distance | 1 |
| Character accuracy | 99.94% |

The only difference was an added hyphen:

```text
reference: nonreversible services
OCR:       non-reversible services
```

In this case, OCR used the more common and linguistically preferable spelling. No sentence, number, or meaningful part was omitted. The model also recognized the heading correctly and divided the text into logical paragraphs.

Practical OCR assessment: **almost 10/10**.

## Translation quality

The translation was produced by `translategemma:12b`. The output preserved every sentence and the main meaning of the source without obvious hallucinations or invented information.

Strengths:

- complete translation;
- preserved document structure;
- correct transfer of the main ideas;
- mostly natural and understandable Czech;
- suitable for quickly understanding the document.

Several places should be corrected before publication:

| Model output | Suggested correction |
| --- | --- |
| `nemohou vyhnout se mediaci sporů` | `nemohou se vyhnout zprostředkování sporů` |
| `Určitý procento` | `Určité procento` |
| `umožnil dvěma ochotným stranám transakce` | `umožnil dvěma ochotným stranám provádět transakce` |
| `kryptografické ověření` | more precisely, `kryptografický důkaz` |
| `upřímné uzly` | in Bitcoin terminology, preferably `poctivé uzly` |

The translation of `peer-to-peer distributed timestamp server` also lost some technical precision. The result is sufficient for general understanding, but professional or publishable text would benefit from human review.

Practical translation assessment: **approximately 7.5/10**.

## Speech synthesis

The translated text was successfully converted to `translate.mp3` using the Czech `jirka` voice.

Output parameters:

| Property | Value |
| --- | --- |
| Duration | 2 minutes 0.24 seconds |
| Format | MP3 |
| Channels | mono |
| Sample rate | 22,050 Hz |
| Bit rate | approximately 68 kb/s |
| File size | approximately 1.03 MB |

The log confirms successful synthesis and output-file creation. Listening quality was not part of this evaluation.

## Processing time

| Stage | Duration |
| --- | ---: |
| OCR evaluation | 64.4 seconds |
| Translation | 7 minutes 35 seconds |
| Speech synthesis | approximately 3 minutes |
| Complete practical workflow, including photography | approximately 14–15 minutes |

Translation was the slowest stage. Considering that it used a local model of approximately 8.1 GB, the processing time is acceptable for a prototype.

The setting:

```json
"ollama_timeout_seconds": 900
```

in `project.json` is not the intended duration of the complete workflow. It is the maximum timeout while waiting for an Ollama response. `runner.py` itself does not impose a time limit on subprocess steps.

## Privacy and security

The log confirms communication with local Ollama at `localhost`. OCR, translation, and speech synthesis ran locally, and no external cloud AI service was used during this test.

Benefits:

- the photograph and text do not need to leave the computer;
- working artifacts remain together in the project directory;
- individual stages are reproducible;
- the log records models, parameters, paths, and timings;
- the user retains direct control over inputs and outputs.

Local processing does not automatically mean encrypted storage. The photograph, OCR text, translation, audio, and complete prompt are stored as readable files, and some content is also recorded in `log.txt`. Security therefore still depends on system access controls and optional disk encryption.

## Logging quality

The `log.txt` file makes it easy to identify:

- the CLI tool used;
- model and parameters;
- input and output files;
- the beginning and end of individual stages;
- evaluation time;
- error states.

The supplied log documents these stages:

```text
camera → OCR → translate → speech
```

There is no separate `cli_mcp.py` block in this particular log. For a complete runner record, `runner.py` could also log the start, finish, elapsed time, and exit code of every step.

The log also contains ANSI terminal color sequences. They do not affect processing, but they reduce file readability and complicate machine processing. A future improvement should keep colored terminal output while writing clean text to the log.

## Overall assessment

| Area | Assessment |
| --- | ---: |
| Resilience to a poor-quality photograph | very good |
| OCR accuracy | excellent |
| Translation completeness | very good |
| Translation language quality | good, requires editing |
| Speech synthesis | technically successful |
| Reproducibility | very good |
| Privacy | very good on a properly secured computer |
| Speed | acceptable for a local prototype |

The project demonstrated that it can process a real, poorly photographed printed document from image capture through Czech spoken output without cloud AI. Nearly flawless OCR was the strongest result. The main opportunities for improvement are translation speed, specialist terminology, and more complete runner-level logging.

The result can be considered **a successful practical demonstration of a local, private, and reproducible AI workflow**.
