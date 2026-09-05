Model: gpt-oss:latest | Parametry: task_base.json, cz | temperature: 0.5 | num_predict: 2048 | num_ctx: 4096 | repeat_penalty: 1.1 | think: false | seed: 427301  
Čas: 116,3 s | Tokeny/s: ≈ 6,8 (odhad, 3 znaky/token)

---

**Porovnání TCP a UDP**

| Kritérium | TCP (Transmission Control Protocol) | UDP (User Datagram Protocol) |
|-----------|-------------------------------------|------------------------------|
| **Navázání spojení** | 3‑way handshake (SYN → SYN‑ACK → ACK). Po navázaném spojení je udržována stavová tabulka a přenos se provádí v rámci tohoto spojení. | Přímý posílání dat bez žádného handshaku; není žádné „spojení“ – každé datagramové pole je samostatný paket. |
| **Spolehlivost doručení** | Zaručuje doručení: retransmise ztracených paketů, kontrola integrity (checksum), číslování sekvence a potvrzení (ACK). | Žádná garance; ztráty paketů nejsou automaticky zachyceny ani opakovaně odesílány. |
| **Pořadí dat** | Zachovává pořadí: pakety jsou číslovány, přijaté pakety se řazí podle sekvenčního čísla a případně retransmitují chybné nebo chybějící segmenty. | Pořadí není zaručeno; příjemce přijímá pakety tak, jak je dostane (může dojít k zamíchání). |
| **Typické použití** | Přenos dat, kde je důležitá úplnost a pořadí: HTTP/HTTPS, FTP, SMTP, SSH, databázové protokoly. | Pro aplikace tolerující ztrátu paketů nebo vyžadující nízkou latenci: VoIP, videokonference, online hry, DNS, streaming (např. RTP). |
| **Rychlost / Latence** | Vysoká režijní náročnost kvůli handshaku, sledování stavu a retransmisi; může být pomalejší při nízké latenci nebo v síťových podmínkách s vysokou ztrátou paketů. | Nízká režie – žádný handshake, žádná retransmise, menší overhead → obvykle nižší latence. |


### Je UDP vždy rychlejší než TCP?

Ne. **UDP má obecně nižší režii a může mít nižší latenci**, protože neprovádí handshake ani sledování stavu spojení. Nicméně:

1. **Ztráty paketů** – v síti s vysokou mírou ztrát mohou být UDP pakety opakovaně odesílány na aplikační úrovni, což může zvýšit celkový čas.
2. **Aplikační režie** – pokud aplikace musí implementovat vlastní kontrolu integrity a pořadí (např. pro streamování), může to přidat značnou zátěž.
3. **Síťové infrastruktury** – některé síťové zařízení mohou mít speciální optimalizace pro TCP (QoS, flow control) nebo omezit UDP provoz kvůli bezpečnosti.

Proto je rychlost závislá na konkrétním scénáři: v prostředí s nízkou ztrátou a kde aplikace nepotřebuje spolehlivost, může být UDP skutečně „rychlejší“. V jiných případech může TCP nabídnout lepší celkový výkon díky své spolehlivosti a správnému řízení toku.