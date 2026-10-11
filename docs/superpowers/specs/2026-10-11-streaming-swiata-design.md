# Streaming świata i LOD po powiększeniu mapy ×1,5 (design)

> Kontekst: `MAP_SCALE` 2,6 → 3,9 (gałąź `feat/map-scale-150`). Mapa zostaje duża; ten dokument
> mówi, jak ją utrzymać w pamięci i w czasie ładowania. Część 1 jest już zrobiona (gałąź
> `perf/map-scale-mem`), części 2–5 to plan dalszej pracy, w kolejności.

## 0. Pomiary (RTX 5060 Ti, i5-12400F, `FOREST_PERFTEST=75 FOREST_PERFROAM=1`)

Na starcie (3,9, przed zmianami): ładowanie do `WorldReady` 25,6 s (44 s pod obciążeniem innych
buildów), RSS 7,7 GiB, 34k encji, 14,3k meshy. Raport `MEM` (`FOREST_MEMREPORT=1`, 12 s po
`WorldReady`) pokazał, że **5,2 GiB z 7,7 to kopie CPU meshy** (97,6 mln wierzchołków), z czego:

| Właściciel (komponenty encji) | MiB | meshe | wierzchołki |
|---|---|---|---|
| `DensitySlice GroundCoverChunk` (podszyt kitu realforest) | 2135 | 4387 | 30,5 mln |
| `GroundCoverChunk` (trawa/kwiaty `biome::spawn_chunks`) | 1597 | 439 | 41,9 mln |
| `DensitySlice FoliageExt GroundCoverChunk` | 523 | 3651 | 6,7 mln |
| `BiomeEntity` (głównie chunki terenu + LOD) | 349 | 601 | 9,1 mln |
| `DensitySlice` (propsy kitu: kamienie, kłody) | 192 | 1082 | 2,6 mln |
| `SnowKitExt` (podszyt + propsy śnieżne) | 234 | 1443 | 3,2 mln |

Obrazy: 297 MiB kopii CPU (tablice tekstur BC7 kitu, maski terenu) — drugorzędne.
Czas: faza 0 (arkusz trawy) 7,7 s, arkusze bagna/Blight 2,1 s, scatter biomów 5–9 ok. 8 s, a do
tego klatki między fazami (upload ~5 GB wierzchołków na GPU) — pojedyncze klatki po 3 s.

## 1. Zrobione (gałąź `perf/map-scale-mem`)

1. **Meshe tylko na GPU** (`RenderAssetUsages::RENDER_WORLD`) dla chunków terenu (+ drape LOD),
   chunków `biome::spawn_chunks` i scalonych grup kitu. Nikt ich nie czyta na CPU (zapytania o
   grunt idą przez cache kafli; `reskin` widzi nowe chunki w PostUpdate klatki spawnu, przed
   ekstrakcją, a teraz używa `try_attribute`, więc nie spanikuje). RSS 7,7 → 1,8 GiB.
2. **Równoległy build** (`crate::par::par_map`, wątki scoped, kolejność wyników zachowana):
   meshowanie chunków terenu, klasyfikacja siatki kafli, scalanie grup chunków. Faza 0
   7,7 → 1,3 s; ładowanie 26 → 21 s.
3. **Streaming podszytu kitu** (`realforest::stream_cover`): `Chunks::spawn` odkłada kompaktowe
   przepisy (model, część, transform) per chunk 16u, a system spawnuje tylko chunki w promieniu
   `STREAM_IN` = 95u od kamery (XZ do środka chunka), despawnuje za `STREAM_OUT` = 119u.
   Scalanie idzie **asynchronicznie** na `AsyncComputeTaskPool` (max 32 nowe klucze/klatkę,
   najbliższe pierwsze), chunk pojawia się w całości, gdy jego zadanie skończy; zadanie dla
   chunka, od którego kamera już odjechała, jest anulowane. (Wersja synchroniczna z `par_map`
   w klatce dławiła się do 300 ms/klatkę, gdy maszynę obciążały równoległe buildy.) System stoi,
   dopóki `WorldReady` jest fałszywe, więc przy przebudowie świata nie zostają sieroty. Każdy
   tier i tak jest ucinany `VisibilityRange` ≤ 75u (`PROPS_FAR`), więc nic widocznego nie znika
   (strzały porównawcze z `FOREST_NOSTREAM=1` identyczne). Ładowanie 21 → 10–13 s.
   `FOREST_NOSTREAM=1` / `FOREST_NOCULL=1` = stara ścieżka (wszystko naraz).

## 2. Następny krok: streaming trawy `biome::spawn_chunks` (1,6 GiB VRAM, 41,9 mln wierzch.)

- **Co**: kubełki `cover` i `props` z `biome::spawn_chunks` (chunk 16u, `COVER_CHUNK`).
- **Problem**: `PendingProp` trzyma gotowy, pokolorowany `Mesh` każdego kępka, więc przepis nie
  jest kompaktowy. Trzeba zamienić go na (rodzaj propa, seed/odcień, transform) i budować mesh
  kępka w momencie scalania — to te same funkcje, które dziś wołamy w scatterze.
- **Promienie**: cover ucina się na 62u, propsy na 75u → `STREAM_IN` 95u, `STREAM_OUT` 119u (jak
  w kroku 1, jeden wspólny system i jeden magazyn z typem przepisu).
- **Zysk**: ~40 mln wierzchołków mniej na GPU i w uploadzie; scatter faz 5–9 krótszy o scalanie.

## 3. Drzewa: instancjonowanie + impostor daleki

- Dziś każde drzewo kitu to encja-korzeń + dzieci (LOD0 0–30u, LOD1 30–180u), ok. 9k encji
  z dziećmi. Zostają **globalne** (rąbanie, blokery, kolizje), ale:
  - pas 120–260u: **impostor** (2 skrzyżowane karty z atlasu wypieczonego z LOD1, crossfade
    `VisibilityRange` 110–130u), bez cienia;
  - encje-dzieci LOD0/LOD1 tworzone tylko w promieniu 190u (ten sam magazyn co w kroku 1,
    chunk 48u), daleko zostaje sama encja-korzeń z danymi gry + impostor scalony per chunk.
- Kolejność: najpierw scalony impostor per chunk 48u (tani, duży zysk w liczbie encji), potem
  streaming dzieci LOD0/LOD1.

## 4. Teren: chunki zostają globalne, LOD trzypoziomowy

- Chunk 48 kafli (`TERRAIN_CHUNK`) zostaje. Teren musi być zawsze (mapa świata, horyzont), więc
  się nie streamuje — tylko LOD:
  - LOD0 pełny: < 150u (jak dziś),
  - LOD1 stride 2: 150–320u (jak dziś drape),
  - **nowy LOD2 stride 6**: > 320u, bez ścian tarasów (zysk na krawędziach wyspy przy
    widokach z lotu ptaka i w mapie świata).
- Pełny LOD0 może być budowany leniwie (dopiero gdy kamera zbliży się na 200u), bo drape LOD1
  wystarcza na starcie — to skraca fazę 0 o kolejne ~60%.

## 5. Dekoracje miejsc fabularnych i POI

- Plany (`poi::plan`, `stories_*::plan`, `vignettes`, `wayside`) zostają globalne i liczone przy
  starcie (ścieżki oblężenia, kolizje, questy ich potrzebują).
- **Wizualna dekoracja** (meshe, cząstki, światła) spawnuje się, gdy kamera jest < 160u od
  środka miejsca, despawn > 200u. Encje z logiką gry (skrzynie, NPC, bossowie) zostają zawsze.
- Mgła (`FOG_BASE_START` ≈ 56u, koniec ≈ 142u) chowa pojawianie się; przy czystym niebie
  progi wyżej o 40u.

## 6. Harness i widok mapy

- `FOREST_SHOT`/`FOREST_CLIP`: system streamingu działa w każdej klatce bez bramki modalnej;
  rozgrzewka strzału (≥240 klatek) z budżetem 32 kluczy/klatkę kolejkuje całe otoczenie
  kamery w ~4 klatki, a zadania kończą się po kilkunastu klatkach. Dla `FOREST_SHOT_CAMS` kamera jest przestawiana — streaming nadąża w tej samej
  klatce. Docelowo: `capture` czeka na flagę „stream ustabilizowany” (brak `dirty`).
- Mapa świata (widok z góry) nie pokazuje podszytu ani tak (cull ≤ 75u), więc nic nie traci.
- Gameplay globalny bez zmian: wysokości gruntu (`ground_at_world`, cache kafli), navgrid,
  plany miejsc, ścieżki oblężenia, blokery drzew.

## 7. Kolejność prac

1. (zrobione) GPU-only meshe, równoległy build, streaming podszytu kitu.
2. Streaming trawy `biome::spawn_chunks` (przepis kompaktowy).
3. Impostory drzew per chunk 48u + streaming dzieci LOD.
4. LOD2 terenu + leniwy LOD0.
5. Streaming dekoracji POI/stories.
6. `capture`: czekanie na stabilny stream; test regresji pop-in (strzały 0/90/180° wokół
   kamery na granicy `STREAM_IN`).
