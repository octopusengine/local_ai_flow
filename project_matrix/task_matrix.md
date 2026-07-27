# Task Matrix Evaluation

## Task

**Prompt:** What is artificial intelligence?

**Instruction:** Answer in English using exactly five words. Output only the answer, with no explanation, labels, or extra text.

**Source:** `task_answers_model_260727_1136.txt` (30 runs: 2 models × 3 temperatures × 5 seeds).

## Evaluation method

The strict format check counts whitespace-delimited words; punctuation does not affect the count. Relevance and wording are assessed manually.

## Summary

| Model | Runs | Exactly five words | On-topic answers | Main finding |
| --- | ---: | ---: | ---: | --- |
| `gemma4:latest` | 15 | 14 / 15 (93.3%) | 15 / 15 | Best constraint adherence, but many answers are terse fragments and repeatedly use filler words such as “now”. |
| `qwen3.5:latest` | 15 | 10 / 15 (66.7%) | 15 / 15 | Usually more natural and clearer, but its word-count compliance is less reliable, especially at temperature 0.5. |
| **Overall** | **30** | **24 / 30 (80.0%)** | **30 / 30** | All answers were English-only and contained no labels or explanations. |

## Format failures

| Model | Temperature | Seed | Answer | Word count | Issue |
| --- | ---: | ---: | --- | ---: | --- |
| `gemma4:latest` | 0.9 | 666 | Simulating human intelligence processes effectively now. | 6 | One word too many. |
| `qwen3.5:latest` | 0.5 | 1 | Self-learning computer program systems. | 4 | One word too few. |
| `qwen3.5:latest` | 0.5 | 21 | It simulates human thinking with computers. | 6 | One word too many. |
| `qwen3.5:latest` | 0.5 | 42 | It simulates human learning and reasoning. | 6 | One word too many. |
| `qwen3.5:latest` | 0.5 | 123 | It simulates human learning and reasoning. | 6 | One word too many. |
| `qwen3.5:latest` | 0.9 | 21 | AI mimics human thinking. | 4 | One word too few. |

## Quality observations

- `gemma4:latest` followed the five-word requirement almost perfectly at temperatures **0.1** and **0.5** (5/5 valid responses for each). Its wording was often less natural, for example “Machines mimicking human intelligence now.”
- `qwen3.5:latest` was fully compliant at temperature **0.1** (5/5 valid responses). Temperature **0.5** was the weakest setting (2/5 valid responses).
- The clearest compliant Qwen answer was: **“AI simulates human intelligence computationally.”** (`temp: 0.9`, `seed: 42`).
- Repeated outputs across different seeds are expected for this short, tightly constrained task. They indicate that the model has a strong preferred completion, not a runner error.

## Recommendation

Use `gemma4:latest` with `temp: 0.1` or `0.5` when exact five-word compliance is the priority. Use `qwen3.5:latest` with `temp: 0.1` when you prefer more natural phrasing while retaining full compliance in this sample.

For a larger benchmark, add an automatic word-count validator after each response. It can flag or retry only the rows that do not contain exactly five words.
