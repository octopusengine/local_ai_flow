# Kontextové okno, role, skills a commands v `cli_ollama.py`

Tato verze navazuje na `kontextove_okno_01_cz.md` a rozšiřuje ji o návrh slash commands pro opakované akce nad textem.

> Stav k 2026-09-05: níže jsou zachované návrhové příklady i popis
> Implementace 02. Autoritativní katalog je `assistant/commands/sc.json`;
> James jej zobrazuje přes Chat → `/cmd` a Setup → slash commands.
> Chatový kontext a agentní historie Cowork vznikají v James / AgentEngine,
> nikoli automatickým načítáním historie v `cli_ollama.py`.

## Co je kontextové okno

Kontextové okno je vše, co model v jednom requestu vidí a může zohlednit: systémové instrukce, uživatelský vstup, referenční podklady, historii zpráv, definice nástrojů, jejich výsledky a obrázky převedené na tokeny. Modelová šablona z Ollamy může přidat další interní tokeny.

Generační parametry (`temperature`, `seed`, `num_predict`, `num_ctx`, `repeat_penalty`, `think`) nejsou obsah kontextu. `num_ctx` pouze omezuje maximální velikost kontextového okna.

Současné CLI automaticky neposílá historii, log ani databázové záznamy. Předchozí výstup se do dalšího tasku dostane pouze explicitně: přes `--input`, `--context` nebo u specializovaných tasků přes `--in`.

## Současné requesty

| Typ tasku | Odesílaný obsah | Endpoint |
| --- | --- | --- |
| `prompt` | `prompt`, volitelně `system`, model, options, think | `/api/generate` |
| `translate` | jako `prompt`; prompt je obsah vstupního souboru | `/api/generate` |
| `ocr` | `prompt`, obrázek, volitelně `system`, model, options, think | `/api/generate` |
| `describe` | system message, pokud existuje, a user message s promptem a obrázkem | `/api/chat` |

## Vrstvy kontextu

```text
profile / role      kdo asistent stabilně je a jak se chová
skills              přenositelné pracovní postupy a schopnosti
task_rules          pravidla konkrétní akce a formátu výstupu
reference context   přiložené dokumenty, výstupy a později historie
user_input          aktuální otázka nebo data
```

`Profile` znamená stabilní roli rozšířenou o jazyk, styl a dlouhodobé zásady:

```md
Jsi trpělivý učitel pro českého studenta.
Vysvětluješ srozumitelně, po krocích a přiměřeně úrovni dotazu.
Nevymýšlíš si fakta; při nejistotě ji přiznáš.
```

Skill popisuje přenositelný způsob práce, nikoli nutně osobnost:

```md
# Skill: vysvětlování

U složitých témat začni krátkou odpovědí, pak vysvětli princip a použij malý příklad pouze tehdy, když pomůže porozumění.
```

Task rule je krátkodobé zadání:

```text
Vysvětli fotosyntézu nejvýše v pěti větách a nepoužívej Markdown.
```

## Implementované CLI vrstvy

```text
--input TEXT|FILE          alias původního --data; nahradí aktuální prompt
--rules TEXT|FILE          přidá běhová pravidla, lze opakovat
--replace-rules TEXT|FILE  nahradí tasková pravidla
--context FILE             přidá referenční podklad s jasnými značkami, lze opakovat
--profile ID               přidá assistant/profiles/ID.md, lze opakovat
--capability ID            přidá assistant/capabilities/ID.md, lze opakovat
--skill ID                 legacy lookup v capabilities, potom v profiles
--dry-run                  vypíše přesný JSON request bez volání Ollamy
```

`--data` zůstává kompatibilním aliasem `--input`. Původní `--instruction` zůstává kompatibilním aliasem `--replace-rules`.

Assety asistenta jsou nově roztříděné podle účelu:

```text
assistant/
  profiles/       stabilní role a persony
  capabilities/   znovupoužitelné postupy a odbornosti
  commands/       katalog slash commands (sc.json)
```

Staré taskové cesty `./skills/nazev.md` zůstávají v CLI podporované jako aliasy,
ale dodané tasky už používají `profile` nebo `capability`. `--skill` také
zůstává pro kompatibilitu: hledá nejdříve capability, potom profile.

```text
task profile(s) -> CLI profile(s) -> task capability(s) -> CLI capability(s)
-> task / replaced rules -> appended --rules
                                        = system

# Reference context
  [REFERENCE FILE: soubor-1.md]
  ... obsah souboru ...
  [END REFERENCE FILE]
  [REFERENCE FILE: soubor-2.md]
  ... obsah souboru ...
  [END REFERENCE FILE]
# Current input
  [INPUT]
  ... aktuální vstup ...
  [END INPUT]
                                        = prompt nebo user message s jednoznačnými hranicemi
```

Příklad:

```powershell
python cli_ollama.py --type task_explain12.json `
  --input question.txt `
  --context source_notes.txt `
  --profile teacher_cz `
  --rules "Odpověz nejvýše v pěti větách." `
  --dry-run
```

## Kompatibilita s dosavadními flow

Soubory `flows/flow*.txt` se nemění.

- `flow_voice_free.txt`, `flow_voice_sky.txt`, `flow_freestyle.txt` a `flow_base.txt` dál fungují: používají zachované `--data` a `--instruction`.
- `flow_cam_describe.txt`, `flow_bwp.txt` a `flow_ocr_test.json` nepoužívají nové volby; jejich současné flow je zachované.
- `flow_voice_holly_pivo.txt` a `flow_voice_cotoje12.txt` zachovávají chování, kdy `--instruction` nahradí pravidla tasku, ale profile zůstane před nimi.
- `flow_html_cz.txt` už dnes pomocí `--data` přepíše statický prompt z `task_html.json`. Není to nová nekompatibilita, ale při budoucí migraci je vhodné přesunout statické „vytvoř pouze HTML“ do taskových pravidel.

Záměrná změna pro případné vlastní image tasky: OCR a describe nyní odešlou jejich `instruction`, profile a capability do system kontextu. Dříve se u obrazových tasků ignorovaly. Dodané image tasky tato pole nemají.

## Slash commands: co jsou a kam patří

Následující položky nejsou profily. Jsou to slash commands: uživatelské zkratky pro výběr akce nebo předpřipraveného tasku.

```text
/explain, /summarize, /translate, /rewrite, /grammar, /improve
/shorten, /lengthen, /bulletpoints, /list, /table
/compare, /contrast, /principles, /steps, /examples, /analogy, /case
/template, /email, /coverletter, /resume, /interview
/quiz, /flashcards, /forecastorm, /plan
```

Command sám o sobě není další část kontextu. Je to volba, která se přeloží na kombinaci skills, task rules, výstupního formátu a případně parametrů modelu.

| Skupina | Commands | Cílová vrstva |
| --- | --- | --- |
| Textová transformace | `/summarize`, `/rewrite`, `/grammar`, `/improve`, `/shorten`, `/lengthen`, `/translate` | action/task preset + případný skill |
| Vysvětlení a analýza | `/explain`, `/compare`, `/contrast`, `/principles`, `/steps`, `/examples`, `/analogy`, `/case` | action/task preset; často skill učitele či analytika |
| Formát odpovědi | `/bulletpoints`, `/list`, `/table` | především `task_rules` |
| Dokumentové výstupy | `/template`, `/email`, `/coverletter`, `/resume`, `/interview` | task preset / šablona artefaktu + specializovaný skill |
| Výuka | `/quiz`, `/flashcards` | task preset + learning skill |
| Nápady a řízení práce | `/forecastorm`, `/plan` | task preset + brainstorming/planning skill |

### Příklad `/summarize`

```text
command: /summarize
skill: text-editor
task_rules:
  Shrň vstup do nejvýše pěti věcných bodů.
  Zachovej důležité výhrady a nejistoty.
input:
  obsah z --input
```

### Příklad `/email`

```text
command: /email
skill: professional-writing
task_rules:
  Vytvoř hotový e-mail: předmět, oslovení, tělo a zakončení.
  Zachovej jazyk vstupu a profesionální, přirozený tón.
input:
  požadavek a podklady z --input
```

### Kombinace profilu, commandu a formátu

```text
profile: teacher-cz
command: /explain
format modifier: /bulletpoints
input: "Jak funguje fotosyntéza?"
```

Význam je: „Vysvětli dané téma jako trpělivý český učitel a odpověz v bodech.“ `/explain` je akce, `teacher-cz` je stabilní role a `/bulletpoints` je formátovací pravidlo.

## Doporučené ukládání commandů

Nevytvářet 28 téměř stejných `task_*.json` souborů. Vhodnější je jeden katalog, například `commands_cz.json`, který command přeloží na reusable skills a pravidla:

```json
{
  "explain": {
    "kind": "action",
    "default_skills": ["explain-clearly"],
    "rules": "Vysvětli princip srozumitelně a věcně."
  },
  "bulletpoints": {
    "kind": "format_modifier",
    "rules": "Odpověď vrať jako stručný seznam odrážek."
  },
  "email": {
    "kind": "artifact",
    "default_skills": ["professional-writing"],
    "rules": "Vytvoř hotový e-mail včetně předmětu a oslovení."
  }
}
```

Budoucí zápis může vypadat takto:

```text
/profile teacher-cz
/explain /bulletpoints
--input question.txt
--context source_notes.txt
--rules "Bez Markdownu."
```

Názvy `/forecastorm` a `/rowto` je vhodné před zavedením upřesnit. První může znamenat `forecast` (předpověď/scénáře) nebo `brainstorm` (tvorba nápadů); druhý nemá z názvu jasný účel. Pro výběr role jsou srozumitelnější názvy `/profile` nebo `/role`.

## Implementace 02: jazykové slash commands

Slash commands jsou nyní dostupné přes jeden jazykový režim a opakovatelný
seznam commandů:

```text
--sc-cz | --sc-en | --sc-es    vybere jazyk command pravidel a jazyk odpovědi
--sc NAME             přidá command z assistant/commands/sc.json; lze opakovat
```

Příklad českého requestu:

```powershell
python cli_ollama.py --type task_base.json `
  --sc-cz `
  --sc summarize `
  --sc bulletpoints `
  --sc brief `
  --input article.txt `
  --dry-run
```

Do kontextu se nevkládají klíče `summarize`, `bulletpoints` ani `brief`.
CLI z nich načte česká pravidla z `assistant/commands/sc.json` a vloží je mezi task rules a
explicitní `--rules`. Na konec system kontextu přidá pravidlo „Odpovídej pouze
česky.“ Analogicky `--sc-en` vloží anglická pravidla a „Respond only in
English.“

`--sc-cz` nebo `--sc-en` bez `--sc` vybere interní výchozí klíč `explain`.
`explain` se do systemu nevkládá doslova; přidá se pouze jazykové pravidlo.
Bez jakékoliv volby `--sc*` zůstává dosavadní request beze změny.

### Skládání commandů

Je povolen jeden primární `action` nebo `artifact`, libovolný počet
`modifier` a nejvýše jeden `persona_modifier`.

```text
platné:
  --sc-cz --sc summarize --sc bulletpoints --sc brief
  --sc-cz --sc explain --sc examples --sc analogy
  --sc-en --sc email --sc human

neplatné:
  --sc-cz --sc summarize --sc email
  --sc-en --sc expert --sc ceo
```

Duplicitní commandy se vyhodnotí jen jednou. Nejasná kombinace skončí chybou;
CLI nikdy tiše nevybere jednu ze vzájemně si odporujících akcí.

### Jazyky a překlad

`--sc-cz` a `--sc-en` nejsou automatický překlad vstupu. Určují pracovní jazyk
pravidel a požadovaný jazyk výsledku. Překlad zůstává viditelným mezikrokem ve
flow:

```text
český vstup -> task_translate.json --direction c2a -> --sc-en pracovní task -> anglický výstup
anglický vstup -> task_translate.json --direction e2c -> --sc-cz pracovní task -> český výstup
```

Je-li potřeba dodat výsledek v jiném jazyce než pracovní task, následuje druhý
explicitní překladový krok. CLI jazyk nevymýšlí ani automaticky nedetekuje.
