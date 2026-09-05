Model: gemma4:latest | Parametry: task_base.json, cz | temperature: 0.5 | num_predict: 2048 | num_ctx: 4096 | repeat_penalty: 1.1 | think: false | seed: 72637  
Čas: 171,9 s | Tokeny/s: ≈ 8,1 (odhad, 3 znaky/token)

---

## Porovnání protokolů TCP a UDP

TCP (Transmission Control Protocol) a UDP (User Datagram Protocol) jsou dva základní protokoly používané v internetových komunikacích na transportové vrstvě modelu OSI. Oba slouží k odesílání dat mezi aplikacemi, ale liší se zásadními principy fungování, což je určeno jejich specifickým použitím.

Níže naleznete srovnání podle požadovaných kritérií a vysvětlení rychlosti.

---

### Porovnávací tabulka

| Kritérium | TCP (Transmission Control Protocol) | UDP (User Datagram Protocol) |
| :--- | :--- | :--- |
| **Navázání spojení** | **Ano (Connection-Oriented)**: Vyžaduje třícestný handshake (SYN, SYN-ACK, ACK) pro navázání spolehlivého spojení. | **Ne (Connectionless)**: Pošle datový balíček (datagram) bez předchozího navázání spojení. Je to "send and forget". |
| **Spolehlivost doručení** | **Vysoká**: Zajišťuje spolehlivost pomocí potvrzení (ACK), retransmisi ztracených dat a kontrolních součtů. | **Nízká/Žádná**: Nezajišťuje spolehlivosti. Pokud balíček zmizí, neudělá nic pro jeho odeslání znovu. |
| **Pořadí dat** | **Zaručené**: Zajistí, že přijímací strana data dostane v přesném pořadí, ve kterém byla odeslána. | **Nezaručené**: Balíčky mohou dorazit v libovolném pořadí (pokud vůbec dorazí). Aplikace musí pořádek řešit sama. |
| **Řízení toku/Zácizení** | **Ano**: Má mechanismy pro řízení toku (Flow Control) a zácizení (Congestion Control), aby se zabránilo přetížení síti nebo příjemce. | **Ne**: Neobsahuje žádné mechanismy pro řízení toku ani zácizení – pošle data bez ohledu na stav cíle. |
| **Přehledný overhead** | Vyšší (kvůli hlavičce, handshake a ověření) | Nižší (jednodušší hlavička) |
| **Typické použití** | Webový provoz (HTTP/HTTPS), E-mail (SMTP), Přenos souborů (FTP). | Video/Audio streaming, Online hrací hry, DNS dotazy. |

---

### Podrobné vysvětlení rozdílů

#### 1. Navázání spojení
* **TCP:** Je *orientovaný na spojení*. Před jakýmkoliv přenosem dat musí být mezi dvěma koncovými body navázáno logické, spolehlivé spojení pomocí třícestného "potvrzení" (three-way handshake). Toto zajišťuje, že obě strany vědí, že jsou připraveny k výměně dat.
* **UDP:** Je *bezorientovaný na spojení*. Jednoduše pošle datový balíček (datagram) bez jakéhokoli předchozího "ohlášení".

#### 2. Spolehlivost doručení
* **TCP:** Je spolehlivý. Pokud odesílatel neobdrží potvrzení (ACK) pro konkrétní segment dat, automaticky ho **opakujete** (retransmisi). To zajišťuje, že data dorazí kompletní a v pořádku.
* **UDP:** Není spolehlivý. Je to „best-effort“ protokol. Pošlete balíček a zapomeňte na něj. Pokud se ztratí na cestě, UDP o tom automaticky neví a nic s tím nedělá.

#### 3. Pořadí dat
* **TCP:** Zajišťuje *řád*. I když data mohou v síti dorazit veškerém pořadí, TCP je zodpovědné za to, aby byla na cíli znovu uspořádána do původního posloupnosti před odesláním aplikaci.
* **UDP:** Nezajišťuje řád. Pokud pošlete balíček A, B a C, ale kvůli síťovým podmínkám dorazí v pořadí C, B, A, UDP to jen tak přijme – aplikace musí sama zjistit, že je něco chybějící nebo vyskakující z pořadí.

---

### Je UDP vždy rychlejší než TCP?

**Ne.** Je třeba rozlišovat mezi *teoretickou* rychlostí a *praktickým výkonem*.

1. **Teoreticky (Minimalní náклад):**
   UDP je **vždy teoreticky snazší a rychlejší na úrovni protokolu**, protože nemá žádný režijní overhead: neprovádí handshake, nezkoumává ztráty, neřeší retransmisi ani řízení toku. To mu dává nižší latenci pro *každý jednotlivý balíček*.

2. **Prakticky (Celkový průchod dat):**
   TCP je často **efektivnější a rychlejší při přenosu velkého množství dat**, protože jeho mechanismy zajišťují, že data dorazí celá a v pořádku. Ztráty dat nebo nepořádky by u UDP vedly k nutnosti, aby aplikace sama řešila chyby (co je složitější a může vést ke zdržení), zatímco TCP tyto chyby automaticky opravuje na úrovni protokolu.

**Závěr:**
* **Pokud je nejdůležitější minimalizovat latenci pro každý balíček, i za cenu ztráty dat (např. živý videostream):** UDP je lepší volba.
* **Pokud je nejdůležitější spolehlivost a kompletní přenos dat bez chyb (např. stažení souboru nebo webová stránka):** TCP je nutnější, i když přidá mírný režijní náklad kvůli ověření.