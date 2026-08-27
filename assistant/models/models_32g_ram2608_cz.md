# Srovnání: Gemma 4 26B A4B vs. Qwen3.8 27B

Aktualizováno: 27. 8. 2026. Srovnání se vztahuje k lokálně staženým Ollama tagům a k jejich veřejným upstream modelům. Nejde o vlastní benchmark na stejném hardwaru; výkon v token/s proto nelze z těchto údajů přímo vyvozovat.

## Identifikace lokálních modelů

| Lokální tag | Digest | Lokální výpis | Veřejný tag / aktuální velikost v Ollama | Kvantizace | Kontext a vstup |
| --- | --- | ---: | --- | --- | --- |
| `gemma4:26b` | `08ae7ec1744b` | 18 GB | [19 GB](https://ollama.com/library/gemma4:26b) | Q4_K_M | 256k; text + obraz |
| `qwen3.8:latest` | `22130167c4c2` | 17 GB | [18 GB](https://ollama.com/library/qwen3.8:latest) | Q4_K_M | 256k; text + obraz |

Rozdíl 1 GB proti místnímu výpisu pravděpodobně vznikl aktualizací manifestu/tagu v registru. Pro reprodukovatelnost je rozhodující digest, nikoli alias `latest`.

Oba modely jsou licencované pod Apache-2.0. U obou se skutečná paměťová potřeba zvyšuje s délkou kontextu kvůli KV cache; 18–19 GB je velikost souboru modelu, ne bezpečný požadavek na RAM/VRAM pro plných 256k tokenů.

## Rychlý výsledek

**Qwen3.8:latest je vhodnější výchozí volba pro programování, nástroje a dlouhé více-krokové agentní úlohy.** Je to hustý 27,3B model, má velmi silné komunitní přijetí a explicitní řízení hloubky uvažování.

**Gemma4:26b vyniká efektivitou MoE, prací s textem/obrazem, vícejazyčností a věcně laděnými odpověďmi.** Aktivuje jen asi 3,8B parametrů na token, přesto má znalostní kapacitu 25,2B modelu. Pro běžnou lokální interakci tak může být citelně svižnější, ale v agentním tool-callingu je komunitní zkušenost méně jednotná.

## Technické srovnání

| Vlastnost | Gemma 4 26B A4B | Qwen3.8 27B |
| --- | --- | --- |
| Architektura | MoE: 25,2B celkem, 3,8B aktivních/token; 8 z 128 expertů + 1 sdílený | hustý (dense) model, 27,3B parametrů |
| Kontext | 256k tokenů | 256k tokenů |
| Multimodalita v tomto tagu | text + obraz, výstup text | text + obraz, výstup text; upstream uvádí i porozumění videu |
| Nativní schopnosti | thinking, tools/function calling, systémová zpráva | thinking, tools, uchování reasoning v historii, řízení `reasoning_effort` |
| Aktuální veřejný artefakt v Ollama | 19 GB Q4_K_M + 573M BF16 CLIP projektor | 18 GB Q4_K_M + 461M BF16 CLIP projektor |
| Licence | Apache-2.0 | Apache-2.0 |

Zdroj technických údajů: [Ollama – Gemma4:26b](https://ollama.com/library/gemma4:26b), [Ollama – Qwen3.8](https://ollama.com/library/qwen3.8:latest), [model card Gemma](https://huggingface.co/google/gemma-4-26B-A4B-it) a [model card Qwen](https://huggingface.co/Qwen/Qwen3.8-27B).

## Gemma4:26b

### Kdy ji použít

- Vysvětlující chat, shrnutí, rešerše nad vlastním kontextem, psaní a překlady. Gemma 4 podporuje přes 140 jazyků.
- Porozumění obrázkům, OCR, dokumentům, grafům a UI screenshotům; pro malý text je vhodné zvýšit vizuální tokenový rozpočet.
- Úlohy, kde pomůže kombinace velké znalostní kapacity a nižšího počtu aktivních parametrů: dlouhé dokumenty, věda, studium jazyků a obecná práce.
- Reasoning a kódování jsou silné stránky, ale při autonomním agentovi je vhodné nejprve ověřit tool calling na vlastním stacku.

Oficiální výsledky pro variantu 26B A4B: MMLU Pro 82,6 %, AIME 2026 88,3 %, LiveCodeBench v6 77,1 %, GPQA Diamond 82,3 % a MMMU Pro 73,8 %. Jsou to výsledky výrobce, proto je nelze číst jako neutrální přímé srovnání s Qwenem. [Tabulka Ollama](https://ollama.com/library/gemma4:26b).

### Doporučené nastavení

| Cíl | Nastavení |
| --- | --- |
| Výchozí sampling | `temperature: 1.0`, `top_p: 0.95`, `top_k: 64` |
| Náročné uvažování | Do začátku system promptu vložit `<|think|>`; omezit výstup rozumným `num_predict` podle úlohy. |
| Rychlá přímá odpověď | Token `<|think|>` nepřidávat. U variant 26B/31B se mohou objevit prázdné značky thought bloku; klient je má skrýt/parzovat. |
| Více kol | Do dalšího kola vracet jen finální odpověď, ne předchozí interní thought blok. |
| Obrázky | Vstupní obraz vložit před text. Pro klasifikaci/captioning volit nižší rozpočet (70–280 obrazových tokenů), pro OCR a drobný text vyšší (560–1120). |

Ollama již obsluhuje chat template. Praktický start je `ollama run gemma4:26b`; parametrické hodnoty lze poslat v poli `options` API. Oficiální pokyny k thinkingu, historii a obrazovým tokenům jsou v [Ollama kartě](https://ollama.com/library/gemma4:26b) a [Hugging Face kartě](https://huggingface.co/google/gemma-4-26B-A4B-it).

### Komunitní hodnocení a slabiny

Model je etablovaný: instruction checkpoint má na Hugging Face přibližně 1,44 tis. likes a 61 příspěvků v komunitě (stav při zpracování). V LocalLLaMA se opakují pochvaly za němčinu/překlady, vědecké dotazy, obraz a schopnost držet dlouhý kontext; současně uživatelé často hodnotí Qwen jako silnější pro agentní kódování. Jde o anekdotické zkušenosti, nikoli kontrolovaný benchmark: [jazyk a věda](https://www.reddit.com/r/LocalLLaMA/comments/1ub4ods/gemma_4_26b_a4b_is_genuinely_the_best_model_i/), [dlouhý kontext a možné smyčky](https://www.reddit.com/r/LocalLLaMA/comments/1sihwo8/gemma_4_26b_a4b_is_still_fully_capable_at/), [praktické srovnání s Qwenem](https://www.reddit.com/r/LocalLLaMA/comments/1v95tka/appreciation_for_gemma_4_26b_a4b/).

Známé praktické slabiny:

- U dlouhých výčtů a velkého kontextu se mohou objevit opakovací/thinking smyčky. V komunitě se jako praktická mitigace objevuje nižší teplota a `repeat_penalty` zhruba 1,17–1,18, ale nejde o oficiální univerzální nastavení.
- U složitých vícekrokových tool-callů může model naplánovat postup a nedokončit všechny volané kroky. Záleží též na runtime a chat template.
- MoE snižuje výpočet na token, ale všechny váhy musí být stále v paměti; neznamená to 4GB model.

## Qwen3.8:latest

### Kdy jej použít

- Programování, opravy repozitáře, použití nástrojů a agentní workflow s opakovanou zpětnou vazbou z prostředí.
- Dlouhé více-krokové úlohy, kde je užitečné přenést stav uvažování mezi tahy (`preserve_thinking`).
- Výzkum, profesionální úlohy a práci s obrázky/videem; výrobce ho cílí na právě tyto oblasti.
- Rychlý chat bez dlouhého reasoning chainu: přepnout do non-thinking/instruct režimu.

Model je novější než Gemma 4, proto je kvalitativní obraz z nezávislé komunity zatím méně ustálený. Oficiální karta jej popisuje jako dosud nejschopnější otevřenou generaci Qwen a uvádí zlepšení v kódu, researchi a dlouhých agentech; tuto formulaci beru jako tvrzení výrobce, ne jako nezávislý verdikt. [Model card](https://huggingface.co/Qwen/Qwen3.8-27B).

### Doporučené nastavení

| Režim | Doporučení výrobce |
| --- | --- |
| Thinking | `temperature: 1.0`, `top_p: 0.95`, `top_k: 20`, `min_p: 0`, `presence_penalty: 0`, `repetition_penalty: 1.0` |
| Instruct / bez thinkingu | `temperature: 0.7`, `top_p: 0.80`, `top_k: 20`, `min_p: 0`, `presence_penalty: 1.5`, `repetition_penalty: 1.0` |
| Hloubka reasoning | `reasoning_effort`: `xhigh` (výchozí; složité úlohy), `medium` (vyvážené), `low` (rychlost/cena) |
| Více kol | `preserve_thinking: true` je výchozí a zlepšuje návaznost; pro běžný chat jej lze vypnout, aby historie nerostla zbytečně rychle. |

V modelovém runtime, který podporuje příslušný chat template, je thinking výchozí. Přepnutí do přímého režimu je `enable_thinking: false`; zachování reasoning historie je `preserve_thinking`. Ollama tag má pro spekulativní generování nastaveno `draft_num_predict: 4`, což může zrychlit dekódování, ale reálný efekt závisí na GPU/CPU a délce kontextu. Kompletní doporučení: [Qwen model card – API a best practices](https://huggingface.co/Qwen/Qwen3.8-27B-FP8#api-usage).

### Komunitní hodnocení a slabiny

Signál zájmu je mimořádně silný, ale velmi čerstvý: oficiální checkpoint měl při zpracování přibližně 13 tis. likes a 177 komunitních příspěvků na Hugging Face; Ollama tag byl publikován zhruba před týdnem. Shrnutí prvních zkušeností LocalLLaMA/LocalLLM jej hodnotí hlavně jako výrazný posun pro lokální agentní kódování a spolehlivost tool-callů, zároveň ale upozorňuje, že `xhigh` může generovat zbytečně mnoho thinking tokenů. [Komunitní souhrn](https://www.reddit.com/r/LocalLLM/comments/1vvu1uj/qwen3827b_one_week_later_the_rlocalllama/).

Slabiny a rizika:

- Výchozí `xhigh` reasoning zvyšuje latenci i spotřebu tokenů. Pro rutinní úlohy začít na `medium`, pro jednoduchý chat na `low` nebo bez thinkingu.
- Zachování všech thought bloků dává smysl u agentů, ale při dlouhém konverzačním chatu rychle spotřebovává kontext; pro takový chat ho vypnout.
- Vyšší `presence_penalty` umí potlačit opakování, ale výrobce upozorňuje na možné mísení jazyků a malé snížení kvality.
- Výsledky prvních komunitních testů jsou ovlivněné kvantizací, chat template a konkrétním backendem; nelze z nich činit univerzální závěr o token/s ani přesnosti.

## Doporučení pro stroj s 32 GB RAM

Oba Q4_K_M modely se podle velikosti vah do 32 GB RAM vejdou, ale plných 256k tokenů není realistický cíl bez výrazné rezervy (zejména s GPU offloadem a dalšími procesy). Začněte na 16–32k kontextu, sledujte rezidentní paměť a poté limit navyšujte. Pokud máte 16GB GPU, obvykle dává smysl offloadovat co nejvíce vrstev a nechat RAM pro váhy/KV cache; konkrétní hranici určí backend, přesnost KV cache a obrazové vstupy.

| Potřeba | Doporučený model | Proč |
| --- | --- | --- |
| Lokální coding agent, nástroje, plán → akce → kontrola | **Qwen3.8** | Silnější komunitní signál pro agentní kódování, explicitní řízení reasoning depth a navazování myšlenek. |
| Překlad, psaní, jazyková výuka, vědní vysvětlení | **Gemma4** | Přesvědčivá komunitní zkušenost s vícejazyčností a odbornějším textem; výpočetně úsporné MoE. |
| OCR, dokumenty, grafy a screenshoty | **Gemma4** jako první pokus | Silné oficiální vision výsledky a nastavitelný obrazový tokenový rozpočet. Qwen je dobrá alternativa, zvlášť když na výsledek navazuje agentní akce. |
| Nejvyšší spolehlivost více-krokového řešení | **Qwen3.8** | Použít thinking + `medium` až `xhigh` podle dopadu chyby; dát modelu dostatek výstupních tokenů. |
| Nízká latence při zachování kvality | **Gemma4** | MoE aktivuje jen 3,8B parametrů/token, ale ověřit na vlastním hardwaru – paměťová stopa zůstává velká. |

Nejrozumnější provozní rozdělení je mít oba modely: Gemmu jako rychlou kvalitní multimodální a vícejazyčnou volbu, Qwen jako specializovanou volbu pro kód, nástroje a náročné agenty. Pro konkrétní aplikaci je vhodné porovnat je na 10–20 skutečných promtech se stejnou kvantizací, kontextem, chat template a limitem výstupu.

## Použité zdroje

- [Ollama: Gemma4:26b](https://ollama.com/library/gemma4:26b) — digest, Q4_K_M, parametry, kontext, best practices a oficiální benchmarky.
- [Ollama: Qwen3.8:latest](https://ollama.com/library/qwen3.8:latest) — digest, Q4_K_M, kontext a schopnosti tagu.
- [Hugging Face: google/gemma-4-26B-A4B-it](https://huggingface.co/google/gemma-4-26B-A4B-it) — architektura, licence, možnosti a komunitní metriky.
- [Hugging Face: Qwen/Qwen3.8-27B](https://huggingface.co/Qwen/Qwen3.8-27B) a [FP8 model card](https://huggingface.co/Qwen/Qwen3.8-27B-FP8) — režimy uvažování, sampling a `reasoning_effort`.
- [Google DeepMind: Gemma 4](https://deepmind.google/models/gemma/gemma-4/) — kontext rodiny a výrobcem zveřejněné Arena Elo.
- Komunitní zkušenosti jsou uvedeny přímo u jednotlivých modelů; mají nižší důkazní váhu než oficiální karty a nejsou náhradou vlastního testu.
