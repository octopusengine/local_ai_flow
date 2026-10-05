# Qwen-Image 2.1 --- promptovací přehled

Praktický cheat sheet pro **Qwen-Image-2.1** se zaměřením na
text-to-image, image editing, fotorealismus, zachování identity a
systematické testování promptů.

> **Poznámka:** Qwen-Image 2.1 je multimodální model pro text-to-image i
> image editing. Následující doporučení vycházejí především z oficiální
> dokumentace Qwen a z prompt-rewriteru vydaného pro Qwen-Image 2.1.
> Chování se může lišit podle konkrétního checkpointu, Diffusers verze,
> inference nastavení a použitého workflow.

------------------------------------------------------------------------

## 1. Základní princip

Qwen-Image není vhodné promptovat úplně stejně jako klasické Stable
Diffusion/SDXL modely.

Preferovaný styl je:

-   normální anglický popis,
-   jasné věty,
-   konkrétní vizuální vlastnosti,
-   přesné vztahy mezi objekty,
-   explicitní instrukce při editaci,
-   minimum nejasných tagů,
-   žádné spoléhání na SD-style weighting syntaxi.

Oficiální Qwen prompt-rewriter pro T2I převádí stručný požadavek do
**jednoho dlouhého anglického popisu hotového obrazu**. Pro editaci
naopak vytváří přesnou instrukci založenou na vstupním obrázku.
\[1\]\[2\]

### Doporučený základ

``` text
A photorealistic image of a woman in a modern office,
looking directly at the camera, natural skin texture,
realistic lighting, subtle shadows, detailed materials,
shallow depth of field and convincing photographic depth.
```

Místo:

``` text
woman, beautiful, photo, realistic, detailed, 8k
```

------------------------------------------------------------------------

# 2. Co Qwen pravděpodobně dobře chápe

Dobře fungují především **konkrétní popisy vizuálních vlastností**.

### Osoba

``` text
a young adult woman
```

``` text
a middle-aged man with short dark hair
```

``` text
the person is looking directly into the camera
```

``` text
a relaxed facial expression
```

``` text
wearing a dark blue wool jacket
```

### Kompozice

``` text
close-up portrait
```

``` text
full-body composition
```

``` text
the person is positioned slightly to the left of the frame
```

``` text
the subject occupies the central third of the image
```

``` text
wide environmental composition
```

### Fotografie

``` text
photorealistic photograph
```

``` text
natural skin texture
```

``` text
realistic fabric texture
```

``` text
physically plausible lighting
```

``` text
natural shadows and reflections
```

``` text
shallow depth of field
```

``` text
subtle photographic imperfections
```

### Materiály

Místo obecného:

``` text
a table
```

lépe:

``` text
a weathered wooden table with visible grain and small surface imperfections
```

Místo:

``` text
glass
```

lépe:

``` text
transparent glass with subtle reflections and realistic refraction
```

Oficiální prompt-rewriter přímo doporučuje popisovat **materiál**,
nikoli pouze objekt: brushed metal, matte plastic, glossy ceramic,
coarse linen, weathered wood, frosted glass atd. \[2\]

------------------------------------------------------------------------

# 3. Co nepoužívat jako hlavní mechanismus

## Stable Diffusion weighting

Nespoléhat na:

``` text
(beautiful:1.2)
```

``` text
(looking at viewer:1.5)
```

``` text
((photorealistic))
```

Qwen-Image není model, u kterého bychom měli předpokládat klasické
SD/A1111 prompt weighting chování.

Pokud je něco důležité, napiš to **silněji a explicitněji**.

### Místo

``` text
(looking at viewer:1.4)
```

použij:

``` text
the person is looking directly into the camera
```

Ještě explicitněji:

``` text
the person's eyes are directed straight toward the camera
```

------------------------------------------------------------------------

# 4. Závorky, lomítka a speciální syntax

## Závorky

``` text
(beautiful:1.2)
```

Nepovažovat za spolehlivý weighting mechanismus.

Závorky mohou být součástí běžného textu, ale není vhodné na nich stavět
experiment.

## Lomítka

``` text
beauty / photorealistic / detailed
```

Nemají speciální význam typu "OR", "weight" nebo "priority".

Použij raději:

``` text
beautiful, photorealistic and highly detailed
```

## Čárky

Čárky jsou v pořádku:

``` text
photorealistic, natural lighting, realistic skin texture, subtle shadows
```

Ale ještě důležitější než samotné čárky je srozumitelná struktura
instrukce.

------------------------------------------------------------------------

# 5. Jak vyjádřit důležitost

Qwen nemá být promptován tak, že každé slovo dostane matematickou váhu.

Místo toho používej:

### Opakování důležitého konceptu

``` text
The image is highly photorealistic.
The result should look like a real photograph, with physically plausible
lighting, realistic materials and natural photographic detail.
```

Opakování nepřehánět. Jedna jasná formulace obvykle stačí.

### Explicitní formulace

Slabší:

``` text
realistic face
```

Silnější:

``` text
a highly realistic human face with natural skin texture,
subtle pores, realistic proportions and authentic photographic detail
```

### Priorita pomocí struktury věty

``` text
The primary focus is the person's face.
Preserve the facial identity and expression while making the image fully photorealistic.
```

To je vhodnější než:

``` text
(face:1.5)
```

------------------------------------------------------------------------

# 6. Prompt pro fotorealismus

Samotné:

``` text
photorealistic
```

je použitelné, ale může být příliš obecné.

Pro silnější efekt:

``` text
highly photorealistic photograph, natural skin texture,
physically plausible lighting, realistic materials,
accurate shadows, subtle reflections, convincing depth,
natural imperfections and authentic photographic detail
```

## Přirozenější fotografický vzhled

``` text
a realistic professional photograph,
natural skin texture, subtle imperfections,
physically plausible lighting, realistic depth of field,
natural color reproduction and authentic photographic detail
```

## Vysoce kvalitní fotografie

``` text
high-end professional photography,
precise focus, realistic lens rendering,
natural depth of field, detailed textures,
physically plausible illumination and subtle photographic imperfections
```

Pozor na bezmyšlenkovité přidávání:

``` text
8k, 16k, ultra HD, masterpiece, best quality
```

Tyto výrazy nemusí přinést odpovídající zlepšení a často jsou méně
užitečné než konkrétní popis materiálů, světla, optiky a scény.

------------------------------------------------------------------------

# 7. Převod kresby na fotorealismus

Pro experimenty typu:

**drawing → photorealistic image**

je dobré explicitně říct, co se má změnit a co má zůstat.

### Doporučený základ

``` text
Transform the provided drawing into a highly photorealistic image.
Preserve the original composition, subject, proportions, pose,
perspective and spatial relationships.

Replace the drawn appearance with realistic human features,
physically plausible materials, natural textures, realistic lighting,
accurate shadows, subtle reflections and convincing three-dimensional depth.

The result should look like a real photograph faithfully reproducing
the original drawing rather than a new interpretation of it.
```

### Důležitý princip

**Edituj pouze požadovaný atribut.**

Pokud chceš změnit pouze styl:

``` text
Transform the visual style into photorealistic photography
while preserving the original composition, subject, pose,
proportions, perspective and all important visual elements.
```

Neříkej současně:

``` text
make it photorealistic, change the face, improve the clothes,
change the lighting, make the background cinematic...
```

pokud skutečně nechceš všechny tyto změny.

Oficiální edit prompt systém Qwen explicitně používá princip **attribute
disentanglement**: změnit pojmenovaný atribut a ostatní obsah držet co
nejvíce věrný vstupu. \[1\]

------------------------------------------------------------------------

# 8. Identity preservation

Qwen-Image 2.1 oficiálně uvádí podporu pro zachování identity lidí a
produktů při editaci. Model podporuje také více referenčních obrázků a
lokální editace. \[3\]

## Základní pravidlo

Pokud je identita důležitá, **odkazuj na referenční obrázek**, místo
abys znovu popisoval obličej pouze textem.

Slabší:

``` text
keep the same face
```

Lepší:

``` text
preserve the person's facial identity from the input image
```

Ještě lepší při komplexní editaci:

``` text
Preserve the person's facial identity, hairstyle, recognizable features,
expression and overall appearance from the input image.
Change only the requested attributes.
```

## Příklad změny oblečení

``` text
Change the person's clothing to a dark formal suit.
Preserve the person's facial identity, hairstyle, body proportions,
pose, expression and the rest of the original image.
```

## Příklad změny prostředí

``` text
Place the person in a modern office environment.
Preserve the person's facial identity, hairstyle, clothing,
body proportions and recognizable appearance.
Change only the environment and lighting required by the new scene.
```

------------------------------------------------------------------------

# 9. Image editing

Qwen-Image 2.1 podporuje:

-   lokální změny,
-   změnu objektů,
-   odstranění objektů,
-   nahrazení objektů,
-   změnu stylu,
-   změnu prostředí,
-   práci s více referenčními obrázky,
-   masky / označené oblasti,
-   zachování identity. \[3\]

## Základní syntax instrukce

``` text
Replace X with Y.
Preserve everything else.
```

Například:

``` text
Replace the red chair with a modern black leather chair.
Preserve the rest of the room, composition, lighting and perspective.
```

## Odstranění

``` text
Remove the object on the right side of the image.
Reconstruct the exposed background naturally and preserve everything else.
```

## Přidání

``` text
Add a small green plant on the table near the right side of the frame.
Match the existing lighting, perspective, scale and shadows.
Preserve everything else.
```

## Změna barvy

``` text
Change the woman's jacket from black to dark red.
Preserve its material, shape, folds and position.
Keep the person and the rest of the image unchanged.
```

------------------------------------------------------------------------

# 10. "Preserve everything else" je důležité

Při editaci je často užitečné explicitně určit, co se **nemá měnit**.

Například:

``` text
Change the background to a realistic forest.
Preserve the person's identity, pose, clothing and proportions.
```

než jen:

``` text
Put the person in a forest.
```

Čím větší zásah, tím důležitější je oddělit:

1.  co se mění,
2.  co zůstává.

------------------------------------------------------------------------

# 11. Negative prompt

U prompt-rewriteru Qwen-Image 2.1 je zajímavé, že oficiální enhancer
**negative prompt negeneruje**. Výstupní pole existuje kvůli
kompatibilitě downstream workflow, ale je prázdné. \[4\]

To neznamená, že každý frontend nebo pipeline musí negative prompt
ignorovat. Znamená to ale, že **negative prompting není hlavní
doporučený mechanismus Qwen promptování**.

Místo dlouhého:

``` text
negative:
bad anatomy, ugly, deformed, blurry, low quality,
extra fingers, malformed hands...
```

je často lepší napsat pozitivní požadavek:

``` text
natural human anatomy, anatomically plausible hands,
realistic proportions, sharp photographic detail
```

## Kdy negative prompt přesto testovat

Pokud ho tvoje konkrétní pipeline podporuje, můžeš experimentálně
porovnat:

### A

``` text
photorealistic portrait of a woman
```

### B

``` text
photorealistic portrait of a woman
```

negative:

``` text
cartoon, illustration, distorted anatomy, blurry
```

A použít stejný seed.

To je lepší než předpokládat, že negative prompt funguje stejně jako u
SDXL.

------------------------------------------------------------------------

# 12. Text v obraze

Qwen-Image má výraznou schopnost generovat text.

Požadovaný text dávej explicitně do dvojitých uvozovek:

``` text
a storefront sign reading "COFFEE HOUSE"
```

ne:

``` text
a coffee house sign
```

Pokud je přesné znění důležité, zachovej přesné znaky, velikost písmen a
interpunkci.

Při editaci Qwen prompt enhancer rovněž požaduje text určený k
vykreslení v uvozovkách. \[1\]\[5\]

------------------------------------------------------------------------

# 13. Kompozice a prostorové vztahy

Qwen prompt enhancer doporučuje explicitně popisovat **pozici objektů ve
frame**.

Používej například:

``` text
in the center of the image
```

``` text
in the upper-left corner
```

``` text
on the far right
```

``` text
in the lower third
```

``` text
in front of the building
```

``` text
behind the woman
```

``` text
slightly left of center
```

Místo:

``` text
a woman, a chair, a plant
```

raději:

``` text
A woman is positioned slightly left of center.
A wooden chair is behind her on the right.
A tall plant occupies the far-right side of the frame.
```

------------------------------------------------------------------------

# 14. Lidé --- co popisovat

U člověka je užitečné explicitně uvést:

-   přibližnou životní fázi,
-   postavu,
-   pózu,
-   směr pohledu,
-   výraz,
-   vlasy,
-   oblečení,
-   materiály oblečení,
-   případné doplňky,
-   vztah k prostředí.

Například:

``` text
a young adult woman with long dark hair,
a relaxed facial expression, looking directly into the camera,
wearing a tailored beige wool coat
```

Pokud je obličej zakrytý nebo otočený, je lepší to říct než si vymýšlet
jeho vlastnosti.

------------------------------------------------------------------------

# 15. Materiály a textury

Qwen prompt enhancer explicitně doporučuje materiály popisovat
konkrétně.

### Slabé

``` text
table
```

### Silnější

``` text
weathered oak table with visible wood grain and small scratches
```

### Slabé

``` text
dress
```

### Silnější

``` text
soft matte black silk dress with subtle folds and realistic fabric texture
```

### Slabé

``` text
wall
```

### Silnější

``` text
aged plaster wall with subtle cracks and uneven surface texture
```

To je zvlášť užitečné při fotorealistickém renderování.

------------------------------------------------------------------------

# 16. Světlo

Místo obecného:

``` text
good lighting
```

používej konkrétní světelnou situaci:

``` text
soft window light from the left
```

``` text
warm late-afternoon sunlight
```

``` text
soft overcast daylight
```

``` text
hard directional sunlight with defined shadows
```

``` text
large diffused studio light
```

``` text
subtle rim light separating the subject from the background
```

Pro fotorealismus:

``` text
physically plausible illumination,
natural shadow falloff and realistic reflections
```

------------------------------------------------------------------------

# 17. Objektiv a fotografický vzhled

Fotografické termíny mohou pomoci, ale neměly by být pouze seznamem
náhodných tagů.

### Portrét

``` text
professional portrait photography,
shallow depth of field,
natural skin texture,
soft background separation
```

### Environmentální fotografie

``` text
environmental portrait,
moderate depth of field,
the surroundings remain clearly recognizable
```

### Cinematic

``` text
cinematic photographic composition,
controlled contrast,
natural volumetric light,
subtle atmospheric depth
```

------------------------------------------------------------------------

# 18. "8K", "4K", "masterpiece", "best quality"

Testovat lze:

``` text
8K
```

``` text
ultra detailed
```

``` text
masterpiece
```

ale **nepovažovat je za hlavní mechanismus kvality**.

Pro Qwen je obvykle informativnější:

``` text
realistic skin pores,
fine hair strands,
accurate fabric texture,
subtle surface imperfections,
physically plausible reflections
```

než:

``` text
masterpiece, best quality, 8K
```

------------------------------------------------------------------------

# 19. Délka promptu

Delší prompt není automaticky lepší.

Dobrá struktura:

``` text
[medium/style]
[main subject]
[composition]
[appearance]
[environment]
[lighting]
[materials/textures]
[photographic rendering]
```

Například:

``` text
A highly photorealistic environmental portrait of a young woman
in a modern architectural interior. She is positioned slightly left
of center and looking directly into the camera. She wears a tailored
dark blue wool jacket with realistic fabric texture. Large windows
behind her reveal a softly blurred cityscape. Natural daylight enters
from the left, producing physically plausible shadows and subtle
reflections on the polished floor. Realistic skin texture, individual
hair strands, accurate materials, natural depth of field and authentic
professional photographic detail.
```

------------------------------------------------------------------------

# 20. Prompt pro čisté T2I

Obecná šablona:

``` text
A [style/medium] image of [main subject] in [environment].
[Composition and position].
[Appearance and clothing].
[Important objects and their positions].
[Lighting].
[Materials and textures].
[Camera/photographic properties].
[Overall visual character].
```

Příklad:

``` text
A highly photorealistic photograph of a young woman in a refined
modern office. She is positioned slightly left of center and looking
directly into the camera. She wears a dark navy wool jacket and a
simple white shirt. A wooden desk occupies the foreground and a large
window is visible behind her. Soft natural daylight enters from the
left, creating realistic shadows and subtle reflections. Natural skin
texture, individual hair strands, realistic fabric, physically
plausible materials, convincing depth of field and authentic
professional photographic detail.
```

------------------------------------------------------------------------

# 21. Prompt pro editaci

Obecná šablona:

``` text
[Action].
[Exact target].
[Desired appearance].
[What must remain unchanged].
[Lighting/perspective integration].
```

Příklad:

``` text
Change the woman's clothing to a dark green tailored business suit.
Preserve her facial identity, hairstyle, expression, body proportions,
pose and position. Match the new clothing to the existing lighting,
perspective, shadows and fabric behavior. Preserve the entire
background and all other objects unchanged.
```

------------------------------------------------------------------------

# 22. Stylová transformace

Pro změnu kresby na fotografii:

``` text
Transform the provided illustration into a highly photorealistic
photograph. Preserve the original composition, subject, proportions,
pose, perspective and spatial relationships. Replace the illustrative
appearance with realistic materials, natural textures, physically
plausible lighting, realistic shadows, subtle reflections and
convincing three-dimensional depth. The final result should look like
a real photograph faithfully reproducing the original image rather
than a reinterpretation of it.
```

------------------------------------------------------------------------

# 23. Identity + nové prostředí

``` text
Place the person from the input image into a realistic modern office
environment. Preserve the person's facial identity, hairstyle,
recognizable appearance, body proportions and clothing. Preserve the
person's pose and expression. Adapt only the lighting and shadows
necessary to integrate the person naturally into the new environment.
Create physically plausible perspective, reflections and depth.
```

------------------------------------------------------------------------

# 24. Změna pouze stylu

``` text
Transform the image into a highly photorealistic photographic style.
Preserve the original subject, composition, pose, proportions,
perspective, objects and spatial relationships. Change only the
rendering style and visual medium.
```

Tohle je důležité při testování, protože explicitně říká:

**měň styl, ne obsah.**

------------------------------------------------------------------------

# 25. Lokální editace

Když chceš změnit konkrétní část:

``` text
Change only the sky to a realistic dramatic sunset.
Preserve the buildings, people, foreground, composition,
perspective and all other elements unchanged.
Match the new sky to the existing lighting and reflections.
```

Tento styl je vhodnější než obecné:

``` text
make it sunset
```

------------------------------------------------------------------------

# 26. Více referenčních obrázků

Qwen-Image 2.1 podporuje až 10 referenčních obrázků. \[3\]

Při více obrázcích je důležité jednoznačně určit jejich role.

Příklad:

``` text
Use the person from image 1 and place them into the environment
from image 2. Preserve the person's identity, clothing and proportions
from image 1. Preserve the composition and architectural structure
from image 2. Match lighting, perspective and shadows between them.
```

Oficiální edit prompt enhancer používá pro více vstupů označení:

``` text
<image1>
<image2>
```

a výslovně určuje, který obrázek je canvas a které obrázky dodávají
materiál. \[1\]

------------------------------------------------------------------------

# 27. Co testovat systematicky

Při ladění Qwen promptu je lepší měnit **jednu věc najednou**.

Například:

### Test A

``` text
photorealistic
```

### Test B

``` text
highly photorealistic
```

### Test C

``` text
highly photorealistic photograph,
natural skin texture, realistic lighting and materials
```

Stejný:

-   seed,
-   input image,
-   rozlišení,
-   počet steps,
-   další parametry.

Pak lze skutečně poznat vliv promptu.

------------------------------------------------------------------------

# 28. Doporučená testovací sada

Pro tvoje experimenty můžeš použít následující proměnné.

## Realism

``` text
photorealistic
```

``` text
highly photorealistic
```

``` text
realistic professional photograph
```

``` text
highly photorealistic photograph with natural textures and physically plausible lighting
```

## Pohled

``` text
looking at the viewer
```

``` text
looking directly at the viewer
```

``` text
looking directly into the camera
```

## Detail

``` text
highly detailed
```

``` text
fine surface detail
```

``` text
realistic skin texture and fine material detail
```

## Světlo

``` text
natural daylight
```

``` text
soft diffused daylight
```

``` text
cinematic lighting
```

``` text
physically plausible natural lighting
```

## Hloubka

``` text
shallow depth of field
```

``` text
natural photographic depth of field
```

``` text
deep focus with realistic atmospheric depth
```

------------------------------------------------------------------------

# 29. Praktické pravidlo pro Qwen

Při psaní promptu si polož pět otázek:

1.  **Co je hlavní subjekt?**
2.  **Kde přesně je ve scéně?**
3.  **Co přesně má vypadat jak?**
4.  **Jaké světlo a materiály chci?**
5.  **Co se při editaci nesmí změnit?**

Pokud na ně prompt odpovídá, je většinou výrazně použitelnější než
dlouhý seznam tagů.

------------------------------------------------------------------------

# 30. Krátký Qwen cheat sheet

  Úkol                     Doporučení
  ------------------------ --------------------------------------------------
  Photorealismus           `highly photorealistic photograph`
  Pohled do kamery         `looking directly into the camera`
  Detail                   popsat konkrétní textury
  Realistická kůže         `natural skin texture, subtle pores`
  Realistické materiály    uvést konkrétní materiál
  Světlo                   popsat zdroj, směr a charakter
  Kompozice                uvést pozici v obraze
  Zachování identity       explicitně `preserve facial identity`
  Změna jednoho atributu   `Change only... Preserve...`
  Text v obraze            přesný text v `"double quotes"`
  Více obrázků             jednoznačně určit roli každého obrázku
  SD weighting             nespoléhat na `(x:1.2)`
  Lomítka                  nepoužívat jako speciální syntaxi
  Negative prompt          testovat, ale nebrat jako hlavní mechanismus
  `masterpiece` / `8K`     sekundární, ne hlavní strategie
  Dlouhý prompt            pouze pokud přidává konkrétní vizuální informace

------------------------------------------------------------------------

# 31. Nejlepší obecná šablona

Pro běžné Qwen T2I:

``` text
A [style/medium] image of [main subject].
[Subject appearance and pose].
[Composition and position in the frame].
[Environment and important objects].
[Materials and textures].
[Lighting and shadows].
[Depth of field / photographic characteristics].
[Specific details that must be visible].
```

Pro Qwen edit:

``` text
Change [specific attribute] to [desired result].
Preserve [identity/composition/pose/objects/etc.].
Match [lighting/perspective/materials/shadows].
Change only the requested attribute and keep the remaining
content faithful to the input image.
```

------------------------------------------------------------------------

# 32. Zdroje

\[1\] Qwen-Image-2.1 --- official Edit Prompt Enhancer system prompt\
https://github.com/QwenLM/Qwen-Image-2.1/blob/main/prompt_rewrite/prompts/system_prompt_edit.txt

\[2\] Qwen-Image-2.1 --- official T2I Prompt Enhancer system prompt\
https://github.com/QwenLM/Qwen-Image-2.1/blob/main/prompt_rewrite/prompts/system_prompt_t2i.txt

\[3\] Qwen-Image-2.1 --- official model README\
https://huggingface.co/Qwen/Qwen-Image-2.1/blob/main/README.md

\[4\] Qwen-Image-2.1 --- Prompt Enhancer README\
https://github.com/QwenLM/Qwen-Image-2.1/blob/main/prompt_rewrite/README.md

\[5\] Qwen-Image --- official prompt utilities\
https://github.com/QwenLM/Qwen-Image/blob/main/src/examples/tools/prompt_utils.py
