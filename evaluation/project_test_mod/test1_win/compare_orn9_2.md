Model: ornith:9b | Parametry: task_base.json, cz | temperature: 0.5 | num_predict: 2048 | num_ctx: 4096 | repeat_penalty: 1.1 | think: false | seed: 314541  
Čas: 176,0 s | Tokeny/s: ≈ 5,3 (odhad, 3 znaky/token)

---

Zde je přehledné srovnání protokolu **TCP** (Transmission Control Protocol) a **UDP** (User Datagram Protocol), které pokrývá vaše dotazy ohledně navázání spojení, spolehlivosti, pořadí dat i rychlosti.

### Srovnávací tabulka: TCP vs. UDP

| Kritérium | **TCP** (Transmission Control Protocol) | **UDP** (User Datagram Protocol) |
| :--- | :--- | :--- |
| **Navázání spojení** | **Ano.** Před передачей dat se provede „trojní zápotce" (handshake), kdy si strany ověří, že jsou připraveny k komunikaci. | **Ne.** Datagramy se odesílají okamžitě bez předchozího zřizování spojení. |
| **Spolehlivost doručení** | **Vysoká (garantovaná).** Pokud paket nezarruší, TCP ho automaticky pozmocňuje a kontroluje jeho integrity pomocí cyklické ověřovací součty (checksum). | **Nízká (negarantovaná).** UDP nekontroluje, zda byl paket doručen, ani zda není poškozený. Ztracené pakety zůstanou nezvrácené. |
| **Pořadí dat** | **Garantováno.** TCP zajišťuje, že data přijdou v pořadí, ve kterém byly odeslány (použitím sekvencí čísel). | **Není garantováno.** Pakety mohou dorazit v libovolném pořadí nebo jich může chybět část. Aplikace si musí poradit sama. |
| **Typické použití** | Webové stránky (HTTP/HTTPS), e-mail (SMTP, IMAP), přenos souborů (FTP), SSH, streamování videa naživo (kde je důležitá integrita celého toku). | DNS vyhledávání, videohry (snížení zpoždění místo čekání na potvrzení), VoIP telefonie, live streamy, DHCP. |
| **Rychlost** | Pomalejší kvůli mechanismům ověření a pozmocňování. | Rychlejší díky absenci handshakeu a potvrzení doručení. |

### Je UDP vždy rychlejší než TCP?

**Ne, ne vždy.** Ačkoliv je UDP obecně lehčí protokol s menším přenosovým headerem (20 vs. 40 bajtů u TCP), rychlost není jediným kritériem:

1.  **Zpoždění vs. propustnost:** UDP skutečně eliminuje zpoždění spojené s handshakeem a čekáním na potvrzení (ACK). To znamená, že první datový paket dorazí rychleji. Pokud ale potřebujete odeslat obrovské množství dat v pořádku (např. stahovat film), TCP je efektivnější díky mechanismu **windowing** (okení), který umožňuje odeslat více dat najednou a přitom si udržet vysokou propustnost spojení.
2.  **Ztráty paketů:** Pokud síť ztratí UDP pakety, aplikace musí data poslat znovu nebo zpracovat data v nesprávném pořadí. V takovém případě může být celkový čas přenosu u UDP delší než u TCP, který automaticky pozmocňuje chybějící části.
3.  **Kontext použití:** Pokud je síť stabilní a ztráty jsou minimální (např. lokální LAN), rozdíl v rychlosti může být nepatrný. Naopak v nestabilních sítích (mobilní data) může UDP působit pomaleji kvůli nezvráceným chybám.

**Závěr:** TCP je vhodný tam, kde je důležitá spolehlivost a pořadí dat, zatímco UDP je ideální pro aplikace, kde je kritické snížit zpoždění (latency) a tolerovat ztráty paketů (např. videohry).