# Jev (TypeSafe AI)



Nový typ modelu — "System One Model": negeneruje text, ale vrací typované rozhodnutí
v jednom paralelním forward passu (ne token po tokenu). Trénovaný metodou **RLCD**
(Reinforcement Learning for Calibrated Decisions) — optimalizuje kalibrované
pravděpodobnosti na strukturovaných rozhodnutích, ne text preferovaný lidmi (na
rozdíl od RLHF/RLVR).



Založeno Diogem Almeidou (dřív OpenAI, InstructGPT). Oznámeno 15. 9. 2026,
early access od 16. 9. 2026.



## RLCD — typy odpovědí



- **choice** — výběr z definovaných možností
- **score** — skóre / ordinální hodnocení
- **noul** — ano/ne pravděpodobnost



## Dostupnost



- Proprietární, cloud-only, zatím žádné otevřené váhy ani self-hosted verze.
- Early access / waitlist: https://typesafe.ai/ (stav k 2026/09/19: na pozvánky)
- Konzole: https://console.typesafe.ai/login
- Nově dostupné i přes Vercel AI Gateway (hostovaně).



## Open-source repliky principu



Komunita už princip (non-autoregresivní, typované rozhodnutí v jednom forward
passu místo generování textu) replikuje open-source — menší modely (řádově
stovky milionů parametrů, ne frontier-scale), takže přesnost/kalibrace nebude
na úrovni Jevu, ale princip "RLCD + jeden forward pass" jde lokálně vyzkoušet
hned teď:



- **OpenJev / Verdict** — https://github.com/Heman10x-NGU/Verdict-open-jev

&#x20; Model na HF: `heman10x/rlcd-modernbert-151m`. Postaveno na ModernBERT

&#x20; (151M parametrů, báze `knowledgator/gliclass-modern-base-v2.0`), 25

&#x20; kandidátních slotů, vyhodnocuje všechny možnosti najednou (<35 ms latence).

&#x20; Stáhnutelné a spustitelné lokálně přes `transformers`.



- **Laya** (`pip install laya`) — podobný koncept, model `convaiinnovations/laya`

&#x20; na Hugging Face, ~33–38 ms na GPU, typované otázky (choice/score/bool) nad

&#x20; libovolným stavem (text, JSON, e-mail...).

