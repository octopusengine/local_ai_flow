Model: qwen3.5:latest | Parametry: task_base.json, cz | temperature: 0.5 | num_predict: 2048 | num_ctx: 4096 | repeat_penalty: 1.1 | think: false | seed: 112468  
Čas: 180,1 s | Tokeny/s: ≈ 6,1 (odhad, 3 znaky/token)

---

Zde je porovnání protokolu TCP (Transmission Control Protocol) a UDP (User Datagram Protocol) podle klíčových kritérií:

| Kritérium | TCP (Transmission Control Protocol) | UDP (User Datagram Protocol) | Vysvětlení rozdílu |
| :--- | :--- | :--- | :--- |
| **Navázání spojení** | **Ano.** Vyžaduje třífázový úvodní proces („handshake") před odesláním dat. Spojuje se s konkrétní cílovou adresou a portem. | **Ne.** Odešílá data okamžitě bez navazování spojení (fire-and-forget). Nemá žádný mechanismus pro ověř existence příjemce před odesláním. | TCP zajišťuje, že oba koncové body jsou připraveny na komunikaci; UDP to vynechává pro úsporu času a zdrojů. |
| **Spolehlivost doručení** | **Vysoká.** Zaručuje, že všechna data budou doručená bez chyb. Pokud paket ztratí nebo se poškodí, TCP jej automaticky požádá o přenos znovu (retransmise). | **Nízka/Nedoložená.** Neexistuje žádný mechanismus pro potvrzení přijetí ani opravy chybových datových paketů. Ztracené pakety zůstávají bez náhrady. | TCP je navržen tak, aby data byla kompletní; UDP předpokládá, že aplikace si s tím sama poradí (nebo to nevadí). |
| **Pořadí dat** | **Umožňuje.** Díky sekvenčním číslům a mechanismu retransmisi zajistí TCP správné pořadí doručení paketů. | **Nezaručuje.** Pakety mohou dorazit v libovolném pořadí (např. druhý před prvním), protože UDP je stream dat bez sekvenování. | Pokud aplikace potřebuje zachovat strukturu (jako text nebo soubor), TCP to řeší; pokud ne (např. video, kde chybějící rámeček nevadí), stačí UDP. |
| **Typické použití** | Web browsing (HTTP/HTTPS), e-mail (SMTP/IMAP), FTP, SSH, přenos velkých souborů. | Online hry v reálném čase, VoIP telefonie, video streamování (live TV), DNS dotazy, DHCP. | Kde je důležitá integrita dat a pořadí → TCP. KDE je důležitý okamžitý odzvuk i na úkor chybějících částí → UDP. |

### Je UDP vždy rychlejší než TCP?

**Ne, není to tak jednoduché.** Ačkoliv má UDP obecně nižší latenci a vyšší propustnost v ideálních podmínkách (kvůli absenci handshakeu a potvrzení), tvrzení, že je „vždy" rychlejší, neplatí ve všech scénářích:

1.  **Velikost dat:** Při přenosu velkého množství malých paketů může být TCP efektivnější díky mechanismům jako *Nagle's algorithm* nebo *Delayed ACK*, které sbírají data a snižují počet handshakeů na úrovni aplikace, což kompenzuje ztrátu času v potvrzovacích signálech (ACK).
2.  **Zatížení sítě:** V případě přetížené sítě může TCP díky svému mechanismu ošetření chyb (překladání rychlosti – *congestion control*) automaticálně zpomalit a stabilizovat tok dat, aby nedošlo k dalšímu ztrátám paketů. UDP v takovém případě bude stále vysílat plnou rychlost i nadále generující nevyužité nebo ztracené pakety, což nemusí být pro aplikaci „rychlejší" ve smyslu užitečného datového toku.
3.  **Závislost na implementaci:** Rychlost UDP je silně závislá na tom, jak si s ním aplikace poradí se ztrátami (např. v herních klientech). Pokud aplikace musí čekat na chybějící pakety a přehrávat obsah (buffering), rozdíl ve rychlosti oproti TCP může být minimální nebo nulový.

**Závěr:** UDP je obvykle rychlejší pro **časově citlivé aplikace**, kde se upouští od spolehlivosti, ale u aplikací vyžadujících integritu dat (jako web) bude TCP v reálném provozu často stejně rychlý nebo dokonce lepší díky optimalizaci přenosové vrstvy.