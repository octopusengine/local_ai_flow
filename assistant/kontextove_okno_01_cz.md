# Kontextové okno v `cli_ollama.py`

## Současný stav

`cli_ollama.py` sestavuje jednorázový request. Automaticky neskládá historii
konverzace ani nepřidává předchozí výstupy z projektu nebo databáze. Kontext má
prakticky dvě textové části: `prompt` a volitelný `system`.

```text
task_*.json + CLI parametry + volitelný skill
    -> vyřešený task
    -> endpoint podle typu tasku
```

| Typ tasku | Odesílaný obsah | Endpoint |
| --- | --- | --- |
| `prompt` | `prompt`, volitelně `system`, model, options, think | `/api/generate` |
| `translate` | jako `prompt`; prompt je obsah vstupního souboru | `/api/generate` |
| `ocr` | `prompt`, obrázek, model, options, think | `/api/generate` |
| `describe` | jedna `user` message s promptem a obrázkem | `/api/chat` |

### Běžný textový task

Výsledný request má přibližně tuto podobu:

```json
{
  "model": "…",
  "prompt": "dynamická data nebo prompt z tasku",
  "system": "obsah skillu\n\n\ninstrukce",
  "stream": true,
  "think": false,
  "options": {
    "seed": 42,
    "temperature": 0.2,
    "num_ctx": 4096,
    "num_predict": 1024,
    "repeat_penalty": 1.1
  }
}
```

Skill se načte z cesty v poli `skill` a vloží se jako první část `system`.
Tasková `instruction` následuje po třech nových řádcích. Volba
`--instruction` nahradí celou instrukci z tasku; nepřidává se k ní.

### Priorita konfigurace

```text
lib/ollama.json (výchozí generation options)
  -> task_*.json
    -> CLI parametry
      -> aplikovaný skill pro prompt a translate
```

`project.json` neurčuje textový obsah requestu. Vybere aktivní projektový
adresář a řídí debug, databázi a timeout. `num_ctx` nastavuje maximální okno
modelu, ale aplikace sama nepočítá tokeny, neprovádí zkracování ani neskládá
historii.

## Důležité detaily a omezení

- `--data` nahradí celý `prompt` z tasku.
- `--instruction` nahradí celou taskovou instrukci.
- Neexistující skill se tiše ignoruje.
- Výstupy předchozích kroků se předávají pouze explicitně: například přes
  `--data soubor.txt` nebo `--in soubor.txt`.
- `task_base.json` nemá vlastní prompt, proto funguje jen při předání `--data`.
- U všech typů tasků určuje `default_output_file` výchozí výstup. Parametr
  `--out` jej pro konkrétní spuštění přebije.
- Pole `prompt_long`, `temperature_long`, `num_predict_long` a `verbose` v
  aktuálním `task_describe.json` nejsou součástí odesílaného requestu.
- Skill se aplikuje pouze na `prompt` a `translate`.
- OCR nepředává `instruction` ani skill do `system`.
- Describe používá jen user message s obrázkem; nepředává `system`, instrukci
  ani skill.

## Problém současného názvosloví

`prompt` má dnes dva odlišné významy:

1. dynamická data nebo uživatelský dotaz (`--data`),
2. statické pravidlo tasku, například „vytvoř pouze HTML“.

Při použití `--data` se statické pravidlo uložené v `prompt` ztratí. To je
rizikové například pro `task_html.json`: jeho statické HTML omezení je
nahrazeno dodanými daty.

## Doporučená cílová struktura

Rozdělit kontext na čtyři jasně pojmenované vrstvy:

```text
1. profile / skills  - stabilní role a pracovní zásady
2. task_rules        - pravidla konkrétního tasku a formát výstupu
3. context           - referenční podklady, soubory a případně historie
4. user_input        - aktuální dotaz nebo data ke zpracování
```

Sestavení requestu:

```text
shared generation defaults
-> task generation overrides
-> profile + selected skills
-> task_rules
-> runtime rules (standardně přidat, ne nahradit)
-> labelled context files
-> user_input
-> endpoint adapter
```

### Návrh tasku verze 2

```json
{
  "version": 2,
  "type": "text",
  "model": "qwen3.5:latest",
  "system": {
    "skills": ["teacher-cz"],
    "rules": "Odpovídej česky. Použij stručné, přesné vysvětlení."
  },
  "input": {
    "default": "Proč je nebe modré?"
  },
  "generation": {
    "temperature": 0.3,
    "num_predict": 1024,
    "num_ctx": 8192
  },
  "output": {
    "default_file": "explain.txt"
  }
}
```

### Doporučené CLI

```text
--input TEXT|FILE          nahradí pouze aktuální vstup
--rules TEXT|FILE          přidá běhová pravidla
--replace-rules TEXT|FILE  výslovně nahradí task_rules
--context FILE             přidá označený referenční podklad
--skill ID                 přidá skill k taskovým skillům
--dry-run                  vypíše přesně složený request
```

Interní struktura by měla být pro všechny typy stejná:

```text
system:
  profile + skills + task_rules + runtime rules

user:
  [CONTEXT: nazev-souboru]
  ...

  [INPUT]
  ...
```

Teprve endpoint adapter tuto společnou strukturu přeloží do JSON konkrétního
Ollama endpointu. Jako jednotný formát dává smysl `/api/chat`, protože nativně
má role `system` a `user`, podporuje historii i obrázky. Pro modely vyžadující
`/api/generate` lze zachovat samostatný adapter.

## Doporučená migrace

1. Zavést interní objekt „resolved request“ a `--dry-run` bez změny současného
   chování.
2. Přidat novou strukturu tasků kompatibilně vedle stávající.
3. Převést dodané tasky a následně validací odmítat nepoužívaná pole.

Tento návrh zachová oddělení stabilních pravidel, vstupních dat a referenčního
kontextu. Díky tomu se při předání dynamických dat neztratí instrukce tasku a
stejná pravidla budou fungovat pro text i obrazové tasky.

## Implementace 01: nové CLI vrstvy

První kompatibilní krok je nyní implementován v `cli_ollama.py`:

```text
--input TEXT|FILE          alias původního --data; nahradí aktuální prompt
--rules TEXT|FILE          přidá běhová pravidla, lze opakovat
--replace-rules TEXT|FILE  nahradí tasková pravidla
--context FILE             přidá označený referenční podklad, lze opakovat
--skill ID                 přidá skills/ID.md, lze opakovat
--dry-run                  vypíše přesný JSON request bez volání Ollamy
```

Původní `--instruction` zůstává kompatibilním aliasem `--replace-rules`.
Původní `--data` zůstává kompatibilním aliasem `--input`.

Složený request má nyní toto pořadí:

```text
task skill(s) -> CLI skill(s) -> task / replaced rules -> appended rules
                                        = system

[REFERENCE: soubor] ... [END REFERENCE] -> [INPUT] aktuální vstup
                                        = prompt nebo user message
```

`--context` nemění system pravidla. Obsahuje referenční data označená názvem
souboru, aby model i člověk při `--dry-run` poznali jejich původ.

## Kompatibilita s dosavadními flow

Soubory `flows/flow*.txt` nebyly změněny.

- `flow_voice_free.txt`, `flow_voice_sky.txt`, `flow_freestyle.txt` a
  `flow_base.txt` fungují nadále: jejich `--data` a `--instruction` jsou
  zachované aliasy.
- `flow_cam_describe.txt`, `flow_bwp.txt` a `flow_ocr_test.json` nepoužívají
  nové volby; jejich dosavadní request zůstává stejný.
- `flow_voice_holly_pivo.txt` a `flow_voice_cotoje12.txt` si zachovávají
  podstatné chování: `--instruction` nahradí pravidla tasku, ale skill zůstane
  před nimi.
- `flow_html_cz.txt` už dnes přepisuje statický prompt `task_html.json` pomocí
  `--data`. Není to nová nekompatibilita, ale důvod pro budoucí přesun
  statického „vytvoř pouze HTML“ do taskových pravidel.

Záměrná změna pro případné starší vlastní image tasky: OCR a describe nyní
odešlou jejich `instruction` a skill do system kontextu. Dříve se tato pole u
obrazových tasků ignorovala. Dodané image tasky je nepoužívají, takže jejich
stávající flow není ovlivněno.
