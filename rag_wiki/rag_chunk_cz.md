# RAG chunky v Jamesovi

Tento dokument popisuje, jak James připravuje zdroje pro RAG, co přesně znamená
chunk a vektorová vzdálenost a jak s výsledky pracovat v **RAG → test** a v
chatu.

## Stručný přehled

RAG (*Retrieval-Augmented Generation*) rozdělí zdrojové dokumenty na menší
textové úseky — **chunky**. Před odpovědí modelu se vyhledají relevantní
chunky a připojí se do kontextu chatu. Model pak odpovídá s oporou v tomto
materiálu, místo aby se spoléhal jen na své obecné znalosti.

Pro wiki `btc_cz` vzniklo například ze dvou souborů 188 chunků:

- `Bitcoin-whitepaper-original-CZ.pdf`;
- `mb_pdf260301.txt`.

Počet chunků není počet kapitol, odstavců, slov ani tokenů. Je to počet
textových úseků, které systém vytvořil z načtených souborů.

## Jak vznikne chunk

V `cli_vector.json` jsou nyní nastaveny hodnoty:

```json
"chunk_size": 1200,
"chunk_overlap": 160
```

Chunk má nejvýše přibližně 1 200 **znaků**, nikoli tokenů modelu. Dělí se
pokud možno na odstavci nebo zalomení řádku. Když to nejde, použije se hranice
znaků.

Sousední chunky se překrývají o až 160 znaků. Díky tomu věta nebo myšlenka,
která leží na hraně, obvykle zůstane dostupná v obou sousedních chuncech.

```text
Zdrojový dokument
└─ chunk 0 ───────────────────────┐
                    └─ chunk 1 ───────────────────────┐
                                   └─ chunk 2 ──────────
          <---- překrytí až 160 znaků ---->
```

Zmenšení na 512 znaků by vedlo k více a jemnějším chunkům. Pět takových
chunků se snáze vejde do kontextu chatu, ale vyhledávání musí přesněji vybrat
správný úsek a změna vyžaduje kompletní reindex dané wiki. Současných 1 200
znaků je rozumný univerzální kompromis.

## Co se indexuje

Každý chunk se uloží do databáze, například `rag_wiki/data/wiki_btc_cz.db`,
dvěma způsoby.

| Vrstva | Co obsahuje | K čemu slouží |
|---|---|---|
| `chunks` | původní text chunku, zdroj, stránku a pořadí | zobrazení výsledku a citace původu |
| FTS5 (`chunks_fts`) | slova/tokeny a jejich pozice v textu | přesné textové hledání v `/chunk` |
| `chunk_vectors` | jeden embedding, zde 768 desetinných čísel | sémantické hledání v **RAG → test** |

Neukládá se samostatný vektor pro každé slovo. Jeden celý chunk dostane jeden
vektor od embedding modelu `embeddinggemma`. U aktuální konfigurace má tento
vektor 768 rozměrů.

Při dotazu se stejným modelem vytvoří vektor i pro vstup uživatele. Databáze
potom porovnává tento vektor s vektorem každého chunku.

## FTS5: přesná textová vrstva chatu

Chatový příkaz `/chunk` používá FTS5. Jde o textové hledání: záleží na
slovech, frázích a operátorech. Nevolá model a ještě neodpovídá na otázku;
pouze nahradí předchozí dočasný RAG zdroj v kontextu chatu. Otázka následuje
až na dalším řádku.

Nejdříve se vybere wiki:

```text
/rag btc_cz
```

Jméno profilu `DATA` obvykle odpovídá databázi `rag_wiki/data/wiki_DATA.db`
a registru v `rag_wiki/databases.json`. Po připojení ukazuje druhý řádek
hlavičky chatu například `RAG: wiki_btc_cz`. Volba je pouze pro současné
sezení chatu; nepřepisuje globální hlavní wiki. Příkaz

```text
/rag off
```

wiki odpojí a odstraní její dočasně připojený RAG zdroj z kontextu.

Potom se připojí zdroje:

```text
/chunk (hardwarová peněženka)
```

Tento zápis použije výchozí počet 5 chunků. Hodnota je uložená v
`james/chat_cmd.json` jako `defaults.rag_chunk_count` a lze ji změnit bez
úpravy kódu.

Po vypsání „Attached RAG context“ se teprve zadá dotaz pro model, například:

```text
Jak bezpečně používat hardwarovou peněženku?
```

### Filtry a operátory

Pro jednu přesnou frázi jsou přehledné závorky:

```text
/chunk (hardwarová peněženka)
/chunk #(hardwarová peněženka)
```

Oba zápisy znamenají totéž. Lze zadat až tři filtry.

Čárka znamená `AND`:

```text
/chunk (bitcoinová peněženka), (těžba bitcoinů)
```

To najde jen chunky obsahující obě fráze. Pokud má mít uživatel kontrolu nad
logikou, použije explicitní operátory:

```text
/chunk (bitcoinová peněženka) or (hardwarová peněženka)
/chunk (těžba bitcoinů) and (proof of work)
/chunk #(peněženka) or #(seed phrase) and #(záloha)
```

Operátory jsou předány FTS5. U složitějších výrazů je dobré dávat závorky na
každou hledanou frázi, aby byl záměr čitelný.

## Vektorové hledání v RAG → test

Položka **RAG → test** je bezpečný, pouze čtecí náhled vektorového vyhledání.
Nemění databázi ani kontext chatu. Postupně se ptá na:

1. wiki, například `btc` nebo `btc_cz`;
2. délku náhledu chunku (výchozí 50 znaků);
3. počet výsledků (výchozí 21);
4. hledanou frázi.

Příklad:

```text
Search phrase: bitcoin mining, hardware wallet
```

Čárka zde rozděluje dotaz na sémantické skupiny. Test vytvoří vektor pro celý
dotaz, pro každou skupinu a pro jednotlivá slova:

```text
all:      bitcoin mining hardware wallet
group:    bitcoin mining
group:    hardware wallet
word:     bitcoin
word:     mining
word:     hardware
word:     wallet
```

Výsledky se řadí podle vzdálenosti `all`. Další vzdálenosti jsou diagnostika
pro **ty samé vybrané chunky**, ne další samostatné seznamy výsledků.

Závorková syntaxe se v testu přijme, ale nemá přesně stejnou Boolean logiku
jako FTS5. Vektorové hledání ji chápe jako význam jednotlivých skupin. Přesné
`AND` a `OR` patří do chatového `/chunk`.

## Co znamená vektorová vzdálenost

Aktuální test používá euklidovskou L2 vzdálenost mezi embeddingem dotazu a
embeddingem chunku.

```text
menší vzdálenost  = významově podobnější chunk
větší vzdálenost  = významově vzdálenější chunk
```

Není to počet shodných slov, procento správnosti ani pravděpodobnost. Dotaz
`hardwarová peněženka` proto může dobře najít text o offline podepisování,
privátních klíčích, seed frázi nebo cold storage, i když v něm není přesně
zadané spojení.

Naopak může sémanticky blízký chunk minout doslovné slovo. Na přesnou frázi je
vhodnější FTS5 `/chunk`; na podobný význam RAG → test.

### Orientační barevné pásmo

Pro aktuální model `embeddinggemma` náhled používá jen orientační značky:

- vzdálenost `≤ 1.10`: blízká, žlutě;
- vzdálenost `≥ 1.25`: vzdálená, zeleně;
- hodnoty mezi nimi: bez zvýraznění, závisí na dotazu.

Tyto prahy nejsou univerzální. Změna embedding modelu, jazyka, délky dotazu
nebo databáze může jejich význam posunout. Nejdůležitější je pořadí výsledků
pro jeden konkrétní dotaz a skutečný text zobrazeného chunku.

Například překlep `bitcoin mininh, hardware wallet` může stále vracet useful
výsledky: embedding model chápe podobnost dotazu, ale FTS5 by takový překlep
doslovně nenašel. To je očekávaný rozdíl mezi oběma vrstvami.

## Náhled a kvalita webových zdrojů

Vektorový test ukazuje krátký náhled kolem prvního doslovně nalezeného slova,
které zvýrazní žlutě. Když se žádné slovo v textu doslovně nevyskytne, ukáže
začátek chunku — sémantická shoda může existovat i bez doslovné shody.

Při ingestu webů se vynechávají běžné HTML části `header`, `nav`, `footer`,
`aside` a formuláře. Název a URL webu se neembedují; zůstávají pouze jako
provenance výsledku. Některé weby však staví navigaci z obyčejných `div`
elementů, takže se ojediněle může objevit navigační nebo patičkový chunk.
Takový výsledek je důvod zkontrolovat náhled, ne důkaz relevance.

## Kolik chunků připojovat do chatu

Chat je spuštěn s kontextovým oknem `num_ctx: 4096` tokenů. Pro připojené RAG
zdroje je v Jamesovi samostatný limit 6 000 znaků, což je zhruba 1 500 tokenů
anglického textu. Zbytek potřebují systémové instrukce, historie konverzace,
aktuální otázka a odpověď modelu.

Pro chunky velké kolem 1 200 znaků je proto praktické nastavení:

| Počet | Doporučení |
|---:|---|
| 3 | běžná otázka, nejvíce prostoru pro historii a odpověď |
| 5 | současný výchozí kompromis |
| více než 5 | jen když jsou chunky kratší nebo je potřeba porovnání zdrojů |
| 20 | pro chat obvykle nevhodné; výsledky se sice vyhledají, ale část kontextu se ořízne |

Je-li nalezených chunků více, než se vejde do 6 000 znaků, James připojí
nejlépe řazené první chunky a poslední rozpracovaný blok označí
`[context truncated]`. Proto není počet vyhledaných chunků automaticky stejný
jako množství textu, které se skutečně dostane k modelu.

## Doporučený pracovní postup

1. V **RAG → test** si vyzkoušet dotaz a zkontrolovat, zda první náhledy
   opravdu odpovídají tématu.
2. V chatu vybrat databázi, například `/rag btc_cz`.
3. Připojit obvykle pět přesných FTS5 chunků, například
   `/chunk (hardwarová peněženka)`.
4. Zkontrolovat vypsaný „Attached RAG context“.
5. Až potom na dalším řádku položit modelu otázku.
6. Pokud výsledky nejsou dobré, zúžit přesnou frázi, použít `AND`/`OR`, nebo
   se vrátit do testu a prozkoumat sémantické výsledky.

RAG není náhrada za kontrolu zdrojů. Je to mechanismus, který modelu předá
nejpravděpodobněji relevantní úseky. Kvalita odpovědi závisí na kvalitě
zdrojů, rozumné velikosti chunků, dobrém dotazu a na tom, zda se správný text
vejde do kontextového okna.
