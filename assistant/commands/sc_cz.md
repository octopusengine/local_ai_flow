# Dostupné slash commands

> Tento dokument je generován z [sc.json](sc.json); neupravujte jej přímo. Anglická verze: [README.md](README.md).

## Konverzace

- `/chat` – Přirozeně pokračuj v konverzaci. Dodaný referenční kontext ber pouze jako poslední odpověď asistenta a odpověz přímo na aktuální vstup uživatele. Referenční kontext nezmiňuj, pokud se na něj uživatel výslovně nezeptá. Odpovídej stručně, pouze čistým textem bez Markdownu.

## Transformace textu

- `/explain` – Vysvětli libovolné téma jednoduchými a srozumitelnými slovy.
- `/summarize` – Shrň dlouhý text nebo článek se zachováním důležitých bodů.
- `/translate` – Přelož text do požadovaného jazyka se zachováním významu a formátu.
- `/rewrite` – Přeformuluj obsah pro požadovaný účel, tón nebo publikum.
- `/grammar` – Oprav gramatiku, pravopis a interpunkci bez změny zamýšleného významu.
- `/speechfix` – Opravuj pouze pravděpodobné chyby v přepisu rozpoznané řeči a postupuj konzervativně. Náhradní slovo zvol jen tehdy, když ho výrazně podporuje zvuková nebo písmenná podobnost s rozpoznaným slovem; kontext věty používej jen jako druhotnou kontrolu. Nikdy slovo nenahrazuj pouze proto, že jiné slovo zní běžněji nebo dává větě hladší smysl. Nic si nevymýšlej, nerozepisuj ani neměň zkratky a nenahrazuj věrohodné technické, produktové, cizojazyčné ani neznámé výrazy. Zachovej původní znění, zamýšlený význam i obsah; nic nepřidávej, nevynechávej, nepřeformulovávej ani stylisticky neupravuj. Pokud slovo zůstává nejisté, ponech je beze změny. Vrať pouze opravený přepis.
- `/improve` – Zlepši srozumitelnost, čitelnost a plynulost při zachování původního záměru.
- `/shorten` – Zkrať text a udělej jej stručnější při zachování podstatných informací.
- `/lengthen` – Rozšiř text o užitečné detaily, vysvětlení nebo příklady.

## Analýza a vysvětlení

- `/compare` – Porovnej dvě nebo více věcí podle relevantních kritérií.
- `/contrast` – Ukaž hlavní rozdíly, kompromisy, silné a slabé stránky.
- `/principles` – Vysvětli hlavní principy nebo myšlenky daného tématu.
- `/steps` – Rozděl úkol na jasný návod krok za krokem.
- `/howto` – Poskytni praktický návod, jak dosáhnout daného cíle.
- `/examples` – Uveď praktické příklady, které téma přiblíží.
- `/analogy` – Vysvětli téma pomocí užitečných přirovnání.
- `/case` – Uveď realistický příklad použití z praxe nebo případovou studii.
- `/research` – Prozkoumej téma do hloubky, rozliš fakta od předpokladů a pokud jsou k dispozici, uveď zdroje.
- `/critic` – Najdi slabiny, chyby, rizika a mezery v dodaném nápadu nebo textu.
- `/decision` – Porovnej uvedené možnosti podle jasných kritérií, popiš kompromisy a doporuč nejlepší variantu se stručným odůvodněním.

## Modifikátory formátu

- `/bulletpoints` – Vrať výsledek jako stručné odrážky.
- `/list` – Vrať výsledek jako přehledný číslovaný seznam.
- `/table` – Převeď výsledek nebo dodaná data do přehledné tabulky.
- `/brief` – Poskytni co nejstručnější užitečnou odpověď.
- `/json` – Vrať pouze platný JSON podle požadované struktury, bez Markdown bloků a vysvětlujícího textu.
- `/diagram` – Vytvoř přehledný Mermaid diagram pro požadovaný proces, strukturu nebo vztahy. Vrať pouze zdroj Mermaid.

## Dokumenty a kariéra

- `/template` – Vytvoř znovupoužitelnou šablonu pro požadovaný účel.
- `/email` – Napiš profesionální e-mail s předmětem, oslovením, tělem a zakončením.
- `/coverletter` – Napiš motivační dopis přizpůsobený uvedené pozici a zkušenostem.
- `/resume` – Vytvoř nebo vylepši přehledný životopis zaměřený na danou roli.
- `/interview` – Vytvoř realistické otázky k pohovoru a kvalitní vzorové odpovědi.
- `/copywriter` – Napiš přesvědčivý marketingový text pro určené publikum a cíl.
- `/seo` – Vytvoř obsah optimalizovaný pro vyhledávání bez ztráty přesnosti a čitelnosti.
- `/viral` – Navrhni obsahové nápady s vysokým zapojením vhodné pro danou platformu a publikum.

## Učení, tvorba nápadů a plánování

- `/quiz` – Vytvoř kvíz s otázkami, odpověďmi a volitelným vysvětlením.
- `/flashcards` – Vytvoř stručné kartičky s otázkou na jedné straně a odpovědí na druhé.
- `/brainstorm` – Vymysli rozmanité praktické nápady a seskup je podle směru nebo priority.
- `/plan` – Vytvoř proveditelný plán nebo roadmapu s cíli, kroky a milníky.
- `/strategy` – Analyzuj možnosti z dlouhodobé strategické perspektivy včetně kompromisů a rizik.
- `/checklist` – Vrať stručný, proveditelný checklist s jasnými položkami k dokončení.
- `/ceo` – Analyzuj situaci z pohledu zakladatele nebo CEO se zaměřením na výsledky a priority.

## Modifikátory stylu a hloubky

- `/human` – Piš přirozeně a lidsky, bez šablonovitých nebo robotických formulací.
- `/eli5` – Vysvětli to jako pětiletému: použij velmi jednoduchá slova, krátké věty a konkrétní příklad.
- `/eli12` – Vysvětli to jako dvanáctiletému: použij jasný běžný jazyk, vysvětli potřebné pojmy a uveď praktický příklad.
- `/expert` – Poskytni odpověď na úrovni specialisty s přesnou terminologií a odůvodněnými detaily.
- `/promptengineer` – Vylepši a optimalizuj dodaný prompt pro srozumitelnost, omezení a spolehlivý výstup.

## Zdraví a medicína

- `/doctor` – Odpovídej jako lékařský specialista a poskytuj jasné zdravotnické informace založené na důkazech. Nevydávej definitivní diagnózu ani nenahrazuj osobní klinické vyšetření. Uveď relevantní nejistoty a limity informací, rozpoznej varovné příznaky vyžadující urgentní péči a případně polož stručné doplňující otázky. Nevymýšlej si zdroje.

## Vývoj softwaru

- `/html` – Vytvoř kompletní responzivní HTML stránku pro požadovaný účel. Použij sémantické a přístupné HTML a přidej jen CSS a JavaScript nezbytný pro její funkčnost.
- `/python` – Napiš správný a čitelný program v Pythonu pro požadovaný úkol. Přidej stručný návod ke spuštění a ošetři relevantní chyby a okrajové případy.
- `/rust` – Napiš idiomatický a bezpečný kód v Rustu pro požadovaný úkol. Přidej stručný návod ke spuštění přes Cargo a ošetři relevantní chyby a okrajové případy.
- `/js` – Vytvoř jeden kompletní HTML dokument s jednoduchou JavaScriptovou aplikací ve vloženém prvku <script>. Nepoužívej externí závislosti. Vrať pouze zdrojový kód HTML.
- `/review` – Proveď revizi dodaného kódu z hlediska správnosti, čitelnosti, udržovatelnosti a pravděpodobných chyb. Zjištění seřaď podle priority a navrhni konkrétní opravy.
- `/refactor` – Refaktoruj dodaný kód tak, aby byl jednodušší, přehlednější a lépe udržovatelný bez změny zamýšleného chování.
- `/debug` – Diagnostikuj dodanou chybu nebo neočekávané chování, vysvětli pravděpodobnou hlavní příčinu a navrhni konkrétní opravu i kroky k ověření.
- `/test` – Vytvoř cílené automatizované testy pro dodaný kód, které pokryjí běžné chování, relevantní okrajové případy a ošetření chyb.
- `/security` – Posuď výsledek z hlediska relevantních bezpečnostních rizik, nebezpečného zpracování vstupů, zveřejněných tajemství a chybějící validace; navrhni zmírnění rizik.
- `/sql` – Napiš správný a čitelný SQL dotaz nebo schéma pro požadovaný úkol. Uveď nezbytné předpoklady a nepoužívej destruktivní příkazy, pokud nejsou výslovně požadovány.
- `/regex` – Vytvoř regulární výraz pro požadovaný vzor, stručně vysvětli jeho části a uveď příklady shodných i neshodných vstupů.
- `/api` – Navrhni praktický kontrakt API pro požadovanou funkci včetně endpointů, tvaru requestů a odpovědí, validace a chybových stavů.

## Skripty

- `/sh` – Napiš kompletní a čitelný Bash skript pro Linux, který vyřeší požadovaný úkol. Funkce Bashe používej jen podle potřeby, ošetři relevantní chyby a okrajové případy a vrať pouze zdrojový kód skriptu.
- `/bat` – Napiš kompletní a čitelný Windows Batch (.bat) skript, který vyřeší požadovaný úkol. Použij standardní příkazy cmd.exe, ošetři relevantní chyby a okrajové případy a vrať pouze zdrojový kód skriptu.

## Extrakce textu z obrázků

- `/ocr` – Věrně přepiš veškerý viditelný text. Zachovej pořadí čtení a smysluplnou strukturu. Nepřekládej, neshrnuj ani nepřidávej komentář; nečitelný text označ jako [nečitelné].
- `/describe` – Věrně popiš, co je na obrázku vidět. Zahrň podstatné objekty, jejich vztahy, rozvržení a případně čitelný text; nic si nevymýšlej.
