# Vyhodnocení test5: pět modelů na Windows a Linuxu

Vyhodnoceno 16. 9. 2026 z devíti reportů v této složce. **V obecné faktografii není spolehlivý vítěz. Ve fyzice vycházejí nejlépe Ornith a GPT-OSS, školní matematiku a elektroniku zvládají modely mnohem lépe. Qwen 4B je nejrychlejší, ovšem jeho faktické chyby omezují použitelnost.** Jde o hodnocení těchto konkrétních českých odpovědí a nastavení, nikoli univerzální žebříček modelů.

## Podklady a metoda

Reporty obsahují 147 sekcí otázek, z toho 137 s uvedenou dobou trvání: 28 inicializačních a 109 věcných odpovědí. Jedna z měřených věcných odpovědí je prázdná. Dalších deset sekcí nemá dokončený výstup s časem; samotná přítomnost nadpisu neprokazuje úspěšné spuštění ani dokončení otázky.

| Report | Sekce | S časem | S textem a časem | Součet časů (min) |
| --- | --- | --- | --- | --- |
| [flow_batch_mod1linux2_cz.md](flow_batch_mod1linux2_cz.md) | 16 | 15 | 15 | 17,1 |
| [flow_batch_mod1linux_cz.md](flow_batch_mod1linux_cz.md) | 11 | 10 | 10 | 11,8 |
| [flow_batch_mod1win1_cz.md](flow_batch_mod1win1_cz.md) | 12 | 12 | 11 | 26,5 |
| [flow_batch_mod2_czlinux2.md](flow_batch_mod2_czlinux2.md) | 25 | 20 | 20 | 65,6 |
| [flow_batch_mod2linux1_cz.md](flow_batch_mod2linux1_cz.md) | 11 | 10 | 10 | 35,3 |
| [flow_batch_mod2linux_cz.md](flow_batch_mod2linux_cz.md) | 11 | 10 | 10 | 35,4 |
| [flow_batch_mod2win1_cz.md](flow_batch_mod2win1_cz.md) | 25 | 25 | 25 | 104,8 |
| [flow_batch_mod3linux1_cz.md](flow_batch_mod3linux1_cz.md) | 11 | 10 | 10 | 22,4 |
| [flow_batch_mod3win1_cz.md](flow_batch_mod3win1_cz.md) | 25 | 25 | 25 | 68,3 |

„Text“ v tabulce znamená neprázdný výstup s časem, nikoli správnou či úplnou odpověď. Součet minut je pouze součet zaznamenaných dob; nezahrnuje neměřené chyby, přestávky ani režii celého flow. `flow_batch_mod2linux_cz.md` a `flow_batch_mod2linux1_cz.md` mají shodné odpovědi, ale odlišné časové údaje: nejsou totožnými kopiemi souboru.

**Bodování 1–99:** odborné posouzení správnosti, splnění zadání, úplnosti a srozumitelnosti. 90–99 = správná a téměř úplná odpověď; 75–89 = převážně použitelná s výhradami; 50–74 = správné jádro, ale významné chyby či neúplnost; 25–49 = silně nespolehlivá; 2–24 = převážně chybná; 1 = prázdná dokončená odpověď nebo nesplněný jednoduchý inicializační pokyn. Body nejsou procenta správných vět ani měření s přesností na jednotky. Rozdíl několika bodů nepovažuji za přesvědčivý důkaz převahy.

Rychlost do bodů nevstupuje. Správná rovnice nezachrání nesprávný výklad; smyšlená díla, paragrafy a data se penalizují výrazně. Uříznutý konec hodnotím podle toho, co v dodané odpovědi skutečně chybí. Q1 kontroluje pouze pokyn „agama“, do tematických průměrů ji nezahrnuji.

Pro každou otázku má Linux a Windows stejnou váhu: nejprve průměr dostupných odpovědí na dané platformě, poté průměr platforem. Opakované linuxové odpovědi zde mají totožný obsah, tedy i stejné skóre. Pokud je dostupná jen jedna platforma, používám její výsledek a omezení uvádím. Chybějící data značí **—**, nikoli 1. Jednička u GPT-OSS v `1_2` je skutečný dokončený prázdný výstup po 355,867 s. Nedokončené linuxové inicializace GPT-OSS nejsou hodnoceny jako vědomostní chyby.

## 1. Hodnocení podle odpovědí

### Obecné otázky: flow 1

**Spolehlivý model tento vzorek neukázal.** Gemma má z úplných dostupných sad nepatrně nejlepší průměr, ale pouze z jednoho linuxového běhu; Qwen latest je blízko a má data z obou strojů. Takto nízké výsledky nejsou důvodem doporučit jednoho z nich jako dobrý faktografický model. GPT-OSS a Ornith pro tuto sadu nelze plnohodnotně porovnat: GPT-OSS má jednu prázdnou věcnou odpověď, Ornith žádnou.

- **Právo (`1_2`):** všechny dostupné neprázdné odpovědi míjejí podstatu výprosy. Modely ji popírají, zaměňují za výpůjčku či nájem nebo vymýšlejí právní institut a paragrafy. Správně je výprosa bezplatné užívání věci bez sjednané doby i účelu, s možností požadovat vrácení podle libosti; zápůjčka se týká zastupitelné věci a vrácení stejného druhu, úrok není povinnou definiční podmínkou. Viz [občanský zákoník, § 2189–2190 a § 2390–2392](https://www.zakonyprolidi.cz/cs/2012-89#p2189).
- **Praha–Ostrava (`1_3`):** velké rozdíly v odhadech, nesmyslné okliky a vymyšlené stanice či silnice. Qwen 4B zmiňuje například Ostravu-Západní; Gemma podhodnocuje cestu na přibližně dvě hodiny. Orientační přímá cesta vlakem kolem 3–4 hodin je rozumnější než tyto extrémy; konkrétní spoj vyžaduje jízdní řád. Podklady: [ČD, zkušenost se spojením kolem 3:15 (2023)](https://zeleznicar.cd.cz/assets/zeleznicar/zeleznicar_10_2023.pdf), [traťový jízdní řád 001 pro rok 2026](https://www.cd.cz/jizdni-rad/tratove-jizdni-rady/files/k001-od-2026-03-01.pdf).
- **Rok 1968 (`1_4`):** modely zpravidla znají invazi a potlačení pražského jara, ale kazí data a souvislosti. Qwen 4B uvádí červenec nebo 27. srpen, latest přidává nesmyslné výrazy či chybnou délku následujícího období. Gemma vystihuje hlavní událost lépe, jazyk je však místy silně poškozený. Referencí je invaze v noci z 20. na 21. srpna a ukončení reformního procesu: [ÚSTR](https://www.ustrcr.cz/ustr-spustil-portal-k-vyroci-55-let-od-invaze-do-ceskoslovenska/).
- **Čapek (`1_5`):** velmi špatné výsledky. Qweny kombinují R.U.R. se smyšlenými či cizími tituly; Gemma nedodá požadovaná tři díla. Uznatelná jsou například R.U.R., Továrna na absolutno a Krakatit; vhodně odůvodněná Válka s mloky také. Nevyžadoval jsem jedinou pevnou trojici. Viz [Památník Karla Čapka](https://karelcapek.cz/cs/aktuality/tovarna-na-utopii).

**Poměr rychlost/správnost:** pro tuto sadu nemá přesvědčivého vítěze. Qwen 4B odpovídá rychle, ale jeho chyby jsou příliš zásadní. Gemma na Linuxu není o mnoho pomalejší a má o něco lepší obsah, pořád však hluboko pod použitelnou úrovní bez ověřování.

### Fyzika a matematika: flow 2, dále `3_3` a `3_5`

**Obsahově nejlepší dvojice: Ornith a GPT-OSS.** Ornith má nepatrně vyšší průměr fyziky, zvláště díky Maxwellovým rovnicím a Hawkingovu záření. GPT-OSS je vyrovnanější u Verlindeho teorie a entropie. Rozdíl je malý, Ornith navíc máme pouze z Windows. Ani jeden nepodává bezchybný fyzikální výklad.

- **Entropie:** modely většinou uvedou plochu horizontu a správný základ vzorce, pak ale přidávají chyby v jednotkách, historických údajích nebo ve vztahu k holografii. Makroskopický vztah není totéž jako obecně hotové mikroskopické vysvětlení všech černých děr. Referenční vztah je `S = k_B c³ A / (4 G ℏ)`; viz [Bekensteinův výklad](https://www.scholarpedia.org/article/Bekenstein-Hawking_entropy).
- **Verlinde:** je potřeba rozlišit emergentní/entropickou gravitaci a následnou hypotézu vysvětlující jevy připisované temné hmotě. Nejde o obecně potvrzenou náhradu obecné relativity. GPT-OSS a Qwen latest zachycují jádro lépe; Ornith přidává nepodložená omezení na typy galaxií. Opora: [Verlinde 2010](https://arxiv.org/abs/1001.0785), [Verlinde 2016](https://arxiv.org/abs/1611.02269).
- **Maxwell:** nestačí vypsat čtyři známé vzorce. Qwen 4B na Windows chybuje v materiálové podobě rovnice, Gemma na Windows zaměňuje jednu Maxwellovu rovnici za rovnici kontinuity. U několika odpovědí chybí dokončení odvození vlnové rovnice. Správné rovnice a jejich význam shrnují [Feynmanovy přednášky](https://www.feynmanlectures.caltech.edu/II_18.html).
- **Hawking:** správný vztah teploty nestačí při současných chybných tvrzeních o energii, singularitě horizontu či numerických odhadech. Ornith se pozitivně odlišuje zmínkou o Bogoljubovově transformaci a rozlišením pozorování černých děr od důkazu Hawkingova záření, ale také není bez chyb.
- **Elektronika a matematika:** zde jsou výsledky výrazně lepší. Správně vychází sériově 40 mA oběma rezistory, úbytky 4 a 8 V, paralelně celkem 180 mA. Rezistor přeměňuje elektrickou energii, „nespotřebovává proud“. U odmocnin platí `√9 = 3`, `√(x²) = |x|`; rovnice `√(x + 2) = x` má pouze `x = 2`, kandidát `−1` nevyhovuje původní rovnici. Tyto výsledky modely většinou zvládají, horší bývá doprovodný výklad.

**Poměr rychlost/správnost:** pro fyziku je v tomto vzorku rozumným kompromisem GPT-OSS, pokud úspěšně odpoví. Na Windows má za šest shodných nerd otázek průměrnou dobu 300,4 s oproti 342,6 s Ornithu. Při omezení také bodů pouze na Windows vychází GPT-OSS na 78,2 a Ornith na 76,3; v samotné fyzice na 69,5 a 67,5. Pořadí této těsné dvojice tedy záleží i na zahrnutí Linuxu. Qwen latest zde trvá 306,1 s a obsahově zaostává; pro fyziku tedy není automaticky lepší kompromis. Qwen 4B je se 215,1 s levnější časově, ale kvalitou fyziky níže. Pro jednoduché výpočty `3_3` a `3_5` je naopak jeho poměr rychlosti a výsledku dobrý. Gemma potřebuje 232,4 s a má slabší fyzikální průměr. Jde o čas celé odpovědi, nikoli rychlost generování tokenů.

### Školní všeobecný přehled: flow 3

Qwen latest, Ornith a GPT-OSS vycházejí prakticky vyrovnaně. Qwen latest má navíc dokončené odpovědi z obou strojů, ostatní dva pouze z Windows. Biologické jádro „rostliny dýchají i ve dne“ modely obvykle znají; chyby vznikají při vysvětlování čisté a hrubé produkce kyslíku. Nejslabší je zeměpis: model může správně jmenovat sklon osy a současně uvést nesprávný měsíc přísluní nebo chybnou orientaci polokoulí.

Pro kontrolu: v Austrálii je v červenci zima a přísluní připadá na začátek ledna. Sklon osy je přibližně 23,4° vůči kolmici k rovině oběhu, nikoli vůči samotné rovině. Viz [NASA: roční období a geometrie oběhu](https://science.nasa.gov/science-research/earth-science/milankovitch-orbital-cycles-and-their-role-in-earths-climate/). Gemma chybně uvádí červen; Qwen 4B se mezi běhy pohybuje mezi prosincem a únorem. Na školní elektroniku a matematiku lze Qwen 4B hodnotit podstatně lépe než na geografická fakta.

Tematické průměry bez inicializačních otázek:

| Model | Obecné: flow 1 | Fyzika: flow 2 | Školní: flow 3 | Nerd: 6 otázek |
| --- | --- | --- | --- | --- |
| qwen3.5:4b | 15,6 | 53,6 | 78,0 | 65,6 |
| qwen3.5:latest | 22,1 | 62,5 | 87,1 | 72,8 |
| gpt-oss:latest | neúplné | 66,2 | 86,8 | 76,0 |
| ornith:9b | neúplné | 67,5 | 87,0 | 76,3 |
| gemma4:latest | 23,8 | 52,8 | 65,5 | 62,7 |

„Nerd“ = čtyři otázky flow 2 + elektronika `3_3` + matematika `3_5`, každá se stejnou vahou. Neúplná sada obecných otázek nemá souhrnný průměr. Ostatní průměry mají všechny tematické otázky, ale nestejné pokrytí platforem; zvláště těsné pořadí proto není robustní.

## 2. Jak obstály jednotlivé modely

### qwen3.5:4b

Nejrychlejší model a zároveň nejúplněji zdokumentovaný společně s Qwen latest. Dobře počítá základní obvody a řeší odmocniny; v biologii vystihne základ. Ve fyzice správné vzorce často doprovází nesprávná interpretace. Obecná česká faktografie je velmi slabá: falešné právní výklady, chybná data invaze a smyšlená Čapkova díla. Na Windows má Maxwellův výklad výrazně horší než na Linuxu. Vhodný z tohoto vzorku hlavně pro jednoduché ověřitelné úlohy, ne jako zdroj faktů.

### qwen3.5:latest

Lepší než 4B zejména ve fyzice a zeměpisu, silný v elektronice a matematice. Ani větší model však nezvládá spolehlivě české právo a literaturu. U Čapka se objevují opakované opravy, další halucinace a nedokončený konec. Ve fyzice jsou problémem přehnané závěry a chybné detaily. Je znatelně pomalejší než 4B; nejlepší uplatnění v tomto testu má ve školní sadě, nikoli ve flow 1.

### gpt-oss:latest

Dobré relativní výsledky fyziky, velmi dobré výpočty; občas významné věcné nebo rozměrové chyby. Například fyzikální odhad teploty malé černé díry na Linuxu neodpovídá ani uvedenému vzorci. Provozní spolehlivost je samostatná slabina: Windows flow 1 má po zahřátí prázdnou odpověď, jeden linuxový report přímo obsahuje `RemoteDisconnected`, další končí u prázdné inicializační sekce. Úspěšné další běhy dokazují, že model odpovídat umí, nikoli že příčina výpadků byla odstraněna. Ze samotných reportů nelze určit, zda šlo o server, limit generování či jinou konfiguraci. Na právo, cestování, historii a Čapka nemáme plnou hodnotitelnou sadu.

### ornith:9b

Relativně nejlepší fyzikální průměr a velmi dobrá školní sada. Nejlepší odpověď na Hawkingovo záření v tomto vzorku, slušné Maxwellovy rovnice, ale výrazně slabší Verlinde. Odpovědi jsou dlouhé a fyzika na Windows nejpomalejší ze všech pěti modelů. Ve flow 1 není zastoupen; na Linuxu má v jednom fyzikálním reportu pouze pět prázdných sekcí bez časů. Z nich nelze odvozovat jeho rychlost ani známkovat pět neúspěšných odpovědí.

### gemma4:latest

Výsledky jsou nerovnoměrné: elektronika dobrá, zeměpis a část fyziky slabé. Na Windows v Maxwellových rovnicích vynechává jednu požadovanou rovnici a nahrazuje ji kontinuitou. Obecný průměr vychází relativně nejvýše, ale absolutně špatně a pouze na Linuxu. **Ve všech čtyřech měřených inicializacích odpovídá `no` místo `agama`**, takže rychlý start zde neznamená splnění pokynu. V češtině má výrazné jazykové deformace, které někdy zhoršují i význam.

### Rychlost věcných odpovědí

Medián doby v sekundách; v závorce počet dokončených neprázdných odpovědí. Nezahrnuje Q1. Srovnávat je vhodné stejný model a flow, nikoli celkový medián přes různé sady. Opakované běhy jsou v počtu zahrnuté.

| Model | Flow | Linux: medián s (n) | Windows: medián s (n) |
| --- | --- | --- | --- |
| qwen3.5:4b | 1 | 61,8 (8) | 93,6 (4) |
| qwen3.5:4b | 2 | 214,7 (12) | 242,8 (4) |
| qwen3.5:4b | 3 | 150,5 (4) | 152,6 (4) |
| qwen3.5:latest | 1 | 82,3 (8) | 140,4 (4) |
| qwen3.5:latest | 2 | 346,5 (12) | 358,8 (4) |
| qwen3.5:latest | 3 | 193,2 (4) | 200,2 (4) |
| gpt-oss:latest | 1 | — | — |
| gpt-oss:latest | 2 | 258,5 (4) | 315,6 (4) |
| gpt-oss:latest | 3 | — | 266,7 (4) |
| ornith:9b | 1 | — | — |
| ornith:9b | 2 | — | 412,0 (4) |
| ornith:9b | 3 | — | 220,3 (4) |
| gemma4:latest | 1 | 66,9 (4) | — |
| gemma4:latest | 2 | 198,8 (4) | 246,2 (4) |
| gemma4:latest | 3 | — | 182,0 (4) |

Prázdný výstup GPT-OSS `1_2` na Windows trval **355,867 s** a je z tabulky úspěšných výstupů vynechán, nikoli zatajen či započten jako rychlá odpověď.

## 3. Windows, Linux a náběh modelů

Podle zadavatele: **Linux: Intel i7, 16 GB RAM; Windows: Intel i7, 32 GB RAM. Verze Ollamy i modelů by měly být stejné.** Přesné typy/generace CPU, GPU a VRAM, kvantizace, zatížení a modelové digesty nejsou doloženy. Výsledek proto porovnává dvě konkrétní sestavy; neizoluje vliv operačního systému. Větší RAM sama o sobě neznamená rychlejší inference.

Pro férovější porovnání rychlosti páruji vždy stejný model, flow a otázku Q2–Q5: čas Windows dělím mediánem časů Linuxu a nakonec beru medián těchto poměrů. Poměr 1,12 znamená, že Windows potřeboval o 12 % delší čas. Nejde o podíl dvou celkových mediánů.

| Model | Počet různých párovaných otázek | Medián Windows / Linux | Výklad |
| --- | --- | --- | --- |
| qwen3.5:4b | 12 | 1,123 | Windows přibližně o 12 % déle |
| qwen3.5:latest | 12 | 1,128 | Windows přibližně o 13 % déle |
| gpt-oss:latest | 4, pouze flow 2 | 1,221 | Windows přibližně o 22 % déle |
| gemma4:latest | 4, pouze flow 2 | 1,271 | Windows přibližně o 27 % déle |
| ornith:9b | 0 | — | Chybí měřený Linux |

Linux je tedy většinou rychlejší, ale ne v každé otázce. U Qwenů má flow 3 na obou strojích podobné časy, zatímco flow 1 vykazuje větší rozdíly. Odpovědi mezi stroji nejsou totožné a mohou mít jinou délku; bez počtu tokenů nelze určit čistou rychlost generování ani celý rozdíl připsat HW. Dlouhá chybná odpověď není výkonnější jen proto, že má hodně textu.

### Inicializace: Q1 „agama“

Všechny hodnoty v sekundách: **medián; minimum–maximum; počet měření**.

| Model | Linux | Windows |
| --- | --- | --- |
| qwen3.5:4b | 5,3; 5,2–5,6; n=6 | 14,8; 8,8–15,3; n=3 |
| qwen3.5:latest | 11,8; 11,6–12,3; n=6 | 24,6; 24,3–27,1; n=3 |
| gpt-oss:latest | 26,0; 26,0–26,0; n=1 | 54,8; 52,4–55,9; n=3 |
| ornith:9b | — | 24,0; 21,6–26,4; n=2 |
| gemma4:latest | 13,1; 13,0–13,2; n=2 | 37,4; 33,6–41,1; n=2 |

Linuxové úspěšné startovací požadavky jsou výrazně kratší: přibližně 5 s pro 4B, 12 s pro Qwen latest, 13 s pro Gemmu a 26 s pro GPT-OSS. Windows vychází přibližně na 15, 25, 37 a 55 s; Ornith na Windows přibližně 24 s.

To jsou doby celého startovacího požadavku, **nikoli izolovaná měření načtení modelu do paměti**. Není doloženo, že model byl před každým během skutečně uvolněn z RAM/VRAM. Může se projevit cache, pořadí modelů i délka zpracování požadavku. U Gemmy navíc měříme dokončenou, ale nesprávnou odpověď `no`. U GPT-OSS jsou v tabulce pouze dokončené inicializace; neúspěchy a prázdné sekce uvedené výše se do mediánu nezapočítávají. Nízký počet měření brání obecným závěrům o spolehlivosti startu.

## 4. Konzistence mezi reporty

**Qweny jsou na Linuxu obsahově velmi konzistentní:** pro každý z obou modelů jsou všechny odpovědi flow 1 ve dvou reportech totožné a všechny odpovědi flow 2 ve třech reportech totožné. Porovnání se týká textu odpovědi po odstranění reportových časů a oddělovačů; nejde pouze o stejný závěr. Shodují se i chyby. Časové údaje se mění, takže obsahová reprodukovatelnost neznamená totožnou dobu výpočtu. U flow 3 je jen jeden linuxový report, opakovatelnost na témže stroji z něj hodnotit nelze.

**Linux proti Windows má odlišné texty a někdy i kvalitu.** Výrazné příklady:

- Qwen 4B, Maxwell: 70 bodů Linux proti 48 Windows; na Windows přibývá chybná rovnice.
- Gemma, Maxwell: 72 proti 40; Windows zamění jednu z požadovaných čtyř rovnic.
- Qwen latest, zeměpis: 88 proti 78; na Windows přibývá chybný den přísluní. Otázka chtěla měsíc, proto nejde o úplné selhání.
- Qweny, obecná faktografie: různá tvrzení a různé halucinace, ale konzistentně nízká použitelnost.
- Gemma, inicializace: konzistentní `no` ve čtyřech dokončených případech.

**Seed 42 a nenulová teplota nejsou v rozporu s totožným textem.** Seed inicializuje pseudonáhodné vzorkování; při stejných podmínkách může i nenulová temperature vést ke stejnému výsledku. Stejný seed však není zárukou shodného textu mezi různými sestavami či odlišnými verzemi promptu. Z reportů nelze rozhodnout, zda rozdíly způsobila numerika backendu, změna flow, kontextu nebo jiného nastavení. Podle zadavatele by modely a Ollama měly být stejné; bez přesných digestů a úplné konfigurace to nelze ověřit.

Současné soubory úloh uvádějí pro Q1 temperature 0,1 a pro ostatní otázky 0,5, limit generování 2048 a kontext 4096. Starší verze flow však nelze z pouhého názvu reportu plně rekonstruovat. Několik fyzikálních odpovědí i odpověď Qwen latest o Čapkovi končí uprostřed výkladu. Limit délky je možná příčina, ale bez `done_reason` a počtu tokenů ji nelze potvrdit. Hodnocení zde platí pro doručený text, nikoli pro hypotetické dokončení.

Pro další srovnání by pomohlo uložit přesný prompt a konfiguraci, digest modelu, specifikaci CPU/GPU, `load_duration`, počet generovaných tokenů a důvod ukončení. Pro ověření stability kvality přidat více seedů; opakovaný seed 42 na stejném stroji v této sadě často jen opakuje tutéž odpověď.

### Kontrolovatelnost přidělených bodů

Následují výchozí ruční známky před průměrováním platforem. Opakované totožné linuxové texty mají stejné známky. Všechny hodnoty v závěrečné tabulce jsou z těchto řádků; Q1 se hodnotí samostatně podle pokynu.

| Model | Flow | Platforma | Q2 | Q3 | Q4 | Q5 |
| --- | --- | --- | --- | --- | --- | --- |
| qwen3.5:4b | 1 | Linux | 5 | 30 | 25 | 15 |
| qwen3.5:4b | 1 | Windows | 12 | 20 | 15 | 3 |
| qwen3.5:4b | 2 | Linux | 62 | 43 | 70 | 55 |
| qwen3.5:4b | 2 | Windows | 56 | 45 | 48 | 50 |
| qwen3.5:4b | 3 | Linux | 76 | 92 | 62 | 94 |
| qwen3.5:4b | 3 | Windows | 78 | 86 | 50 | 86 |
| qwen3.5:latest | 1 | Linux | 8 | 25 | 48 | 10 |
| qwen3.5:latest | 1 | Windows | 8 | 32 | 38 | 8 |
| qwen3.5:latest | 2 | Linux | 60 | 57 | 74 | 57 |
| qwen3.5:latest | 2 | Windows | 64 | 66 | 68 | 54 |
| qwen3.5:latest | 3 | Linux | 84 | 95 | 88 | 88 |
| qwen3.5:latest | 3 | Windows | 74 | 96 | 78 | 94 |
| gpt-oss:latest | 1 | Windows | 1 | — | — | — |
| gpt-oss:latest | 2 | Linux | 64 | 67 | 67 | 54 |
| gpt-oss:latest | 2 | Windows | 74 | 72 | 70 | 62 |
| gpt-oss:latest | 3 | Windows | 78 | 96 | 78 | 95 |
| ornith:9b | 2 | Windows | 73 | 49 | 76 | 72 |
| ornith:9b | 3 | Windows | 84 | 94 | 76 | 94 |
| gemma4:latest | 1 | Linux | 8 | 20 | 55 | 12 |
| gemma4:latest | 2 | Linux | 43 | 48 | 72 | 54 |
| gemma4:latest | 2 | Windows | 55 | 58 | 40 | 52 |
| gemma4:latest | 3 | Windows | 55 | 95 | 42 | 70 |

## 5. Souhrnná tabulka: body 1–99

Identifikátor je `flow_otázka`. `1_1`, `2_1`, `3_1` = init „agama“; `1_2` právo, `1_3` cesta, `1_4` rok 1968, `1_5` Čapek; `2_2` entropie, `2_3` Verlinde, `2_4` Maxwell, `2_5` Hawking; `3_2` biologie, `3_3` elektronika, `3_4` zeměpis, `3_5` matematika.

Půlbody vznikají průměrem Linuxu a Windows, nikoli jemnější přesností úsudku. **— = chybí hodnotitelný výstup.** Gemma flow 1 je pouze Linux; GPT-OSS a Ornith flow 3 pouze Windows; Ornith flow 2 pouze Windows. GPT-OSS `1_2` je pouze prázdný výstup z Windows. Skóre 99 za init u GPT-OSS platí pro dokončené odpovědi a nepopírá zaznamenané technické neúspěchy. Záměrně nepočítám celkové pořadí přes všech 15 sloupců: odměňovalo by init a zkreslovalo chybějící data.

| Model | 1_1 | 1_2 | 1_3 | 1_4 | 1_5 | 2_1 | 2_2 | 2_3 | 2_4 | 2_5 | 3_1 | 3_2 | 3_3 | 3_4 | 3_5 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| qwen3.5:4b | 99 | 8,5 | 25 | 20 | 9 | 99 | 59 | 44 | 59 | 52,5 | 99 | 77 | 89 | 56 | 90 |
| qwen3.5:latest | 99 | 8 | 28,5 | 43 | 9 | 99 | 62 | 61,5 | 71 | 55,5 | 99 | 79 | 95,5 | 83 | 91 |
| gpt-oss:latest | 99 | 1 | — | — | — | 99 | 69 | 69,5 | 68,5 | 58 | 99 | 78 | 96 | 78 | 95 |
| ornith:9b | — | — | — | — | — | 99 | 73 | 49 | 76 | 72 | 99 | 84 | 94 | 76 | 94 |
| gemma4:latest | 1 | 8 | 20 | 55 | 12 | 1 | 49 | 53 | 56 | 53 | 1 | 55 | 95 | 42 | 70 |
