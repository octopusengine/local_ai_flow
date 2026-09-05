Model: gpt-oss:latest | Parametry: task_base.json, cz | temperature: 0.5 | num_predict: 2048 | num_ctx: 4096 | repeat_penalty: 1.1 | think: false | seed: 687768  
Čas: 106,3 s | Tokeny/s: ≈ 5,8 (odhad, 3 znaky/token)

---

| Kritérium | TCP (Transmission Control Protocol) | UDP (User Datagram Protocol) |
|-----------|--------------------------------------|------------------------------|
| **Navázání spojení** | **Trojfázové handshake** – klient posílá SYN, server odpovídá SYN‑ACK a klient potvrzuje ACK. Vytváří se spolehlivé spojení před přenosem dat. | **Bez navázání spojení** – data se odesílají okamžitě jako samostatné datagramy; není žádná inicializační fáze. |
| **Spolehlivost doručení** | Zaručuje, že všechna data dorazí v pořádku nebo dojde k opakovanému přenosu po ztrátě paketů (retransmission). | Nebyla zajištěna – žádné potvrzení o příjmu a žádná retransmise. Při ztrátě paketu se nedělá nic. |
| **Pořadí dat** | Zachovává pořadí paketů; přijímač je schopen je přeskupit do správného řazení. | Pořadí není garantováno – příchozí pakety mohou dorazit v libovolném pořadí, případně i duplicitně. |
| **Typické použití** | Webové stránky (HTTP/HTTPS), e‑mail (SMTP, POP3, IMAP), souborové přenosy (FTP, SFTP), databázové spojení. | Streaming médií (audio/video), VoIP, online hry, DNS, DHCP, real‑time kontrolní protokoly. |

### Je UDP vždy rychlejší než TCP?
Ne.  
- **UDP** má nižší režii – žádné handshake a žádné potvrzení – což může vést k menšímu zpoždění při přenosu malých dat nebo v prostředí, kde je nezbytná nízká latence.
- **TCP** však využívá kontrolní mechanismy (flow control, congestion control), které mohou optimalizovat rychlost v síťových podmínkách s vysokou ztrátou paketů. V některých případech může TCP dosahovat vyšší efektivity než UDP, protože se vyhýbá opakovaným přenosům a zbytečnému zahlcení sítě.

**Shrnutí:** UDP je obvykle rychlejší v tom smyslu, že má méně režie, ale to neznamená, že je vždy „rychlejší“ ve všech situacích. Výběr protokolu závisí na požadavcích aplikace (spolehlivost vs. nízká latence).