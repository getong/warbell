# Centrum mapy: zamek i miasteczko (design, faza 1)

> Po polsku dla autora; wszystko, co pada w grze, zostaje po angielsku. Źródło fabuły:
> `2026-10-10-kampania-fabula-design.md` (kolonia Korony na Kell, Ser Godric Harrow = Wat, Maud,
> Pip i dzwon, Crane w Akcie II). **Kolonia nie ma kościoła** (ziarno zwrotu B), więc w mieście
> nie ma kaplicy. Sercem miasta jest **wieża dzwonu**, nie świątynia.

## 1. Co gracz ma czuć, akt po akcie

| Akt | Obraz centrum | Emocja |
|---|---|---|
| **Prolog / Akt I „The Toll”** | Ruiny starego keepu, świeże namioty i 2 chaty, klepisko rozjeżdżone przez wozy z plaży, błoto, słoma. Dzwon wisi na prowizorycznej ramie z belek. Pierwsza palisada z bali. | Obóz rozbitków, który dopiero udaje miasto. |
| **Akt II „The Wilds”** | Kamienna kurtyna zamiast palisady, brukowane bramy, rynek z 3–4 straganami, kuźnia, piekarnia, karczma. Po Rozdz. 7 przy bramie wschodniej stoi skład Korony z herbem Crane’a (skrzynie, beczki, żołnierze w obcych barwach). | Miasto żyje i rośnie, ale coraz więcej w nim cudzych barw. |
| **Akt III „The Hold”** | Wyższy keep, wieże z blankami, machiny na murach. Rynek pustoszeje (mniej straganów, zamknięte okiennice), więcej żołnierzy Korony niż handlarzy. Barki milkną. | Twierdza wygrywa z miastem. |
| **Akt IV „The Last Toll”** | Keep zajęty przez Crane’a (jego chorągwie), lud na rynku pod wieżą dzwonu. Epilog RING: pomnik „Ser Godrica” na rynku. Epilog BREAK: pusta rama dzwonu, lemiesz z brązu przy kuźni. | Rynek pod dzwonem jako scena finału. |

Zasada: **każdy akt zmienia centrum widocznie**, ale z tych samych klocków (warianty straganów,
chorągwie, okiennice, liczba NPC przy straganach). To tanie i niesie fabułę bez cutscenek.

## 2. Układ (docelowy, po powiększeniu)

```
                 N brama (droga do lasu / kamieniołomu)
        [stajnie]  ─── trakt (koleiny) ───  [cieśla + skład drewna]
   [spichlerz]          ┌──────────┐            [kuźnia]
 W brama ── trakt ──── │   KEEP    │ ──── trakt ──── E brama (później: przystań / skład Korony)
   [karczma]   RYNEK   └──────────┘   WIEŻA DZWONU + mała ława War Table
   stragany, studnia, pręgierz?       [piekarnia z piecem]
                 S brama (droga na farmy / bagna — stąd przychodzą orki)
```

- **Keep** w centrum (zostaje). **Wieża dzwonu** z platformą dla Pipa, na wprost bramy południowej,
  bo to z południa (bagna) przychodzi noc: dzwon „patrzy” na orki.
- **Rynek** między keepem a bramą zachodnią: bruk, studnia, 3–6 straganów (chleb, sukno, garnki,
  warzywa, ryby), wóz. **Sklepy w domach przy rynku**: kowal (palenisko, kowadło, szyld), piekarz
  (piec chlebowy na zewnątrz), cieśla (kozły, wióry), karczma (ławy, beczki, szyld z dzwonem:
  „The Cracked Bell” — ziarno), spichlerz na palach, stajnie z sianem. **Bez kościoła.**
- Domy mieszkalne przy murach (dzisiejsze `houses()` 12 slotów), ogródki, kurniki.

## 3. Ulepszenia zamku jako progresja wizualna

Mapowanie na istniejące flagi `economy::Defenses` (bez zmiany logiki gry):

| Flaga | Dziś | Docelowo (wizualnie) |
|---|---|---|
| start (`!walls`) | klepisko `PreWalls`, keep tier 0 | Obóz: keep-ruina, namioty, **częstokół z zaostrzonych bali** tylko od południa, rama dzwonu z belek. |
| `walls` | kamienne mury + bruk + keep tier 1 | **Palisada drewniana** na wale ziemnym z rowem (tier 1), błotne bramy z deskami. |
| `gate` | brama | Brama z blanką nad przejazdem, bruk w przejeździe. |
| `towers` | 4 wieże narożne | Drewniane wieże strażnicze → po `tower_mastery` kamienne. |
| `reinforced` | keep tier 2 (iglica, chorągwie) | **Kamienna kurtyna zastępuje palisadę** + większy keep (donżon z wieżą schodową). |
| `ballista`, `keep_archers` | — | Machiny na murach, łucznicy w blankach (już częściowo są). |

Rekomendacja: dodać **tier 0.5 „palisada”** jako osobny `CastleKind` (te same flagi, inny wygląd
przy `walls && !reinforced`), a obecne kamienne mury pokazywać dopiero przy `reinforced`. Modele
z kitu (Blender, `structures.glb`), nie z prymitywów `castle.rs`.

## 4. Podłoże (plan „KCD2”)

Wzór: KCD2 (Kuttenberg, Trosky) — ziemia pod zamkiem to **mozaika zużycia**, nie jedna tekstura:
- **Trakty od bram**: ubite błoto, dwie koleiny od wozów, trawa między koleinami, kałuże w koleinach.
- **Bruk/płyty** tylko tam, gdzie ruch największy: przejazdy bram, rynek, wokół studni i keepu.
- **Wydeptana trawa** z plackami ziemi wzdłuż murów i między domami; **kępy trawy** w narożnikach,
  przy ścianach, gdzie nikt nie chodzi.
- **Słoma/siano** przy stajniach, **wióry** przy cieśli, **sadza/żużel** przy kuźni.
- **Wilgoć**: ciemniejsza ziemia w zagłębieniach, kałuże, rynny/odpływy ze żwiru wzdłuż traktów.

Technika (faza 1, zrobione): maska realforest (`bake_mask`) dostaje „zamkowy” kanał przez R/G
(R = podłoże PBR, G = trakt) — skanowana warstwa *path* (gleba + kamyki + POM + kałuże) na
traktach i klepisku, mech/trawa na brzegach; koleiny wozów od bram wpisane do maski kolein
(`roads::bake_rut_mask`), więc kałuże zbierają się w koleinach. Kod: `src/castle_ground.rs`.
Po murach bruk (`PAVED_RECTS`) leży już tylko na fartuchu keepu i w przejazdach bram, a nie na
całym krzyżu dróg. Faza 2: bruk jako warstwa PBR (CC0 cobblestone z ambientCG) zamiast
proceduralnej płyty, decale słomy/wiórów z kitu, ciemniejsze zagłębienia z wodą przy studni.

## 5. Powiększenie mapy / miasta (PLAN, nie robić teraz)

**Co rośnie:** (a) obwód zamku `HALF_X/HALF_Z` 17×12 → ~26×20 (rynek + sklepy wewnątrz murów);
(b) `SAFE_R` 12.45 → ~17 (bazowe; świat ≈44u płaskiej strefy); (c) `MAP_SCALE` — **nie ruszać**,
bo skaluje całą wyspę (biomy, drogi, wyspy, łodzie, story sites, perf).

**Co psuje powiększenie `SAFE_R`/obwodu:** budżet A* `navgrid::NAV_MAX_NODES` (większy pierścień
płaskiego terenu = więcej węzłów), położenie biomów i przełęczy (`Pass`, przełęcz SE „toward the
castle”), story sites przy krawędzi strefy, działki `town.rs` (pierścień plotów), linie oblężenia
`siege.rs` (punkty startu fal, odległość do bram), `defenses.rs` (pozycje wież/balist), testy
z twardymi współrzędnymi (`campaign_verify`, testy dróg), kamery trailera (`cinematic.rs`).

**Rekomendacja:** jeden krok, gdy biom śniegu i łodzie są zamknięte: `SAFE_R` +4, obwód +50%,
wszystkie pozycje w `castle.rs` jako funkcje `HALF_X/HALF_Z` (już w większości są), potem
przegląd testów i jedna sesja screenshotów. Przystań Crane’a (Rozdz. 7) jako osobny etap.

## 6. Nowe linie głosowe (skrypt; brak TTS w pipeline — nagrać później)

| Klucz | Mówca | Trigger | Linia |
|---|---|---|---|
| `vendor_bread_a` | piekarka | gracz przy straganie z chlebem | "Bread's warm. Prices aren't, but the bread is." |
| `vendor_bread_b` | piekarka | rano po nocy | "Baked through the whole siege. Couldn't sleep anyway." |
| `vendor_cloth` | sukiennik | przy straganie | "Good wool. Orks don't wear it, so you know it's quality." |
| `vendor_pots` | garncarz | przy straganie | "Pots, jugs, bowls. Buy one before the next ram does." |
| `vendor_veg` | warzywniczka | przy straganie | "Turnips. Again. The swamp likes turnips." |
| `smith_a` | kowal | przy kuźni | "Bring me iron and I'll bring you an edge." |
| `smith_b` | kowal | po oblężeniu | "Half the town's swords came back bent. Good. Means they were used." |
| `tavern_a` | karczmarz | przy karczmie wieczorem | "Drink up before the bell. Nobody drinks after it." |
| `guard_gate_a` | strażnik | gracz przechodzi bramą za dnia | "Gate's open till dusk, Ser." |
| `guard_gate_b` | strażnik | o zmierzchu | "Bell soon. Get the carts in." |
| `pip_bell_a` | Pip | gracz przy wieży dzwonu za dnia | "Rope's waxed, Ser! Ready when you say!" |
| `pip_bell_b` | Pip | po pierwszej nocy | "Did you hear it? Loudest bell on Kell!" |
| `maud_market_a` | Maud | gracz na rynku (Akt I) | "A market. Three stalls and a goat. Very royal." |
| `maud_market_b` | Maud | po `reinforced` | "Stone walls. Now the goat feels safe." |
| `crane_quay` | Crane | skład Korony (Akt II) | "The Crown provides. Sign here, Ser Godric." |

## 7. Fazy

1. **Faza 1 (ta sesja):** ten dokument; zróżnicowane podłoże pod zamkiem (maska PBR, koleiny,
   kałuże, wydeptana trawa); jeśli starczy czasu — pierwszy stragan z handlarzem.
2. **Faza 2:** rynek z kitu (stragany ≤3k tri, towary, wóz), handlarze-NPC z barkami (istniejące
   linie `merchant`, `market_a/b`), sklepy (kuźnia, piekarnia, karczma) jako fasady domów.
3. **Faza 3:** progresja zamku: palisada → kamienna kurtyna → większy keep (modele Blender).
4. **Faza 4:** powiększenie obwodu i `SAFE_R` (§5), wieża dzwonu jako budynek.
5. **Faza 5:** warianty aktowe (chorągwie Crane’a, puste stragany Aktu III, pomnik/lemiesz) + VO.
