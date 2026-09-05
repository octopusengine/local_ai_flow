Model: qwen3.5:4b | Parametry: task_base.json, cz | temperature: 0.5 | num_predict: 2048 | num_ctx: 4096 | repeat_penalty: 1.1 | think: false | seed: 272290  
Čas: 81,9 s | Tokeny/s: ≈ 10,6 (odhad, 3 znaky/token)

---

Zde porovnání protokolu TCP (Transmission Control Protocol) a UDP (User Datagram Protocol) podle vybraných kritérií:

| Kritérium | TCP (Transmission Control Protocol) | UDP (User Datagram Protocol) |
| :--- | :--- | :--- |
| **Navázání spojení** | Vyžaduje fázi „handshake" (trojitého handshake). Před přenosem dat musí být navázáno spolehlivé spojení mezi zdrojem a cílem. | Nevyžaduje navazování spojení. Datové balíčky jsou posílány okamžitě bez předchozí komunikace (bez jakéhokoliv „handshake"). |
| **Spolehlivost doručení** | Zaručuje spolehlivé doručení pomocí potvrzení o přijetí (ACK), automatického opakování při ztrátě dat a opravy chybových znaků. | Nespoléhlivý protokol. Neexistují mechanismy pro potvrzení, opravu chyb ani automatické opakování posílaného dat. |
| **Pořadí dat** | Zaručuje správné pořadí doručení dat pomocí sekvencovního čtení a reasemblování na straně cíle. | Neexistuje záruka, že balíčky budou přijaty v pořadí, ve kterém byly odeslány. |
| **Typické použití** | Aplikace vyžadující přesnost a celistvost dat: WWW (HTTP), e-mail (SMTP), FTP, SSH, streamování videa/audio s vysokou kvalitou. | Aplikace tolerantní ztrátám dat nebo vyžadující nízké latence: hlasové/základné video streaming (VoIP), DNS query, online hry, DHCP. |

**Odpověď na otázku: Je UDP vždy rychlejší než TCP?**

Ne, **UDP není vždy rychlejší**. Rychlost odeslání dat se v praxi může lišit podle kontextu sítě a zatížení:

1.  **Teoretická rychlost (latence):** Ano, UDP je často rychlejší na začátku komunikace nebo ve situacích s vysokým tlakem, protože vyřazuje časotravné fáze navazování spojení a potvrzení o přijetí. TCP musí nejprve provést handshake a poté čekat na ACK před každou další částí dat, což zvyšuje latenci (zpoždění).
2.  **Praxe při vysokém zatížení:** Pokud je síť velmi zabavená nebo jsou vysílána obrovské množství datových balíčků v krátkých intervalech, může TCP být až rychlejší díky svým mechanismům řízení proudu (flow control) a řízení přetížení. UDP má tyto mechanizmy chybí, což může vést k masivní ztrátě balíčků na síti nebo jejich „zaseknutí" v bufferu odesílatele, pokud se nevytřídí (queue).
3.  **Optimalizace jadr:** Moderní operační systémy mají pro TCP a UDP různé optimalizační cesty ve jádru operace sicejsi (kernel), což může vést k situacím, kdy za stejných podmínek je odeslání přes TCP efektivnější.

**Závěr:** Rychlost je závislá na typu síťového provozu a podmínkách přenosu dat. UDP snižuje zpoždění odstraněním nadbytečných kroků, ale TCP může být rychlejší díky svému schopnosti řídat proudu a optimalizovat odesílání při vysokém zatížení sítě.