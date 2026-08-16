# Report: test `sd8x`

## Shrnutí

Test `tasks_flows/flow_test_sd8x.txt` splnil svůj účel. Ověřil osm samostatných slash commands nad stejným českým vstupem, stejným seedem a stejným modelem.

```text
explain, summarize, rewrite, grammar,
improve, shorten, bulletpoints, table
```

## Výsledek běhu

- Flow skončilo úspěšně: 11 kroků za 226,6 s.
- Všech osm odpovědí se zobrazilo v terminálu.
- V databázi vzniklo osm záznamů pod selektorem `sd8x`: ID `119–126`.
- Všechny testované běhy používaly stejný model, vstup, `--sc-cz` a seed `42`.
- Jediná proměnná mezi běhy byl vybraný `--sc` command.

## Co fungovalo dobře

Commands se projevily rozlišitelně a odpovídaly zamýšlenému účelu:

- `shorten` vytvořil stručné, věcně použitelné shrnutí.
- `bulletpoints` správně převedl vstup do odrážek.
- `table` správně vytvořil přehlednou Markdown tabulku.
- `summarize` zachoval hlavní obsah vstupu.

To potvrzuje, že sestavování `--sc` pravidel, `--sc-cz` a ukládání výsledků do DB funguje.

## Pozorování

### `explain` je baseline

`explain` je nyní interní výchozí klíč a jeho název ani vlastní instrukce se do system kontextu nevkládají. Běh proto dal obecnou interpretaci a doporučení, ne úzce řízené „vysvětlení“. Toto chování odpovídá současnému návrhu.

### Obecná pravidla transformací jsou příliš volná

U commandů `grammar`, `rewrite` a zejména `improve` model někdy změnil význam nebo vytvořil jazykovou chybu:

- `rewrite`: „nový verze“, „dva chyby“;
- `improve`: „nové menu matky“;
- `grammar`: změnil formulace místo pouhé korektury.

To není problém skládání CLI ani flow. Je to signál, že pravidla jednotlivých commandů v `assistant/commands/sc.json` potřebují přesnější instrukce pro model.

## Doporučený další krok

Rozšířit vybrané commandy o samostatná, přesnější pravidla pro model, například `rules_cz` a později i `rules_en`. Texty `sc_cz` a `sc_en` pak mohou zůstat stručným popisem commandu pro uživatele.

### Návrh pro `grammar`

```text
Oprav pouze gramatiku, pravopis a interpunkci.
Neměň fakta, význam, tón, pořadí informací ani formát.
Nevysvětluj změny. Vrať pouze opravený text.
```

### Návrh pro `improve`

```text
Zlepši srozumitelnost a plynulost.
Zachovej všechna fakta, význam a záměr vstupu.
Nevymýšlej nové informace ani neměň věcná tvrzení.
Vrať pouze upravený text.
```

## Závěr

Architektura slash commands i testovací flow fungují. Další hodnotný krok je ladění kvality jednotlivých command pravidel, zejména u transformací, kde musí model zachovat význam a nesmí doplňovat nové informace.
