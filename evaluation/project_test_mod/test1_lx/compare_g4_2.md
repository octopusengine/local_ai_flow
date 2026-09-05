Model: gemma4:latest | Parametry: task_base.json, cz | temperature: 0.5 | num_predict: 2048 | num_ctx: 4096 | repeat_penalty: 1.1 | think: false | seed: 253563  
Čas: 147,3 s | Tokeny/s: ≈ 9,8 (odhad, 3 znaky/token)

---

## Porovnání TCP a UDP

TCP (Transmission Control Protocol) a UDP (User Datagram Protocol) jsou dva nejčastěji používané protokoly na vrstvě přepravy (Transport Layer) Internetového protokolu souboru (IP). Oba slouží k odesílání dat mezi aplikacemi na síti, ale liší se zásadním způsobem, jak tuto službu zajišťují.

Níže je podrobné srovnání podle požadovaných kritérií.

### Porovnávací tabulka

| Kritérium | TCP (Transmission Control Protocol) | UDP (User Datagram Protocol) |
| :--- | :--- | :--- |
| **Navázání spojení** | **Spojovací (Connection-Oriented)** – Vyžaduje navázání spolehlivého spojení pomocí tzv. *útrojování* (Three-Way Handshake: SYN, SYN-ACK, ACK). | **Bezspojovací (Connectionless)** – Nepotřebuje navazovat žádné předchozí spojení; prostě odesílá datový balík (datagram) bez kontroly přijetí. |
| **Spolehlivost doručení** | **Vysoká spolehlivost.** Zajišťuje dodání dat pomocí potvrzení (ACK). Pokud se data nezobrazí, protokoly automaticky opakují odesílání. | **Nízká/Žádná spolehlivost.** Nezajišťuje potvrzení. Pokud balík zničí nebo se ztratí v síti, UDP o tom neví a nepokouší se ho znovu odeslat. |
| **Pořadí dat** | **Zaručeno pořadí.** TCP číslovaná sekvence zajišťuje, že data budou přijata v přesném pořadí, ve kterém byla odeslána. | **Nezaručené pořadí.** Balíky mohou dorazit v libovolném pořadí, bez ohledu na pořadí odeslání. Aplikace musí pořadí sama řešit. |
| **Kontrola přetížení (Flow Control)** | **Ano.** Reguluje rychlost odesílání tak, aby nepřekročila přijímací kapacitu příjemce. | **Ne.** Odesílá data bez ohledu na to, zda je příjemce připraven ji zpracovat. |
| **Kontrola zácpy (Congestion Control)** | **Ano.** Aktivně monitoruje stav sítě a zpomaluje odesílání v případě detekce přetížení sítě. | **Ne.** Může přispět k zácpě, protože nezná síťové podmínky. |
| **Přehledná rychlost** | Pomalejší kvůli režii (handshake, potvrzení, kontroly). | Rychlejší, protože je minimalistický a nemá režijní overhead. |
| **Typické použití** | Webový provoz (HTTP/HTTPS), E-mail (SMTP), Přenos souborů (FTP) – kde je kritická integrita dat. | Streaming videa/zvuku, Online hry, DNS dotazy – kde je časovost důležitější než ztráta několika datových bodů. |

***

### Podrobný rozbor rozdílů

#### 1. Navázání spojení (Connection Management)
* **TCP:** Je *spojovací*. Před výměnou jakýchkoli dat musí být mezi odesílatelem a příjemcem navázáno virtuální, spolehlivé kanálové spojení. Tento proces se provádí pomocí tzv. "útrojování" (Three-Way Handshake).
* **UDP:** Je *bezspojovací*. Je to jednoduše vysílání datového balíku (datagramu) do síti, jako byste odeslali poukou poštovníčku bez předchozího kontaktu.

#### 2. Spolehlivost a Pořadí
* **TCP:** Zajišťuje *spolehlivost* tím, že každé potvrzení (ACK) je požadováno. Pokud ACK ned přijde v daném časovém intervalu, TCP automaticky opakuje odeslání datového segmentu. Také zajišťuje, že i když balíky dorazí v nepořádku, na vyšší vrstvě budou zrekonstruovány správně a v pořadí.
* **UDP:** Je *bezgarantované*. Pokud se paket změní nebo se ztratí v síti, UDP to nezjistí a nepokouší se nic napravit.

***

### Je UDP vždy rychlejší než TCP?

**Ne, UDP není *vždy* rychlejší než TCP.** Toto je klíčový koncept při porozumění oběma protokolům.

1. **UDP je teoreticky rychlejší (nižší latence):**
   Protože UDP nemá žádnou režii potřebnou pro navázání spojení, potvrzení o přijetí dat, nebo kontroly zácpy, je jeho *overhead* minimalní. V situacích, kdy je síť stabilní a nevyžaduje se absolutní spolehlivost (např. živý audio stream), bude UDP **rychlejší** než TCP, protože nemusí čekat na potvrzení nebo řešit retransmisi ztracených dat.

2. **TCP může být rychlejší v určitých podmínkách:**
   Pokud je síť nestabilní a často dochází k ztrátě paketů, bude TCP *vcelku* spolehlivější. Ačkoli proces opravy (retransmisi) zpomalí přenos dat oproti UDP, nakonec zajistí, že data dorazí kompletní. Pokud by aplikace potřebovala naprosto nekompletní nebo chybně seřazené údaje (např. video stream), které jsou pro uživatele méně důležité než časovost, může být vyšší režie TCP vnímána jako zpoždění.

**Závěr:**
* **UDP je rychlejší *v ideálním stavu sítě*, protože nemá žádnou režii.**
* **TCP je spolehlivější a zajišťuje integritu dat za cenu vyššího provozního nákladu (overhead) a potenciálního zpoždění při chybách v síti.**