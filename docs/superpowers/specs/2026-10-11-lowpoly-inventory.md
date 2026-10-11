# Inwentarz resztek low-poly (stan na 2026-10-11, branch `feat/biome-props-realism`)

> Po polsku dla autora. Lista wszystkiego, co na mapie jest jeszcze **proceduralnym prymitywem**
> (ico-sfery, cylindry, prostopadłościany, `flat_shaded` + kolor w wierzchołkach na białym
> `StandardMaterial`) zamiast modelu z Blendera na skanach PBR. Bossowie (treant, golem, revenant,
> hag, Bałwan) są już zrobieni i pominięci. Liczby to szacunki z `chance × SCATTER_DENSITY 1.35`
> i liczby kafli regionu (pustynia ~12k, bagno ~10k, skały ~8k kafli), nie pomiar.

Co już jest realistyczne: las (`realforest`, `biome.rs` gałąź `kit`), śnieg (`alpine::snowkit`,
domyślnie włączony), przydrożne meble i sceny POI (`wayside.glb`), obozy orków (`structures.glb`
z fallbackiem), stary młyn, Opuszczony Obóz, jabłonie, zamek i miasto (`castle_kit` / `town_kit`).

Widoczność: **W** = wysoka (blisko zamku / głównych dróg albo duże na tle nieba), **Ś** = średnia,
**N** = niska (drobne / rzadkie / w mgle).

## 1. Biomy: scatter (najwięcej sztuk na mapie)

| Asset | Plik:linia | Ile na mapie | Widoczność | Status |
|---|---|---|---|---|
| Skały: grań z płyt / rozłupana grań / rumowisko (crag 0–2) | `biome_rocky.rs:189` (klasa :706) | ~300–450 | W | **zamienione** → `rk_crag_a/b/c` |
| Skały: kopczyk (cairn, crag 3) | `biome_rocky.rs:274` | ~30–50 | W | **zamienione** → `rk_cairn` |
| Skały: suche krzaki (fasetowane kępy) | `biome_rocky.rs:515` (klasa :694) | ~300 | W | **zamienione** → jałowiec / kosodrzewina / kępa trawy z `alpine_flora.glb` |
| Skały: hoodoo (pasiaste iglice) | `biome_rocky.rs:303` (klasa tree :725) | ~60 | W | **zamienione** → `rk_spire_a/b` (piaskowiec na `s_rock`) |
| Skały: sosny na wietrze + suchy pień | `biome_rocky.rs:399`, `:455` | ~60 | W | **zamienione** → `spruce_flag` / `pine_*` / `dead_a` z kitu |
| Skały: piargi (scree) | `biome_rocky.rs:555` (klasa :740) | ~200 | Ś | **zamienione** → `rk_scree_a/b` |
| Skały: pokrycie (kamyczki, suche kępki, porosty + kwiatki) | `biome_rocky.rs:597/642/654` | tysiące (scalone chunki) | Ś | **zamienione** → `rk_pebbles`, `tussock_*`, `grass_*`, kwiaty z kitu |
| Pustynia: saguaro (klasa tree) | `biome_desert.rs:137` (klasa :583) | ~400–600 | W (2–2.5 u) | **zamienione** → `ds_saguaro_a/b/c` |
| Pustynia: suchy krzak / tumbleweed (też fallback drzew) | `biome_desert.rs:292` (:575) | ~500 | Ś | zostaje |
| Pustynia: kaktus beczkowy | `biome_desert.rs:238` (:595) | ~350 | Ś | zostaje |
| Pustynia: opuncja | `biome_desert.rs:322` (:603) | ~200 | Ś | zostaje |
| Pustynia: wybielone skały + kości / czaszka | `biome_desert.rs:368` (:611) | ~400 | Ś | zostaje |
| Pustynia: pokrycie (kamyczki, sucha trawa, sukulenty) | `biome_desert.rs:422/440/469/482` | tysiące | N | zostaje |
| Bagno: namorzyn („grzybkowe” drzewa) | `biome_swamp.rs:195` (klasa :908) | ~500–650 | W | **zamienione** → `oak_*` / `beech_*` / `dead_a` z kitu |
| Bagno: pień cyprysu z kolanami | `biome_swamp.rs:338` | ~200–250 | Ś | **zamienione** → `stump_a` (skan) |
| Bagno: pałka wodna | `biome_swamp.rs:390` (:923) | ~500 | Ś | zostaje |
| Bagno: muchomory, omszały głaz, zatopiona kłoda | `biome_swamp.rs:464` (:934) | ~300 | Ś | zostaje |
| Bagno: pokrycie (mech, trzcinka, grzybki, wełnianka) | `biome_swamp.rs:570–634` | tysiące | N | zostaje |
| Śnieg z `FOREST_ALPINE=0` (sosny, kopce, głazy) | `biome_snow.rs`, `worldmap.rs:3698` | — | — | tylko z wyłączonym kitem |

## 2. Okolice zamku (najbliżej kamery na starcie)

| Asset | Plik:linia | Ile | Widoczność | Status |
|---|---|---|---|---|
| Drzewa łąki przy zamku (`trees::build_tree_mesh`) | `meadow.rs:175–203` | 7 | W | zostaje — **pierwszy kandydat** (kit ma te same gatunki) |
| Rekwizyty wioski: wóz z sianem, bele, strach na wróble, ule, stos drewna, skrzynie, płot | `meadow.rs:256–367` | ~10 | W | zostaje |
| Ognisko odpoczynku + 3 pieńki | `meadow.rs:419/440` | 4 | W (spawn bohatera) | zostaje (kit ma `stump_a`) |
| Głazy i krzaki łąki | `meadow.rs:384/399` | 4 + 4 | W | zostaje (kit ma `rock_*`, `bush_*`) |
| Dekor dziedzińca (tablica, koryto, ławka, latarnie, ogródek, pranie, zbrojownia, kapliczka…) | `castle_decor.rs:327–684` | ~8 + ~15 z ulepszeniami | W | zostaje (generowane tekstury) |
| Sklep kupca za bramą | `villagers.rs` `shop_parts` (:2569) | 1 | W | zostaje |
| Budynki produkcyjne miasta (farma / drwal / kopalnia), gruz, place | `town_meshes.rs`, `town.rs:644/1658/1696` | do 12 | W | zostaje |
| Kukły treningowe | `training_dummies.rs:40` | kilka | W | zostaje |
| Balista | `defenses.rs:584` | 1 | Ś | zostaje |
| Mosty (pokład z desek) / kładki na bagnie | `bridges.rs:407` / `:473` | ≤5 / ≤10 | W / Ś | zostaje |

## 3. Landmarki, twierdze, punkty

| Asset | Plik:linia | Ile | Widoczność | Status |
|---|---|---|---|---|
| Zatopiona schodkowa piramida (pustynia) | `landmark_models.rs:603`, spawn `ruins.rs:616` (×1.5 → ~7×7×7 u) | 1 | W (sylweta) | zostaje |
| Chata wiedźmy (bagno) | `landmark_models.rs:250`, `ruins.rs:619` | 1 | W | zostaje |
| Zamarznięta iglica (śnieg) | `landmark_models.rs:483`, `ruins.rs:615` | 1 | W | zostaje |
| Menhiry (skały) | `landmark_models.rs:802`, `ruins.rs:617` | 1 | W | zostaje |
| Twierdza orków: palisada, brama, wieże, wielka hala, iglica | `ork_fortress.rs:1490–1706` | 13 + 3 + 7 + 2 | W (duże) | zostaje |
| Twierdza orków: namioty, kolce, palenisko | `ork_fortress.rs:1760/2434/2486` | 6 + 4 + 1 | W | zostaje — **tanie**: GLB `ork_tent` / `ork_spikes` / `ork_firepit` już są, obozy ich używają |
| Twierdza orków: chaty, kuźnia, zagroda, bębny, rożen, totemy, drogowskazy, śmieci | `ork_fortress.rs:1814–2477` | ~60 | Ś | zostaje |
| Plaga: martwe drzewa, szpony, kikuty + śmieci (grzyby, złom, smoła, klatki, kukły) | `ork_fortress.rs:1059–1120`, `:2020–2240` | ~150–250 + ~400 | Ś | zostaje |
| Twierdza rywala: keep, mury, brama, wieże | `rival.rs:189/257/211/230` | 1 komplet | W (sylweta) | zostaje (generowane tekstury) |
| Domy i budynki rywala | `rival.rs:245`, `:424–435` | 5 + 7 | Ś–W | zostaje |
| Złoża rudy (bryła z prostopadłościanów + świecące stożki kryształów) | `verbs.rs:1277/1294` | 64 (`ORE_COUNT`) | W (gameplay) | zostaje — **ważne w biomie skał**, teraz najbardziej odstaje |
| Skrzynie (drewniana + relikwiarz) | `chest.rs:552–616` | ~30 | Ś | zostaje |
| Bagno: utopione drzewa, wieża, chata na palach, świecące grzyby | `bog.rs:81/122/183–281` | ≤28 + 1 + 1 + ≤20 | Ś | zostaje (dzieli meshe z namorzynem) |
| Winiety: Zagubiona Karawana, Wrak, Zamarznięty Obóz, Wieża Strażnicza | `vignettes.rs:111/202/180/152` | 4 | Ś | zostaje |
| Wodospad + punkt widokowy (sosna, kamień, kopczyk) | `vista.rs:79/115` | 1 + 3 | Ś–W | zostaje |
| Zioła bagienne (zbieractwo) | `verbs.rs:1373` | 55 | N–Ś | zostaje |
| Wrony nad warownią | `poi.rs:686` | 5 | N | zostaje |
| Odległe wyspy w tle (**plik zablokowany**) | `distant_isles.rs:214` | 5 | N–Ś (mgła) | nie ruszać w tym zadaniu |
| Żaglówki w tle (**plik zablokowany**) | `boats.rs:239` | 9 | N–Ś | nie ruszać w tym zadaniu |

Martwy kod (nigdzie nie spawnowany): `landmarks()` w `biome_desert.rs` (palmy oazy), `biome_snow.rs`,
`biome_forest.rs`, `biome_rocky.rs` (łuk skalny) i `biome_swamp.rs` (ale `bog.rs` używa jego meshy);
`decor.rs` w całości.

## 4. Co zrobiono w tym branchu

Nowy zestaw `tools/blender_forest/biome_props.py` → `assets/forest_pbr/biome_props.glb`
(skan `s_rock` dla kamienia, `s_plaster` zabarwiony na zielono dla kaktusów) i
`src/realforest/biomekit.rs` z wyborem modeli. W `biome::scatter_region` dodana gałąź
`rocky_kit` / `desert_kit` / `swamp_kit` obok `snow_kit`: ten sam RNG, maski, odstępy i blokery
low-poly, zmienia się tylko to, co jest rysowane (bez `biome_props.glb` wraca stary scatter).
Budżet: grań 0.9–1.25k trójkątów, kopczyk 1k, iglica 1.3–1.8k, saguaro 1.2–2.4k, piarg 0.6–0.9k,
kamyczki pokrycia 60; propsy łączone w chunki jak w lesie (cięcie 75 u), iglice i kaktusy znikają
od 180 u jak drzewa.

Do poprawy przy następnym podejściu: płyty grani wciąż trochę „bochenkowe” (za okrągłe krawędzie,
za jasny ciepły ton pod słońcem pustyni), jałowce z kitu są soczyście zielone jak na suche wyżyny,
saguaro są ciemne i smukłe. Bagno z drzewami kitu wygląda jak las — brakuje olch / wierzb
z ciemniejszą, mokrą korą.

## 5. Kolejność dalszej pracy

1. Bagno: utopione drzewa w `bog.rs` (te same meshe namorzynu, ≤28) + pałki i muchomory;
   własna wierzba / olcha w `trees.py` zamiast lasowych dębów.
2. Złoża rudy w skałach (64 sztuki, gameplay) → kamień `rk_crag_b` + kryształy z Blendera.
3. Łąka przy zamku (7 drzew, 4 głazy, 4 krzaki, ognisko) → gotowe modele z kitu.
4. Twierdza orków: namioty / kolce / palenisko → istniejące GLB z obozów (jedna linia na spawn).
5. Pozostały scatter pustyni (beczki, opuncje, krzaki, kości) i bagna (pałki, muchomory).
6. Piramida, chata wiedźmy, iglica, menhiry — duże sylwety, po jednej sztuce.
7. Twierdza rywala i dekor dziedzińca (pudełka z generowaną teksturą).
