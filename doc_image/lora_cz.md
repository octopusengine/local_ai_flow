# LoRA: kódy, druhy a přepisy pro Qwen Image

LoRA (Low-Rank Adaptation) je doplňkový model, který upravuje chování základního generátoru. Může přidat styl, podobu postavy, materiál nebo změnit způsob generování. Tag v promptu je pokyn pro aplikaci, aby tento doplněk načetla.

**Slovní přepis pro Qwen Image pouze popisuje požadovaný výsledek. Nenahrazuje naučené váhy LoRA a nezaručuje totožný obrázek.** Níže jsou česká vysvětlení a anglické fragmenty připravené k vložení do promptu.

## 1. Základní syntaxe

```text
<lora:nazev_modelu:vaha>
```

```text
Portrait of a woman, soft window light. <lora:YFG-ChatGPT-4o-Style-v2e16:0.45>
```

| Část | Význam |
| --- | --- |
| `lora` | Typ doplňku, který má aplikace načíst. |
| `nazev_modelu` | Název souboru nebo jeho alias; pravidla určuje aplikace. |
| `vaha` | Síla aplikované úpravy. Nejde o procenta ani pravděpodobnost. |
| `.safetensors` | Formát souboru s vahami; někde se přípona v tagu vynechává. |

Tagy nejsou univerzální jazyk samotného Qwen Image. Fungují jen tehdy, když je zpracovává použité rozhraní. V jiném workflow se LoRA načítá uzlem nebo programově mimo text promptu. Soubor musí být dostupný a kompatibilní s přesnou rodinou a verzí základního modelu. LoRA pro FLUX či Z-Image se tímto zápisem nestane kompatibilní s Qwen Image.

### Váhy a jejich kombinace

| Zápis | Obvyklý význam |
| --- | --- |
| `:0` | Nulový příspěvek LoRA; tag lze zpravidla vynechat. |
| `:0.3` nebo `:.3` | Slabší působení. |
| `:0.8` nebo `:.8` | Výraznější působení. |
| `:1` | Nominální plná váha; vhodná hodnota závisí na modelu. |
| `:1.2` | Zesílení nad nominální váhu; může zvýraznit i vady. |
| `:-1` | Záporná aplikace naučené úpravy, pokud ji loader podporuje. |

Váhy více LoRA se nemusí sečíst na `1`. Hodnota `0.5` neznamená přesně poloviční vizuální účinek. Výchozí hodnotu hledejte v dokumentaci konkrétní LoRA.

```text
<lora:styl_A:0.6> <lora:styl_B:0.3>
```

`styl_A` a `styl_B` jsou zde pouze zástupné názvy, nikoli doporučené soubory ke stažení. Stejně jsou označeny všechny obecné příklady níže.

### Dvě čísla za názvem

```text
<lora:zimage/painting_zimage_v1.safetensors:1.0:1.0>
```

Některé loadery dovolují oddělené váhy pro různé části modelu, například textový enkodér a obrazovou síť. **Pořadí a význam dvou čísel ověřte v použité aplikaci.** Tento zápis nelze bezpečně přenášet mezi rozhraními.

## 2. Malířské a výtvarné styly

Tyto LoRA mění techniku, tahy štětce, barvy nebo charakter ilustrace. Slovní přepis bývá použitelný pro přiblížení vzhledu.

| Druh | Příklad tagu | Alternativní fragment pro Qwen Image |
| --- | --- | --- |
| Malířský vzhled | `<lora:zimage/painting_zimage_v1.safetensors:1.0:1.0>` | `A painterly illustration with visible brushstrokes, layered pigments, textured canvas, and softly blended edges.` |
| Rembrandtův styl | `<lora:style_of_Rembrandt_FLUX_135:.8>` | `A Dutch Golden Age oil portrait with dramatic chiaroscuro, warm earth tones, deep brown shadows, luminous skin, and visible brushwork.` |
| Pastelová ilustrace | `<lora:midjourneypastel8q_d16a8e4:1.0>` | `A soft pastel illustration with powdery textures, muted peach, lavender and mint colors, diffused light, and gentle tonal transitions.` |
| Akvarel – obecný příklad | `<lora:watercolor_style:0.7>` | `A watercolor painting on textured paper, translucent washes, pigment blooms, and soft bleeding edges.` |
| Komiks – obecný příklad | `<lora:comic_style:0.7>` | `A comic-book illustration with bold ink outlines, cel shading, halftone textures, and graphic shapes.` |
| Tužka – obecný příklad | `<lora:pencil_sketch:0.7>` | `A graphite pencil drawing on cream paper, fine hatching, varied line pressure, and softly shaded volumes.` |

U názvů z původních ukázek jde o návrhy podle názvu, nikoli ověřenou reprodukci obsahu souboru. Zejména slovo `midjourney` v názvu nespouští službu Midjourney.

### Celý prompt bez LoRA

```text
A portrait of a 35-year-old woman seated beside a window. A Dutch Golden Age oil painting with dramatic chiaroscuro, warm earth tones, luminous skin, deep brown shadows, and visible brushwork. A dark, simple background and a calm expression.
```

## 3. Digitální ilustrace a styl konkrétního generátoru

```text
<lora:YFG-ChatGPT-4o-Style-v2e16:0.45>
```

Název naznačuje LoRA napodobující určitý vizuální vzhled. Nejde o přístup ke GPT-4o ani přepnutí generátoru. Pro přepis určete konkrétní vlastnosti obrázku, které chcete zachovat.

Možná interpretace jako čistá digitální ilustrace:

```text
A polished digital illustration with clean silhouettes, softly modeled forms, coherent lighting, a restrained color palette, and carefully arranged details.
```

### Nejasné nebo autorské názvy

```text
<lora:YFG-Soares-v1e4:1>
<lora:Delicate_Balance:.3>
<lora:113_novuschromaFLX_1:.2>
```

Z těchto názvů nelze spolehlivě určit účinek. Pro věrnější přepis potřebujete modelovou kartu nebo ukázkový obrázek. Části jako `v1e4`, `d16a8e4` a `FLX` mohou označovat verzi, trénink nebo rodinu modelu; nejsou to samostatné příkazy promptu.

Pokud je vaším záměrem jemná vyvážená kompozice, lze použít následující vlastní popis. Není to ověřený ekvivalent `Delicate_Balance`:

```text
A balanced composition with subtle color contrasts, delicate details, soft transitions, and generous negative space.
```

## 4. Fotografie, světlo a barevnost

| Druh | Příklad tagu | Alternativní fragment pro Qwen Image |
| --- | --- | --- |
| Fotografický vzhled – obecný příklad | `<lora:photo_realism:0.7>` | `A realistic photograph with natural skin texture, plausible materials, subtle imperfections, and physically consistent lighting.` |
| Filmový vzhled – obecný příklad | `<lora:cinematic_light:0.6>` | `A cinematic still with directional key light, soft fill light, controlled highlights, and subtle film grain.` |
| Analogový film – obecný příklad | `<lora:analog_film:0.6>` | `A 35mm color film photograph with fine grain, gentle highlight roll-off, slightly faded colors, and subtle halation.` |
| Černobílá fotografie – obecný příklad | `<lora:black_white_photo:0.8>` | `A monochrome photograph with rich grayscale tones, deep blacks, bright highlights, and fine film grain.` |
| Temný matný vzhled | `<lora:- Flux1 - vanta_black_V2.0:.6>` | `A low-key image with ultra-matte black surfaces, minimal reflections, deep shadows, and a narrow rim light defining the silhouette.` |

Poslední přepis je odhad podle názvu LoRA. U světla a barev bývá přesnější popsat požadovaný výsledek než zadat pouze `cinematic` nebo `dark`.

## 5. Materiály a prostorové zpracování

Následující názvy LoRA jsou zástupné příklady kategorií.

| Druh | Příklad tagu | Alternativní fragment pro Qwen Image |
| --- | --- | --- |
| Hlína | `<lora:clay_render:0.8>` | `A handcrafted clay figure with matte surfaces, slight fingerprints, rounded forms, and soft studio lighting.` |
| Papír | `<lora:paper_cut:0.8>` | `A layered paper-cut illustration with visible paper fibers, crisp cut edges, and soft shadows between layers.` |
| Keramika | `<lora:ceramic_style:0.7>` | `A glazed ceramic sculpture with subtle surface irregularities, glossy highlights, and a handcrafted finish.` |
| 3D render | `<lora:stylized_3d:0.7>` | `A stylized 3D render with rounded geometry, soft global illumination, ambient occlusion, and smooth materials.` |

## 6. Postavy, identita, oblečení a pózy

LoRA může obsahovat konkrétní naučenou identitu nebo produkt. Běžný prompt dovede popsat viditelné rysy, ale nemusí zachovat přesnou podobu mezi obrázky. Pro identitu je vhodná kompatibilní LoRA nebo workflow s obrazovou referencí.

| Druh | Zástupný tag | Příklad slovního přepisu |
| --- | --- | --- |
| Postava | `<lora:character_name:0.8>` | `An adult woman with a short auburn bob, green eyes, freckles, an oval face, and a calm expression.` |
| Oblečení | `<lora:costume_style:0.7>` | `A dark green velvet coat with brass buttons, embroidered cuffs, a fitted waist, and a high collar.` |
| Póza | `<lora:pose_concept:0.7>` | `Full-body view, standing with weight on the left leg, right hand resting on the hip, left arm relaxed, both feet visible.` |
| Produkt | `<lora:product_name:0.8>` | `A compact cream-colored espresso machine with a circular pressure gauge, a wooden handle, and a brushed steel drip tray.` |

Některé LoRA vyžadují také **trigger words** uvedená autorem. Samotný název souboru není automaticky aktivační slovo. Přesnou pózu nebo tvar může lépe řídit obrazová reference či jiné řízení podporované konkrétním workflow.

## 7. Zrychlovací LoRA: Lightning, Turbo a podobné

```text
<lora:Qwen-Image-Lightning-4steps-V2.0:0.5>
```

Tato kategorie upravuje generování pro malý počet kroků. **Nemá slovní náhradu.** Napsat `4 steps`, `fast generation` nebo `Lightning` do promptu nezrychlí výpočet.

- Načtěte správný adaptér pro konkrétní základní model.
- Počet kroků, váhu adaptéru, sampler a guidance/CFG nastavte podle příslušné modelové karty nebo workflow.
- `4steps` v názvu označuje zamýšlenou variantu; samotný tag nemusí nastavit počet kroků.
- Váha `0.5` je hodnota z ukázky, nikoli univerzální doporučení.
- Adaptéry pro Qwen-Image, jednotlivé novější verze a Qwen-Image-Edit nepovažujte automaticky za zaměnitelné.

Při slovním přepisu stylového promptu tento tag odstraňte z textu a technické nastavení řešte samostatně.

## 8. Záporné váhy a potlačování vlastností

```text
<lora:neeeg_f1:-1>
```

Záporná váha obrací směr naučené úpravy. Není to negativní prompt a bez znalosti LoRA nelze říct, co přesně potlačí nebo zvýrazní. Z názvu `neeeg_f1` nelze odvodit spolehlivý slovní ekvivalent.

Pokud chcete například přirozenější, méně přehnaný obraz, popište tento konkrétní záměr:

```text
Natural proportions, restrained colors, realistic skin texture, and soft, controlled contrast.
```

Tento fragment není převodem `neeeg_f1:-1`. Je to samostatný požadavek na výsledek. Podpora samostatného negativního promptu závisí na pipeline a nastavení guidance.

## 9. Přepis původních kombinací pro Qwen Image

### A. Malířská LoRA pro Z-Image

Původní tag:

```text
<lora:zimage/painting_zimage_v1.safetensors:1.0:1.0>
```

Možný textový přepis obecného malířského záměru:

```text
A painting with visible brushstrokes, layered pigments, textured canvas, softly blended edges, and carefully modeled light and shadow.
```

### B. Dvě autorské stylové LoRA

```text
<lora:YFG-ChatGPT-4o-Style-v2e16:0.45> <lora:YFG-Soares-v1e4:1>
```

Bez ukázek nelze věrně přepsat jejich kombinovaný styl. Jako vlastní alternativu čisté digitální ilustrace můžete použít:

```text
A polished digital illustration with clean silhouettes, softly modeled forms, coherent lighting, harmonious colors, and carefully arranged details.
```

### C. Lightning, pastel a vypnutá LoRA

```text
<lora:Qwen-Image-Lightning-4steps-V2.0:0.5> <lora:midjourneypastel8q_d16a8e4:1.0> <lora:TA-2025-11-12-15-59-01-midjourney-420:0>
```

Textová alternativa pastelového vzhledu:

```text
A soft pastel illustration with powdery textures, muted peach, lavender and mint colors, diffused light, gentle tonal transitions, and an airy composition.
```

Lightning patří do nastavení generování. Poslední LoRA má nulovou váhu, proto pro ni není potřeba slovní náhrada.

### D. Rembrandt, temný vzhled a další úpravy

```text
<lora:style_of_Rembrandt_FLUX_135:.8> <lora:- Flux1 - vanta_black_V2.0:.6> <lora:Delicate_Balance:.3> <lora:neeeg_f1:-1> <lora:113_novuschromaFLX_1:.2>
```

Možná alternativa pro rozpoznatelný malířský a temný záměr:

```text
A Dutch Golden Age oil portrait with dramatic chiaroscuro, warm earth tones, luminous skin, and visible brushwork. Deep matte-black fabric and a dark background, with restrained highlights defining the silhouette. A calm, balanced composition.
```

Účinky `Delicate_Balance`, `neeeg_f1` a `113_novuschromaFLX_1` nejsou ověřené; tento přepis je nenahrazuje. Číselné váhy nemají přesný převod na slova.

## 10. Praktický postup a šablona promptu

1. Určete subjekt, prostředí a kompozici.
2. Zvolte hlavní médium: fotografie, olejomalba, akvarel, ilustrace nebo 3D.
3. Přidejte konkrétní barvy, světlo a textury.
4. Nejasný název LoRA nahraďte až podle její dokumentace nebo ukázkového obrázku.
5. Technické adaptéry jako Lightning nastavte mimo slovní popis.
6. Při porovnávání měňte jednu vlastnost a pokud možno zachovejte seed i ostatní nastavení.

```text
[Subject and action]. [Environment and framing]. [Medium and visual style]. [Lighting]. [Colors and materials]. [Important details].
```

### Hotový příklad: pastelový portrét

```text
A portrait of a 35-year-old woman with a short auburn bob, wearing a cream linen blouse, seated in a quiet garden. Head-and-shoulders composition. A soft pastel illustration with powdery paper texture, muted peach, lavender and mint colors, gentle transitions, and diffused morning light. Delicate facial details and a softly simplified background.
```

### Hotový příklad: temný olejový portrét

```text
A portrait of a 55-year-old man in a black velvet coat, seated against a dark brown background. A Dutch Golden Age oil painting with warm earth tones, visible brushwork, and dramatic chiaroscuro. A warm side light illuminates his face and hands; the matte-black coat fades into deep shadow. Calm expression, natural facial proportions, and a restrained composition.
```

## 11. Zdroje a hranice přepisů

- [AUTOMATIC1111: syntaxe LoRA tagů](https://github.com/AUTOMATIC1111/stable-diffusion-webui/wiki/Features) — základní zápis názvu a váhy; konkrétní rozhraní mohou mít jiné rozšíření syntaxe.
- [Qwen-Image: oficiální modelová karta](https://huggingface.co/Qwen/Qwen-Image) — příklady generování pomocí textového promptu.
- [Qwen-Image: oficiální repozitář](https://github.com/QwenLM/Qwen-Image) — dokumentace rodiny modelů a příklady použití.
- [LightX2V Qwen-Image-Lightning](https://github.com/ModelTC/LightX2V-Qwen-Image-Lightning) — zrychlovací adaptéry a jejich workflow.

Obecné názvy v tabulkách jsou ilustrační. Konkrétní autorské LoRA z původního dotazu zde nejsou ověřené podle modelových karet; navržené stylové přepisy jsou popisy vizuálního záměru, nikoli přesné ekvivalenty.
