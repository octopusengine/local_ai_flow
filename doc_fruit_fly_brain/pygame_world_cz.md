# Moucha a cukr: jednoduchý svět s učením

## Spuštění

```powershell
.\venv\Scripts\python.exe pygame_world.py
```

Běžné spuštění začíná **od nuly**, s prázdnou Q tabulkou. Jde o samostatný
herní model učení. Původní FlyWire simulace zůstává v `pygame_brain.py` a tento
svět ji zatím neřídí ani neučí její biologické spoje.

## Svět, smysly, pohyb a cíl

| Prvek | Pravidlo |
|---|---|
| Svět | 30 × 30 čtvercových polí, neprůchodné okraje |
| Moucha | Fialové kolečko, jeden krok nahoru, doprava, dolů nebo doleva |
| Cukr | 24 oranžových polí na náhodných místech |
| Sebrání | Vstup na cukr ho spotřebuje; nový se objeví na volném náhodném poli |
| Senzor | Směr k nejbližšímu cukru do vzdálenosti 6 kroků, plus sousední okraje |
| Cíl | Nasbírat co nejvíce cukru s co nejméně zbytečnými kroky |
| Epizoda | Po 1 000 krocích nová mapa a pozice, naučená tabulka zůstává |

Vzdálenost je počet vodorovných a svislých kroků, takže senzor má tvar kosočtverce.
Moucha nezná celou mapu, vlastní globální souřadnice ani přesnou vzdálenost cukru.
Dostává jen hrubý směr: osm možností, případně „nic v dosahu“.
Ty jako pozorovatel vidíš všechny cukry; moucha je mimo svůj dosah nevnímá.

Senzor je záměrně umělá pomůcka, nikoli biologický model čichu nebo chuti.
Mimo dosah cukru je napevno nastavené náhodné hledání ve všech režimech.
Neučíme tedy celou smyslovou soustavu: agent se učí reagovat na dostupný místní signál.

Počáteční pohyb připomíná diskrétní náhodnou procházku. Není to fyzikální
Brownův pohyb ani simulace letu, nohou či svalů.

## Odměny a učení

- Sebrání cukru: **+10**.
- Každý krok: **−0,03**, také při sebrání cukru.
- Pokus odejít za okraj: dalších **−0,5**; moucha zůstane na místě.

Krok se sebráním tedy přinese celkem +9,97, náraz −0,53.
Za pouhé přiblížení k cukru není přidaná odměna.

Agent používá **Q-learning**: tabulku odhadů, jak výhodné je v určitém vjemu
udělat jednotlivé pohyby. Devět stavů směrového senzoru a čtyři bity okrajů
dávají 144 možných položek vjemu. Každá má čtyři Q hodnoty.

Po kroku v režimu Učení se aktualizuje jediná hodnota:

```text
Q(vjem, pohyb) ← Q + 0,12 × [odměna + 0,95 × max Q(další vjem) − Q]
```

Na posledním kroku epizody se budoucí člen vynechá.
Q hodnoty jsou odhady budoucí odměny, nikoli biologické synaptické váhy.
Vjem je zjednodušený: různá skutečná uspořádání mohou vypadat agentovi stejně.
Proto nejde o optimální plánovač a moucha může i po učení bloudit nebo se zacyklit.

Na začátku si v režimu Učení volí náhodný pohyb se 100% pravděpodobností.
S počtem učicích kroků podíl průzkumu exponenciálně klesá, nejníže na 5 %.
Zbytek voleb vychází z nejvyšší Q hodnoty; při shodě je výběr náhodný.
Bez cukrového signálu vždy hledá náhodně, bez ohledu na procento průzkumu.

## Ovládání a zobrazení

| Ovládání | Účinek |
|---|---|
| Učení | Pohyb, průzkum a aktualizace tabulky |
| Naučené | Použití dosavadní tabulky bez dalšího učení a bez průzkumu při dostupném signálu |
| Náhodné | Rovnoměrně náhodné pohyby, tabulka se nepoužívá ani nemění |
| Rychlost animace | 1–300 kroků za sekundu; nemění pravidla ani odměny |
| Pauza / mezerník | Pozastavení či pokračování; při úloze ji zruší |
| Nová mapa / N | Nový svět, znalosti zůstávají |
| Učit +50 000 kroků / T | Rychlý trénink po malých dávkách, okno zůstává ovladatelné |
| Porovnat / E | Samostatný test proti náhodné chůzi na šesti mapách |
| Uložit / S | Uložení tabulky a počtu učicích kroků |
| Načíst | Obnovení uloženého agenta, přepnutí do Naučené |
| Nové učení | Smazání znalostí v aktuálním sezení, návrat na začátek; uložený soubor se nemaže |
| Esc | Zavření okna |

Po zrychleném tréninku nebo porovnání se běžný pohyb pozastaví, aby byl čas
si výsledek přečíst. Pokračuj mezerníkem. Při zavření se agent automaticky
neukládá; chceš-li ho zachovat, použij nejprve **Uložit**.

Podbarvení kolem mouchy ukazuje dosah senzoru, žlutý kroužek právě zjištěný
nejbližší cukr a krátká fialová stopa poslední pohyby.
Panel Q hodnot ukazuje odhady pro současný vjem; když chybí signál, agent je ignoruje.

Graf vývoje používá bloky po 500 učicích krocích, přepočtené na cukry za 1 000 kroků.
Zobrazuje nejvýše posledních 60 bloků. Obsahuje i náhodný průzkum a střídání map,
proto může kolísat a nemusí trvale růst. Není sám o sobě důkazem zlepšení.

## Jak ověřujeme zlepšení

**Porovnat** vezme kopii současné tabulky a během testu ji neučí.
Na šesti pevně zvolených mapách vždy porovná 1 000 kroků náhodné chůze
s 1 000 kroky naučeného řízení. Oba začínají ze stejného rozmístění i pozice.
Po sběru se cukr dál doplňuje; protože řídicí strategie sbírají jinak,
nemusí mít svět po několika krocích stejnou podobu.

Hlavní metrika je **cukry za 1 000 kroků**, zprůměrovaná přes šest map.
Stejný uložený agent a stejné testovací seedy dávají stejný výsledek.
Opakování tlačítka beze změny agenta proto není nový nezávislý experiment.

Ověřený výsledek po 100 000 učicích krocích z čistého startu, trénovací seed 7:

| Řízení | Průměr cukrů / 1 000 kroků |
|---|---:|
| Náhodná chůze | 9,8 |
| Naučená tabulka | 66,7 |

V tomto testu je to přibližně 6,8× více. Dokládá to učení v našich jednoduchých
pravidlech, ne naučení skutečného mozku octomilky. Během ručního hraní může
výsledek vyjít jinak, protože měníš historii pohybů, map a tréninku.

## Tři první pokusy

### 1. Od nemotornosti k lepšímu hledání

1. Spusť nové učení a sleduj pohyb při 15 krocích za sekundu.
2. Stiskni Porovnat a poznamenej výsledek.
3. Dvakrát použij Učit +50 000 kroků a znovu Porovnat.
4. Přepni na Naučené a pokračuj mezerníkem. Porovnej pohyb s režimem Náhodné.

### 2. Pamatuje si mapu, nebo reaguje na signál?

1. Po tréninku přepni na Naučené.
2. Několikrát změň mapu tlačítkem Nová mapa.
3. Sleduj, zda se stále dokáže přibližovat k cukru v dosahu.

Tabulka nedostává globální souřadnice, proto nemůže prostě uložit trasu
„na této pozici jdi doprava“. Učí se reakce na směrové vjemy a okraje.

### 3. Kde jsou hranice naučeného chování?

1. Pozoruj mouchu v místě bez cukru v dosahu podbarvené oblasti.
2. Všimni si, že i naučené řízení zde hledá náhodně.
3. Sleduj, jak se změní pohyb po získání signálu a co dělá u okraje mapy.

Tím rozlišíš naučenou reakci na dostupný signál od chování, které jsme
naprogramovali jako základní průzkum. Zlepšení nemusí být monotónní a další
trénink může některé situace i dočasně zhoršit.

## Soubory na D:

- `pygame_world.py`: okno a ovládání.
- `grid_learning.py`: pravidla prostředí a Q-learning, použitelný i bez grafiky.
- `results/grid_world/agent.json`: ručně uložený agent; další Uložit ho přepíše.
- `results/grid_world/evaluation_*.json`: výsledky porovnání, seedy a kontrolní součet agenta.
- `results/grid_world/demo_agent.json`: oddělená naučená ukázka vytvořená při ověření.
- `results/grid_world/demo_evaluation.json`: výsledek ověřené ukázky.

Načtení obnovuje znalosti, nikoli přesně rozehraný svět a stav generátoru náhody.
Demo agent se při běžném startu automaticky nenačítá.

Ověření pravidel, učení, ukládání a ovládání:

```powershell
.\venv\Scripts\python.exe -m unittest test_grid_world -v
```

Pozdější propojení s FlyWire by vyžadovalo určit, jak herní senzor aktivuje
konkrétní vstupní neurony a jak jejich výstupy řídí pohyb. Učení biologických
vah by navíc potřebovalo vlastní pravidlo plasticity. Tato jednoduchá verze
zatím poskytuje prostředí, cíl, odměny a ověřitelný učicí mechanismus.
