# Available slash commands

> This document is generated from [sc.json](sc.json); do not edit it directly. Czech version: [sc_cz.md](sc_cz.md).

## Conversation

- `/chat` – Continue the conversation naturally. Give the highest priority to the user's latest question. When relevant, use the immediately preceding assistant reply as the main conversational continuity. Treat older turns and attached sources only as supporting context; use them more broadly only when the user explicitly asks to work with the context, a source, or earlier discussion. Do not mention the reference context unless the user asks. Reply briefly and directly.

## Text transformation

- `/explain` – Explain any topic in simple terms.
- `/summarize` – Summarize a long text or article while preserving the important points.
- `/tldr` – Condense the supplied content to about 50 words. Preserve the essential point, key facts, and any important conclusion. By default use one coherent paragraph without prefacing text; follow a separately selected format modifier when it requests a different structure.
- `/wtf` – Explain the supplied content in plain, everyday language: what it is, what it does, why it matters, and the main catch or limitation. Assume the reader is new to the topic. By default use one short paragraph of about 60–90 words; avoid jargon, or explain it immediately. Follow a separately selected format modifier when it requests a different structure.
- `/translate` – Translate the text into the requested language while preserving its meaning and format.
- `/rewrite` – Rewrite the content for the requested purpose, tone, or audience.
- `/grammar` – Fix grammar, spelling, and punctuation without changing the intended meaning.
- `/speechfix` – Correct only likely speech-recognition transcription errors, working conservatively. Choose a replacement only when it is strongly supported by phonetic or spelling similarity to the recognized word; use sentence context only as a secondary check. Never replace a word merely because another word makes the sentence more common or semantically smoother. Do not invent content, expand or alter acronyms, or replace plausible technical, product, foreign, or unknown terms. Preserve the intended wording, meaning, and content; do not add, remove, paraphrase, or make stylistic edits. If a word remains uncertain, leave it unchanged. Return only the corrected transcription.
- `/improve` – Improve clarity, readability, and flow while keeping the original intent.
- `/shorten` – Make the text shorter and more concise while preserving essential information.
- `/lengthen` – Expand the text with useful detail, explanation, or examples.
- `/about100` – Expand the text with useful detail, explanation, or examples.

## Analysis and explanation

- `/compare` – Compare two or more things using relevant criteria.
- `/contrast` – Show key differences, trade-offs, strengths, and weaknesses.
- `/principles` – Explain the key principles or ideas behind a topic.
- `/steps` – Break the task down into a clear step-by-step guide.
- `/howto` – Provide practical how-to instructions for accomplishing a goal.
- `/examples` – Give practical examples that make the topic concrete.
- `/analogy` – Explain the topic using helpful analogies.
- `/case` – Provide a realistic real-world use case or case study.
- `/research` – Research the topic deeply, distinguish facts from assumptions, and cite sources when available.
- `/critic` – Identify weaknesses, flaws, risks, and gaps in the supplied idea or text.
- `/decision` – Compare the supplied options using clear criteria, state trade-offs, and recommend the best option with a brief justification.

## Format modifiers

- `/bulletpoints` – Return the result as concise bullet points.
- `/list` – Return the result as a clear numbered list.
- `/table` – Convert the result or supplied data into a clear table.
- `/brief` – Give the shortest useful answer possible.
- `/md` – Format the answer as restrained Markdown when structure helps: short # or ## headings, bullet lists, **bold**, `inline code`, and --- separators. Do not add Markdown merely for decoration.
- `/json` – Return only valid JSON matching the requested structure, with no Markdown fences or explanatory text.
- `/diagram` – Create a clear Mermaid diagram for the requested process, structure, or relationships. Return only the Mermaid source.

## Documents and career

- `/template` – Create a reusable template for the requested purpose.
- `/email` – Write a professional email with a subject, greeting, body, and closing.
- `/coverletter` – Write a tailored cover letter for the supplied role and background.
- `/resume` – Create or improve a clear, role-focused resume.
- `/interview` – Create realistic interview questions and strong example answers.
- `/copywriter` – Write persuasive marketing copy for the specified audience and goal.
- `/seo` – Create search-optimized content without sacrificing accuracy and readability.
- `/viral` – Generate high-engagement content ideas suited to the requested platform and audience.

## Learning, ideation, and planning

- `/quiz` – Create a quiz with questions, answers, and optional explanations.
- `/flashcards` – Generate concise flashcards with a prompt on one side and an answer on the other.
- `/brainstorm` – Brainstorm diverse, practical ideas and group them by direction or priority.
- `/plan` – Create an actionable plan or roadmap with goals, steps, and milestones.
- `/strategy` – Analyze options through a long-term strategic lens, including trade-offs and risks.
- `/checklist` – Return a concise, actionable checklist with clear completion items.
- `/ceo` – Analyze the situation from a founder or CEO perspective, focusing on outcomes and priorities.

## Style and depth modifiers

- `/human` – Write naturally and humanly, avoiding formulaic or robotic phrasing.
- `/eli5` – Explain it like I am 5: use very simple words, short sentences, and a concrete example.
- `/eli12` – Explain it like I am 12: use clear everyday language, introduce necessary terms, and include a practical example.
- `/expert` – Give a specialist-level answer with precise terminology and justified detail.
- `/promptengineer` – Improve and optimize the supplied prompt for clarity, constraints, and reliable output.

## Medical

- `/doctor` – Respond as a medical specialist providing clear, evidence-based health information. Do not present a definitive diagnosis or replace an in-person clinical assessment. State relevant uncertainty and information limits, identify urgent red flags and when to seek immediate care, and ask concise follow-up questions when necessary. Do not invent sources.

## Software development

- `/html` – Create a complete, responsive HTML page for the requested purpose. Use semantic, accessible HTML and include only the CSS and JavaScript needed for the page to work.
- `/python` – Write a correct, readable Python program for the requested task. Include concise run instructions and handle relevant errors and edge cases.
- `/rust` – Write idiomatic, safe Rust code for the requested task. Include concise Cargo run instructions and handle relevant errors and edge cases.
- `/js` – Create one complete HTML document containing a simple JavaScript application in an inline <script> element. Do not use external dependencies. Return only the HTML source code.
- `/review` – Review the supplied code for correctness, readability, maintainability, and likely bugs. Prioritize findings and propose concrete fixes.
- `/refactor` – Refactor the supplied code to make it simpler, clearer, and easier to maintain without changing its intended behavior.
- `/debug` – Diagnose the supplied error or unexpected behavior, explain the likely root cause, and provide a concrete fix and verification steps.
- `/test` – Create focused automated tests for the supplied code, covering normal behavior, relevant edge cases, and error handling.
- `/security` – Assess the result for relevant security risks, unsafe input handling, exposed secrets, and missing validation; propose mitigations.
- `/sql` – Write a correct, readable SQL query or schema for the requested task. State required assumptions and avoid destructive statements unless explicitly requested.
- `/regex` – Create a regular expression for the requested pattern, explain its parts briefly, and provide matching and non-matching examples.
- `/api` – Design a practical API contract for the requested feature, including endpoints, request and response shapes, validation, and error cases.

## Scripts

- `/sh` – Write a complete, readable Bash script for Linux that solves the requested task. Use Bash features only when needed, handle relevant errors and edge cases, and return only the script source code.
- `/bat` – Write a complete, readable Windows Batch (.bat) script that solves the requested task. Use standard cmd.exe commands, handle relevant errors and edge cases, and return only the script source code.

## Image text extraction

- `/ocr` – Transcribe all visible text faithfully. Preserve reading order and meaningful structure. Do not translate, summarize, or add commentary; mark unreadable text as [unreadable].
- `/describe` – Describe faithfully what is visible in the image. Cover important objects, their relationships, layout, and any readable text; do not invent details.
