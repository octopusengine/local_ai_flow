# Vyhodnocení lokálního AI workflow

## Shrnutí

Test projektu `local_ai_flow` nad reálným vytištěným dokumentem byl úspěšný. Celý dokumentový tok proběhl lokálně:

```text
fotografie → OCR → překlad → syntéza řeči
```

Navzdory nekvalitní fotografii pořízené za šera dosáhlo OCR prakticky bezchybného výsledku. Překlad zachoval celý význam původního textu, ale před publikováním by vyžadoval jazykovou a terminologickou korekturu. Výsledné dvouminutové MP3 bylo vytvořeno úspěšně.

Celkové praktické hodnocení: **velmi dobrý a použitelný lokální prototyp**.

## Testovací artefakty

- Referenční text: [`project_bwp/real.txt`](project_bwp/real.txt)
- Fotografie dokumentu: [`project_bwp/camera.png`](project_bwp/camera.png)
- Výsledek OCR: [`project_bwp/camera.txt`](project_bwp/camera.txt)
- Český překlad: [`project_bwp/translate.txt`](project_bwp/translate.txt)
- Výsledná řeč: [`project_bwp/translate.mp3`](project_bwp/translate.mp3)
- Provozní záznam: [`project_bwp/log.txt`](project_bwp/log.txt)

## Vstupní fotografie

Fotografie má rozlišení 640 × 480 bodů a velikost přibližně 378 kB. Byla pořízena za nepříznivých podmínek:

- nízká úroveň osvětlení;
- slabý kontrast mezi papírem a textem;
- mírné rozostření;
- perspektivní zkreslení;
- nerovnoměrné osvětlení stránky.

Přesto zůstal celý anglický odstavec pro OCR čitelný. Z hlediska testování jde o podstatně náročnější a realističtější vstup než čistý digitální snímek PDF.

## Přesnost OCR

OCR provedl model `deepseek-ocr:3b` s parametry:

```json
{
  "temperature": 0.1,
  "num_predict": 4096
}
```

Po normalizaci Markdown nadpisu, mezer a zalomení řádků byly naměřeny tyto výsledky:

| Metrika | Výsledek |
| --- | ---: |
| Počet slov v referenci | 269 |
| Počet slov po OCR | 269 |
| Editační vzdálenost na úrovni slov | 1 |
| Slovní shoda | 99,63 % |
| Editační vzdálenost na úrovni znaků | 1 |
| Znaková shoda | 99,94 % |

Jediným rozdílem bylo doplnění spojovníku:

```text
reference: nonreversible services
OCR:       non-reversible services
```

OCR v tomto případě použilo běžnější a jazykově vhodnější zápis. Nebyla vynechána žádná věta, číslo ani významová část. Model navíc správně rozpoznal nadpis a rozdělil text do logických odstavců.

Praktické hodnocení OCR: **téměř 10/10**.

## Kvalita překladu

Překlad vytvořil model `translategemma:12b`. Výstup zachoval všechny věty i hlavní význam původního textu a neobsahoval zjevné halucinace nebo doplněné informace.

Silné stránky:

- úplnost překladu;
- zachování struktury textu;
- správné převedení hlavních myšlenek;
- převážně přirozená a srozumitelná čeština;
- použitelnost pro rychlé porozumění dokumentu.

Před publikováním by bylo vhodné opravit několik míst:

| Výstup modelu | Doporučená úprava |
| --- | --- |
| `nemohou vyhnout se mediaci sporů` | `nemohou se vyhnout zprostředkování sporů` |
| `Určitý procento` | `Určité procento` |
| `umožnil dvěma ochotným stranám transakce` | `umožnil dvěma ochotným stranám provádět transakce` |
| `kryptografické ověření` | přesněji `kryptografický důkaz` |
| `upřímné uzly` | v bitcoinové terminologii spíše `poctivé uzly` |

Překlad výrazu `peer-to-peer distributed timestamp server` také částečně ztratil technickou přesnost. Pro běžné pochopení je výsledek dostatečný, pro odborný nebo publikační text je vhodná lidská korektura.

Praktické hodnocení překladu: **přibližně 7,5/10**.

## Syntéza řeči

Přeložený text byl úspěšně převeden na soubor `translate.mp3` pomocí českého hlasu `jirka`.

Parametry výsledného souboru:

| Vlastnost | Hodnota |
| --- | --- |
| Délka | 2 minuty 0,24 sekundy |
| Formát | MP3 |
| Kanály | mono |
| Vzorkovací frekvence | 22 050 Hz |
| Datový tok | přibližně 68 kb/s |
| Velikost | přibližně 1,03 MB |

Log potvrzuje úspěšné dokončení syntézy i uložení výsledného souboru. Poslechová kvalita nebyla součástí tohoto vyhodnocení.

## Časová náročnost

| Fáze | Doba |
| --- | ---: |
| OCR vyhodnocení | 64,4 sekundy |
| Překlad | 7 minut 35 sekund |
| Syntéza řeči | přibližně 3 minuty |
| Celý praktický postup včetně fotografování | přibližně 14–15 minut |

Překlad byl nejpomalejší částí workflow. Vzhledem k použití lokálního modelu o velikosti přibližně 8,1 GB je ale výsledný čas pro prototyp přijatelný.

Hodnota:

```json
"ollama_timeout_seconds": 900
```

v souboru `project.json` nepředstavuje plánovanou délku celého workflow. Jde o maximální timeout při čekání na odpověď Ollamy. Samotný `runner.py` délku jednotlivých subprocess kroků neomezuje.

## Soukromí a bezpečnost

Záznam potvrzuje komunikaci s lokální Ollamou na adrese `localhost`. OCR, překlad i syntéza řeči proběhly lokálně a při tomto testu nebyla použita externí cloudová AI služba.

Výhody:

- fotografie ani text nemusejí opustit počítač;
- pracovní artefakty jsou soustředěny v adresáři projektu;
- jednotlivé kroky jsou reprodukovatelné;
- log obsahuje použité modely, parametry, cesty a časy;
- uživatel má přímou kontrolu nad vstupy i výstupy.

Lokální zpracování ale automaticky neznamená šifrované uložení. Fotografie, OCR text, překlad, audio i celý prompt jsou čitelně uložené na disku a část obsahu je také v `log.txt`. Bezpečnost proto stále závisí na zabezpečení počítače, přístupových právech a případném šifrování disku.

## Kvalita logování

Soubor `log.txt` umožňuje dobře dohledat:

- použitý CLI nástroj;
- model a jeho parametry;
- vstupní a výstupní soubory;
- začátek a konec jednotlivých fází;
- dobu vyhodnocení;
- chybové stavy.

V dodaném logu jsou doloženy fáze:

```text
camera → OCR → translate → speech
```

Samostatný blok `cli_mcp.py` v tomto konkrétním logu není. Pro úplný záznam runneru by bylo vhodné doplnit také začátek, konec, dobu trvání a návratový kód každého kroku přímo z `runner.py`.

Log navíc obsahuje ANSI řídicí sekvence pro barvy terminálu. Ty sice neovlivňují výsledek, ale zhoršují čitelnost souboru a strojové zpracování. V budoucnu by bylo vhodné zapisovat do terminálu barevný text a do logu jeho čistou variantu.

## Celkové hodnocení

| Oblast | Hodnocení |
| --- | ---: |
| Odolnost vůči nekvalitní fotografii | velmi dobrá |
| Přesnost OCR | výborná |
| Úplnost překladu | velmi dobrá |
| Jazyková kvalita překladu | dobrá, vyžaduje korekturu |
| Syntéza řeči | technicky úspěšná |
| Reprodukovatelnost | velmi dobrá |
| Soukromí | velmi dobré při správně zabezpečeném počítači |
| Rychlost | přijatelná pro lokální prototyp |

Projekt prokázal, že dokáže zpracovat reálný, nekvalitně nasnímaný tištěný dokument od fotografie až po český zvukový výstup bez použití cloudové AI. Největším úspěchem je téměř bezchybné OCR. Hlavním prostorem pro zlepšení zůstává rychlost překladu, odborná terminologie a úplnější logování runneru.

Výsledek lze považovat za **úspěšnou praktickou demonstraci lokálního, soukromého a reprodukovatelného AI workflow**.
