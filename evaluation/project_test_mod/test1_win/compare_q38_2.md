Model: qwen3.8:latest | Parametry: task_base.json, cz | temperature: 0.5 | num_predict: 2048 | num_ctx: 4096 | repeat_penalty: 1.1 | think: false | seed: 368566  
Čas: 784,1 s | Tokeny/s: ≈ 1,7 (odhad, 3 znaky/token)

---

Zde je srovnání protokolů TCP a UDP podle požadovaných kritérií:

| Kritérium | TCP (Transmission Control Protocol) | UDP (User Datagram Protocol) |
| :--- | :--- | :--- |
| **Navázání spojení** | **Spojení orientovaný.** Před přenosem dat je nutné navázat spojení pomocí „třech kliků“ (SYN, SYN-ACK, ACK). Po dokončení přenosu se spojení ukončí. | **Bezspojení.** Navazování spojení není potřeba. Odesílatel pouze pošle datagram a nečeká na potvrzení od příjemce. |
| **Spolehlivost doručení** | **Vysoká.** Protokol zajišťuje, že data dorazí k příjemci. Pokud je paket ztracen, požádá o opakování (retransmisi). Zkontroluje kontrolní součty a potvrzuje přijetí dat (ACK). | **Nízka / Žádná záruka.** Protokol nezajišťuje doručení. Pokud je paket ztracen nebo poškozen, jednoduše se zahodí. Neexistuje mechanismus potvrzení příjmu ani opakování. |
| **Pořadí dat** | **Zaručeno.** TCP řadí pakety do správného pořadí, ve kterém byly odeslány, i pokud by v síti dorazily v jiném pořadí (díky sekvencovacím číslům). | **Nezaručeno.** Pakety mohou dorazit v libovolném pořadí. Příjemce si musí sám poradit s případným rozptýlením dat, pokud je to pro aplikaci nutné. |
| **Typické použití** | Webové prohlížeče (HTTP/HTTPS), e-mail (SMTP, POP3, IMAP), přenos souborů (FTP), vzdálené přihlášení (SSH). Všechny aplikace, kde je důležitá integrita a úplnost dat. | Streamování médií (video/audio), online hry, VoIP (telefonie přes internet), DNS dotazy, IoT senzory. Aplikace, kde je důležitější nízká latence než dokonalost dat. |

### Je UDP vždy rychlejší než TCP?

**Ne, není to pravda.** Tvrzení, že UDP je *vždy* rychlejší, je zjednodušením a často i chybou. Rychlost závisí na kontextu a definici „rychlosti“ (latence vs. throughput).

1.  **Nižší přehledová nákladnost (Overhead):**
    *   UDP má menší hlavičku (8 bajtů) oproti TCP (20+ bajtů), což znamená, že více prostoru v paketu využije užitečná data.
    *   UDP nevyžaduje potvrzení příjmu (ACK) a opakování ztracených paketů. To šetří čas a síťovou kapacitu.

2.  **Kdy je UDP skutečně rychlejší?**
    *   Při **krátkých, jednorázových dotazech** (např. DNS), kde by navázání TCP spojení zabralo více času než samotné přenos dat.
    *   V aplikacích s **reálným časem** (video streamy, hry), kde je důležitá nízká latence. Ztracený paket se v UDP okamžitě zahodí a aplikace pokračuje dál. U TCP by se čekalo na opakování ztraceného paketu, což by způsobilo zpoždění (stuttering) u následujících dat.

3.  **Kdy může být TCP rychlejší nebo srovnatelné?**
    *   Při **přenosu velkých objemů dat** v stabilní síti: Moderní implementace TCP jsou velmi optimalizované. Pokud je síť spolehlivá a ztráty paketů minimální, rozdíl v rychlosti (throughput) mezi TCP a UDP může být zanedbatelný.
    *   **Ztráty dat:** V síti s vysokou mírou ztrát paketů bude TCP pomalejší kvůli opakování, ale **UDP nebude nutně „rychlejší“** v tom smyslu, že by aplikace dostala užitečná data – spíše by dostávala poškozená nebo neúplná data. Pokud aplikace potřebuje opravit chyby (např. video dekodér), může být celkový výsledek horší než u TCP, které zaručuje správnost.
    *   **Síťové podmínky:** V některých sítích mohou routery a firewally lépe optimalizovat tok TCP díky mechanizmům ovládání toku (flow control) a okénkovým mechanismům, což může vést k vyššímu celkovému throughputu než u UDP, který může „zaplavovat“ síť datagramy bez ohledu na kapacitu příjemce.

**Závěr:**
UDP je **obecně efektivnější pro nízkou latenci a jednoduché přenosy**, protože nemá přehledovou nákladnost potvrzení a pořadí. Ale není „vždy“ rychlejší – v kontextu celkového výkonu aplikace (kde se počít i správnost dat) nebo v síti s vysokými ztrátami může být TCP vhodnější, i když má vyšší latenci na jednotku operace. Pro většinu uživatelských aplikací je rozdílný hlavně v tom, **jak** data doručuje (spolehlivě vs. co nejrychleji, i kdyby byla poškozená).