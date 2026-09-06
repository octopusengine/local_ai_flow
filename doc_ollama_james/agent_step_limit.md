# Limit kroků agenta

Společný limit pro James / Cowork a samostatný CLI agent je v kořenovém
`cli_agent.json`, mimo `options` modelu:

```json
"max_steps": 32
```

Hodnota musí být kladné celé číslo. Starší konfigurace bez tohoto klíče
použijí 32. Nastavení se načítá při každém novém uživatelském zadání, takže
po prvním restartu s touto aktualizací lze JSON měnit i během otevřené relace.
Probíhající zadání dokončí běh se svým původním limitem.

Jeden krok znamená jedno kolo dotazu na model; může obsahovat více volání
nástrojů. Limit zahrnuje také kolo závěrečné odpovědi. Číslo `/32` tedy není
limit počtu jednotlivých souborových operací ani tokenů.

Samostatné CLI může limit přebít argumentem `--max-steps 48`; explicitní
argument platí po celou relaci a má přednost před JSONem. Profily z
`agent/agents.json` tento společný limit nepřebíjejí. Samostatný reviewer
má nadále vlastní limit 8 kroků. Kontext modelu (`num_ctx`) se nemění.
