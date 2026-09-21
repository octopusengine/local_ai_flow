# laya evaluation, run 2: nine English tickets

Model **laya `multilingual`** on CPU, driven by `cli_laya.py --batch`, questions from `question.json` (the original wording, not `question_v2.json`).

## Setup and assumptions

- **Input:** nine English tickets (`ticket1.md` to `ticket9.md`). The run was made on the `data` folder; I assume the tickets from `data_en` were copied there. Two things support this: the folder held nine files, and the results for tickets 1 to 3 differ from the previous Czech run (for example ticket 1 `churn_risk` went from 0.028 to 0.892).
- **Ground truth:** my own labels, assigned when I wrote the tickets, not an external benchmark. Urgency is on the model's scale: 0 = not urgent, 1 = soon, 2 = critical.
- **Sample size:** nine tickets. Every percentage below is illustrative, not statistically meaningful.
- **Thresholds:** `churn_risk` is judged at 0.5. Department is judged by the top choice.

## Summary

| Question | Measure | Result | Verdict |
|---|---|---|---|
| `department` | top-choice accuracy | **6 / 9 (67 %)** | Decent; errors come with low confidence |
| `urgency` | rank correlation with my labels (Spearman) | **0.63**; 22 of 27 differently-labelled pairs ordered correctly (81 %) | Weak but real ordering signal |
| `urgency` | mean absolute error (0-2 scale) | **0.69**, versus 0.67 for always answering 1 | Values are compressed and not usable as absolute levels |
| `churn_risk` | accuracy at 0.5 | **7 / 9 (78 %)**; precision 2/3, recall 2/3 | Reasonable; one false alarm, one miss |
| `churn_risk` | ranking quality (AUROC) | **0.94** (17 of 18 positive/negative pairs) | Good ranking, threshold is the weak spot |
| speed | answer time per ticket | median **0.61 s**, range 0.44 to 1.13 s | Fast on CPU, grows with text length |
| speed | model load | **31.2 s** once per run | Dominates a small batch |

Overall: laya is fast and useful as a **ranker** (which ticket is more urgent, which is more likely to churn) and for **department** choice, but its absolute numbers should not be taken at face value.

## Per-ticket results

`exp` is my label, `pred` is the model's output. A tick marks agreement (department: same label; churn: same side of 0.5).

| # | Ticket | Department exp / pred (confidence) | Urgency exp / pred | Churn exp / pred |
|---|---|---|---|---|
| 1 | Double charge, threatens to cancel | billing / billing (1.00) ✅ | 2 / 1.49 | yes / 0.892 ✅ |
| 2 | Admin login fails (HTTP 500) | technical / technical (0.98) ✅ | 2 / 1.51 | no / 0.000 ✅ |
| 3 | Pricing for eight branches | sales / **billing** (0.26) ❌ | 0 / 1.31 | no / **0.644** ❌ |
| 4 | Copies of last year's invoices | billing / billing (1.00) ✅ | 0 / 1.12 | no / 0.009 ✅ |
| 5 | Wrong date format in CSV export | technical / technical (0.49) ✅ | 1 / 1.50 | no / 0.000 ✅ |
| 6 | Thanks and a feature idea | other / **technical** (0.48) ❌ | 0 / 1.08 | no / 0.013 ✅ |
| 7 | 25 % price increase, looking at other providers | billing / billing (1.00) ✅ | 1 / 1.24 | yes / **0.104** ❌ |
| 8 | Third outage, threatens to terminate | technical / technical (0.62) ✅ | 2 / 1.29 | yes / 0.770 ✅ |
| 9 | Upgrade to a bigger plan | sales / **other** (0.09) ❌ | 1 / 1.27 | no / 0.029 ✅ |

## Department

- **6 of 9 correct.** The three errors are tickets 3, 6 and 9.
- **`sales` was never predicted.** Both sales tickets went elsewhere (billing and other). The `sales` description in `question.json` ("pricing, new contracts") overlaps with billing, and "other: everything else" gives the model little to match against. Both are candidates for the more specific wording in `question_v2.json`.
- **Confidence is informative here.** The wrong answers have confidence 0.26, 0.48 and 0.09. The correct answers have 1.00, 1.00, 1.00, 0.98, 0.62 and 0.49. A gate at 0.6 would auto-accept five tickets (all correct) and send four to a human (three wrong, one correct). That threshold was chosen after seeing the data, so treat it as an illustration, not a setting to trust.

## Urgency

- **The scale is compressed.** All predictions fall between 1.08 and 1.51, a span of 0.43 on a 0-2 scale. Nothing was predicted as clearly "not urgent" or clearly "critical".
- **The order is mostly right anyway.** Mean prediction by my label: not urgent 1.17, soon 1.34, critical 1.43. In 22 of 27 pairs where my labels differ, the more urgent ticket got the higher score.
- **Absolute error is no better than a constant.** Mean absolute error 0.69 against 0.67 for always answering 1. Use urgency to sort a queue, not to decide whether something is critical.
- **Correction to my earlier reading.** After the three Czech tickets I said the model barely distinguished urgency. With nine tickets there is a modest ordering signal; the earlier sample was simply too small and all three of those tickets scored high (1.78 to 1.87).

## Churn risk

- **Hits:** tickets 1 (0.892) and 8 (0.770), both with explicit threats. Five tickets with no threat scored below 0.03.
- **False alarm, ticket 3 (0.644).** This is a prospective customer who says they are "considering switching to your service" and mentions that their current supplier's contract ends. The model appears to react to switching language regardless of direction. In fairness, my ticket contains that wording, so this is partly a test-design weakness. A question that names the direction explicitly (as `question_v2.json` does, "cancel the plan, terminate the contract or switch to another provider" applied to the customer's plan with us) may help.
- **Miss, ticket 7 (0.104).** The threat is soft ("looking at other providers", no explicit cancellation). The model ranked it above the clean negatives but far below 0.5.
- **Ranking is good (AUROC 0.94).** The only mis-ordered pair set is ticket 7 against ticket 3. Most of the error is the threshold, not the ordering.

## Czech versus English (tickets 1 to 3)

The English tickets are close translations, not word-for-word copies (ticket 3 in particular differs in details), so this comparison is approximate.

| Ticket | Czech run | English run |
|---|---|---|
| 1, double charge | billing 1.00, urgency 1.80, churn **0.028** ❌ | billing 1.00, urgency 1.49, churn **0.892** ✅ |
| 2, login failure | technical 0.98, urgency 1.87, churn 0.011 ✅ | technical 0.98, urgency 1.51, churn 0.000 ✅ |
| 3, pricing inquiry | sales 0.96 ✅, urgency 1.78, churn 0.003 ✅ | billing 0.26 ❌, urgency 1.31, churn 0.644 ❌ |

Mixed picture: English fixed the missed churn threat on ticket 1 but lost the correct `sales` label and produced a false churn alarm on ticket 3. Three tickets cannot say which language is better. English urgency values are lower and less uniform than the Czech ones.

## Speed

| Ticket | Words | Answer time |
|---|---|---|
| 1 | 24 | 0.44 s |
| 2 | 52 | 0.57 s |
| 4 | 51 | 0.61 s |
| 5 | 59 | 0.59 s |
| 6 | 55 | 0.58 s |
| 7 | 71 | 0.62 s |
| 8 | 72 | 0.71 s |
| 9 | 60 | 0.66 s |
| 3 | 154 | 1.13 s |

- Total answer time 5.91 s for nine tickets: mean 0.66 s, median 0.61 s.
- Time grows with length (Spearman 0.88 between word count and time). Tickets of 50 to 75 words all land between 0.57 and 0.71 s; the 154-word ticket takes about twice as long.
- **No warm-up penalty** is visible: the first ticket was the fastest.
- **Model load took 31.2 s** (31.3 s in the previous run). I had guessed a repeat run might load faster from the operating system cache; it did not. For small batches the load dominates: 37.1 s for the whole run against 5.9 s of actual answering.

## Caveats

- Nine tickets and my own labels: one flipped ticket moves accuracy by 11 points.
- Tickets 3 and 7 are deliberately or accidentally ambiguous, so part of the error is in the test, not only in the model.
- `laya-multilingual` ships without fitted calibration temperatures, so probabilities such as 1.00 or 0.000 are overconfident; they are best read as scores.
- Timings come from one CPU machine and a single run.

## Suggested next steps

1. Run the same tickets with `question_v2.json` (`python cli_laya.py -b -q question_v2.json`) and compare department, ticket 3 churn and the urgency spread against this table.
2. Store the expected labels in a file and let the CLI compute these metrics automatically, so each new run gives a scorecard instead of a manual comparison.
3. If accuracy is still not enough, the laya project provides a fine-tuning notebook; by its own documentation, fine-tuning on domain data is where most of the gain comes from.
