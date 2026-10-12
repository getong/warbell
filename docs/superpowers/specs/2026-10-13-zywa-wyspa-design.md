# Żywa wyspa: gęstość, postacie i funkcje (design)

> Po polsku dla autora, a wszystko w grze zostaje po angielsku. Nadrzędne są
> `2026-10-10-kampania-fabula-design.md` (tylko do odczytu) i `2026-10-12-wyspa-opowiada-design.md`.
> Ten dokument niczego w nich nie zmienia. Rozszerzenia fabuły opisuje §4, z listą beatów, do
> których się podpinają. Obowiązują stałe zasady: realizm KCD2 (biedne pogranicze), pokaż zamiast
> mówić, brak kościoła, każdy biom inny i mało powtórzeń (drobiazg najwyżej 2×).

## 1. Audyt gęstości (stan `claude/blender-forest-pbr`, `MAP_SCALE` 3.9)

Liczby to szacunki z planerów (`camps::plan`, `ruins`, `vignettes`, `stories_warm/cold`,
`sites_warm`, `wild_sites`, `boss`, `rival`) i z promieni `worldmap::REGIONS`. Środki biomów w
świecie liczę jako `(bx−72, bz−54)·3.9`. Wyspa ma ok. ±277 (X) × ±207 (Z), a Blight z Hold
(12, 230) leży dalej na południu.

| Biom | Środek / zasięg (świat) | Pow. ≈ | Co tam jest | POI ≈ | Na 10k u² | Interaktywne |
|---|---|---|---|---|---|---|
| Śnieg NW | (−179, −117), r≈187, mesa z przełęczami | 49k | Spire, winieta, obóz łowców, Frostgiant, 7 scen `stories_cold`, igloo rozbitków | 14 | 2.9 | 3 |
| Pustynia NE | (144, −133), r≈172 | 39k | Piramida, winieta, raiders, Revenant, twierdza Pashy, 5 scen `stories_warm`, 6 `sites_warm` | 16 | 4.1 | 4 |
| Skały E | (176, 23), r≈148, mesa DEM | 42k | Stones, winieta, jaskinia, Golem, ~5 `stories_cold`, 5 `wild_sites`, ruda | 14 | 3.3 | 3 + ruda |
| Las SW/W | (−156, 101), r≈140 | 35k | Młyn, winieta, szamani, Treant, 4 `stories_warm`, 5 `sites_warm` | 13 | 3.7 | 3 |
| Bagno S | (0, 148), r≈78 | 14k | Chata wiedźmy, winieta, klatki na palach, Bog Hag, 4 `stories_warm`, 5 `wild_sites`, `bog` | 15 | ~10 | 3 |
| Trawa (szew) | pas S zamku, SE wybrzeże | 6k | pola, działki | 0 | 0 | 0 |

**Wniosek.** Liczba punktów nie jest zła (średni odstęp to ~30–50 u), ale **prawie wszystko to
nieme dioramy**. Na biom wypadają tylko **3 rzeczy, które coś robią** (obóz, shrine/trial,
strażnik) plus skrzynie. Między nimi nie ma żadnych **aktorów**: nikt nie chodzi po drogach, nie
handluje, nie pracuje i nie poluje. Bagno jest już gęste, więc dostaje funkcje, a nie nowe miejsca.

**Największe puste obszary** (do potwierdzenia testem z Kroku 0):
1. **Szew S pomiędzy pierścieniem zamku a bagnem**, x −50…30, z 47…95. Tędy co noc idą orki, a
   oprócz pól i działek nie ma tu nic.
2. **Łąka wokół murów** (płaski pierścień do ~±54 × ±47). Stoi na niej 12 działek i 6 pól, a
   pomiędzy nimi jest pusto, zwłaszcza na E (x 36…54) i N (z −36…−47).
3. **SE wybrzeże między bagnem a skałami**, x 40…110, z 120…200: trawa i plaża.
4. **Morze wydm NE**, x 150…250, z −110…−190, między twierdzą Pashy (117, −156) a wybrzeżem.
5. **Szew N wybrzeża śnieg/pustynia**, x −60…20, z −185…−205.
6. **Dalekie W lasu**, x < −200. Ten obszar **jest zarezerwowany pod Wreck Cove (M1)** i zostaje pusty.

## 2. Dodatki (20)

Przy każdym dodatku: **[F]** oznacza istniejącą mechanikę, **[NOWE]** minimalną nową. Lokalizacje
są przybliżone, a planer zawsze reject-samplingiem szuka miejsca przez `poi::site_ok`, z dala od
dróg, działek, obozów i innych scen. Modele powstają w Blenderze (realna skala, base y=0, front
na −Z), a bez kitu jest fallback albo nic się nie spawnuje (jak `stories_warm`).

### A. Obozy orków ×2: pięć nowych, każdy z inną rolą
Dziś `raid_target` wybiera obóz przez preferencję biomu. **[NOWE, małe]** Zamieniamy to na
mapowanie `ThreatKind → CampKind`, a nowe obozy dopisujemy na końcu `plan()` (indeksy 5–9), więc
`rescued_camps` / `cleared_camps` w starych sejwach zostają zgodne.

1. **The Ram Yard (Las, wsch. skraj, ok. (−110, 60)).** Orki ścinają dęby pod taran. Widać
   niedokończony taran na wałkach, okorowane pnie, ślady cioski i kozły. **Funkcja:** obóz
   etapowy dla **Breakers** [F threat], który pojawia się dopiero po `def_walls` (orki odpowiadają
   na nasze mury, pokazane bez słów). **[NOWE]** Akcja E „Fire the ram” (3 s kanału, warband
   szarżuje) czyści zagrożenie bez wybicia całego obozu. **Fabuła:** lustro taranu Crane'a z Rozdz. 9.
2. **The Pitch Seep (Pustynia, wadi przy granicy skał, ok. (120, −60)).** Wyciek bitumu, kotły ze
   smołą na ogniu, pęki pochodni i czarna ziemia. **Funkcja:** etap **Arson** [F]. Kałuże smoły
   parzą jak ogień [F `flame_fx`]. **[NOWE]** Akcja E „Tip the pitch” podpala obóz: zagrożenie
   czyści się, ale łupu nie ma. **Fabuła:** stąd biorą się pochodnie z Rozdz. 2 „Torches”.
3. **The Reed Hide (szew S, ok. (−10, 75), obszar pusty nr 1).** Ukrycie zwiadowców w trzcinie z
   matami do spania i widokiem na mury. Na ziemi leży **makieta naszego fortu z gliny i patyków**,
   na której orki planują szturm (pokazane, nie powiedziane). **Funkcja:** etap **Flank** [F],
   blisko murów, więc to dobry cel na wczesne noce. Trzech zwiadowców, bez klatki.
4. **The Eyrie (Skały, półka nad przełęczą, ok. (200, 40)).** Czatownia zwiadowców z drabiną
   linową, rogiem na słupie i stosem kamieni. **Funkcja [NOWE]:** jeśli zwiadowca dobiegnie do
   rogu, warband najbliższego obozu (jaskini) rusza na bohatera. Ciche oczyszczenie Eyrie
   (podejście od tyłu, przełęczą) odsłania jak z punktu widokowego wszystkie miejsca w promieniu
   ~150 u na kompasie jako „?” (`pilgrim_hint` / `compass`). **Fabuła:** orki obserwują wyspę;
   Rozdz. 6 „The Old Colony” (ekspedycja).
5. **Skarn's Ring (Śnieg, płaska półka przy N wybrzeżu, ok. (−170, −170)).** Wydeptany krąg w
   śniegu ogrodzony włóczniami z czaszkami i porożem, ława z bali, sparujący berserkerzy i
   chorągiew z czerwoną dłonią (znak Skarna). **Funkcja:** obóz-wyzwanie bez zagrożenia nocy, za
   to z **mini-bossem „Hrolk, Skarn's Second”** (powiększony berserker, wzorzec `warlord.rs`,
   `Armory::spawn_prop`). Daje unikalną broń `ring_cleaver` (+26). **Fabuła:** pierwsze ziarno
   Skarna przed Rozdz. 10–11. Wojna jest tu treningiem, a nie odpowiedzią na dzwon.

### B. Bagno: wiedźma i cmentarzysko
6. **Old Seffa, wiedźma (istniejący landmark „The Witch's Hut”).** Chata już stoi (trial +
   shrine). Dokładamy **postać**: starą kobietę w spłowiałej pustynnej chuście, z koszem i
   kosturem, która pracuje przy chacie (warzy, suszy zioła, karmi kozę). Przy furtce leży
   **kamień niemej wymiany**.
   - **Funkcja, etap 1 [NOWE, małe]:** gracz kładzie na kamieniu składnik (E), a o świcie leży tam
     wywar. Seffa nie rozmawia z „rycerzem Korony”, tylko patrzy z okna.
   - **Funkcja, etap 2:** po 3 wymianach albo po Rozdz. 4 (Hamid) drzwi się otwierają i Seffa
     zostaje sprzedawczynią: `ShopVendor::Witch` [F modal `Shop`], która skupuje składniki i
     sprzedaje wywary.
   - **Wywary** (`BuffKind` [F]):

     | Wywar | Działanie | Z czego |
     |---|---|---|
     | `bog_draught` | heal 60 + Resist 30 s | `marsh_herb` + `toad_glow` |
     | `wolfsbane` | Power ×1.4 30 s | `venom` + `vulture_quill` |
     | `hornet_balm` | Haste ×1.3 30 s | `honeycomb` + `goat_charm` |

     **[NOWE, opcjonalnie]** `sleep_smoke`: rzucony w obóz usypia warband na 25 s, co daje
     cichy odbiór jeńców.
   - Lore landmarku zmienia się z „The door never opens.” na stan drzwi.
7. **The Field of the Answered, cmentarzysko orków (płn. skraj bagna na drodze orków, ok. (−25,
   105)).** Rozbudowa istniejących „Ork Barrows” z `wild_sites`, przeniesionych do nowego modułu.
   Rzędy kurhanów, żelazne kamienie z nacięciami, miski z rybą i **świeże kopce, których przybywa
   z każdą przetrwaną nocą** (`min(wave_index, 24)`, wartość pochodna, bez zapisu: wyspa liczy
   uderzenia dzwonu). Za dnia przychodzi 1–2 **starych żałobników**: orki niebojowe, które
   uciekają przed bohaterem i nie są w zapytaniu trafień.
   - **E „Leave an offering” (mięso/ryba):** shrine-buff Resist [F `attach_custom`] +1 do
     przychylności Seffy.
   - **E „Take grave goods”:** +40 zł i orkowa broń, ale flaga `desecrated` odstrasza żałobników
     na stałe, a przez 2 noce przychodzi +2 berserkerów [NOWE `NightMods`].
   - Wybór ma konsekwencje i nikt go nie komentuje.

### C. Stworzenia (5 unikalnych, po jednym na biom)
Każde to samodzielny moduł we wzorcu `snowman.rs` (własny mózg, `Health`, trafialne przez stożek
bohatera), bez edycji `wildlife.rs`. Łup zasila wiedźmę.

8. **Hornet nest (Las, 3 gniazda na dębach).** Szare gniazdo na gałęzi i brzęczenie. Uderzenie w
   gniazdo albo stanie pod nim >4 s wypuszcza rój (cząstki): 4 dmg/s, ucieczka do wody albo na
   >25 u. Zniszczone gniazdo zostawia `honeycomb` (heal 30 + krótki Haste). Odradza się po 2
   świtach. **Fabuła:** pasieka pod murami (meadow) to ludzki odpowiednik.
9. **Lantern Toad (Bagno, przy oczkach, aktywna od zmierzchu).** Ropucha wielkości psa ze
   świecącym workiem gardłowym, przez co z daleka wygląda jak błędne ogniki (`bog.rs` ma wisps).
   Plucie śluzem spowalnia na 3 s, HP 60. Łup: `toad_glow`. **Fabuła:** źródło plotek o
   „światłach na bagnie”.
10. **Carrion vultures (Skały).** 3–5 ptaków krąży nad Gully of the First War i nad każdym trupem
    w biomie, ląduje i żeruje. Atakują tylko bohatera z HP <30% (padlinożercy). **Funkcja:**
    **drogowskaz**, bo sępy krążą też nad nieotwartymi skrzyniami Relic. Łup: `vulture_quill`.
11. **Antlion pit (Pustynia, 3 lejki w wydmach, obszar pusty nr 4).** Lejek w piasku o promieniu
    ~4 u. Wejście ściąga do środka (ruch na zewnątrz ×0.4), a z dna kąsają żuwaczki (14 dmg).
    Zabicie zapada lejek i daje `antlion_chitin`. Odnawia się po 2 świtach.
12. **Wolverine (Śnieg, 2 sztuki).** Rosomak: szybki (7), HP 120. Przy trafieniu **kradnie jeden
    jedzeniowy item z sakwy** i ucieka do nory [NOWE, małe]. Nora jest małym discoverable ze
    skradzionymi rzeczami, w tym z beczułką z łodzi rozbitków. Zabicie zwraca łup + `fur`.

### D. Łąka pod murami (ładna i funkcjonalna)
13. **Common Pasture & Sheepfold (łąka E, x 36…52, z 18…44).** Wiklinowa zagroda, poidło ze
    żłobem, stado ~8 owiec i pastuszek z psem [F `Dog`]. O zmierzchu chłopak zapędza owce do
    zagrody, więc dzwon zapowiada się sam. **Funkcja [NOWE, małe]:** żywe owce dokładają
    +0.1 food/s do `Town::food_rate`, co przyspiesza osiedlanie [F]. W noce Arson podpalacze
    celują też w zagrodę, a od Rozdz. 5 (Pasha w stanie `Harassing`) jego ludzie **kradną 1–2
    owce** (kanon: „wypady na bydło”). Co świt rodzi się jagnię, do limitu.
14. **Militia Butts (łąka N za furtą, ok. (0…20, −38…−46)).** Ziemne kulochwyty ze słomianymi
    tarczami, rząd pali, stojak na broń i ława. Rano 2–4 wieśniaków ćwiczy (smart-spoty
    `village_life` [F]: strzał, cięcie pala). **Funkcja [NOWE, małe]:** dzień z ćwiczeniem daje
    w nocy milicji (muster K [F] i strażnikom) +25% HP i +15% obrażeń. **Fabuła:** Rozdz. 4 „The
    Muster”, a w Rozdz. 9 edykt poboru opróżnia plac, bo ćwiczą już żołnierze Korony.
15. **South Watch Beacon (pagórek na S trakcie, ok. (0, 58)).** Kozioł z koszem smolnym na
    kopcu i drabina. O zmierzchu strażnik wchodzi i zapala ogień, widoczny z dziedzińca.
    **Funkcja:** w noce **Flank** strażnik macha pochodnią w stronę flanki, a na kompasie pojawia
    się strzałka [NOWE, małe]. W noce Arson ogień gaśnie jako pierwszy. Ogień jest pokazany, nie
    opisany.

### E. Wędrowcy i spotkania
16. **The Salt Caravan (trasa: twierdza Pashy → ring road → targ przy bramie W).** Dwa muły w
    jukach, dwóch kupców w barwionych chustach i strażnik z szablą, co drugi dzień przed
    Rozdz. 5. **Funkcja:** wędrowny sklep `ShopVendor::Caravan` z innym asortymentem i skupem
    futer. Na odcinku „szlaku wojennego” ~40% szans na zasadzkę warbandu. Obrona karawany daje
    `shop_discount` [F]. **Fabuła:** po zerwaniu handlu (Rozdz. 5) **karawany przestają
    przychodzić**, a pusty targ mówi wszystko. Orki napadają karawany na szlakach wojennych
    (§11 p.19).
17. **The Unanswering, wygnaniec (Skały, nisza nad jeziorem przy wodospadzie, ok. (110, 90)).**
    Samotny ork przy zimnym ognisku, z połamanym własnym młotem do gongu. Nie walczy, a zaatakowany
    tylko się zasłania. **Funkcja [NOWE, małe]:** podarowane mięso sprawia, że rysuje patykiem
    na ziemi znak, a kompas zaznacza obóz etapowy następnej nocy (`camps::raid_target`). Od
    Rozdz. 10 jego mruknięcia mają napisy.
18. **Tobin, rozbitek (Śnieg, grota przy N wybrzeżu 40–60 u od igloo, ok. (−120, −195)).** Od
    igloo prowadzą **ślady sań** (rząd decali i porzucona płoza). Na końcu leży wychudzony
    chłopak z okrętu pod szalupowym żaglem. **Funkcja:** F „Help him up”, eskorta do fortu (wilki
    po drodze), potem +1 populacja [F recruit] i nazwany wieśniak, który łowi ryby z brzegu.
    **Fabuła:** domyka igloo, choć tylko częściowo: *„Nine came off the reef. Six walked
    inland.”* Gdzie jest reszta, nie wiadomo.
19. **Captive Escort (szlaki wojenne obóz → Hold).** Trzech orków prowadzi 1–2 związanych
    wieśniaków. Pojawia się za dnia po nocy, w której orki dotarły do domów. Przy drodze stoją
    **słupy szlaku wojennego** (czaszka na palu, ochra), które pokazują, skąd idzie noc.
    **Funkcja:** uwolnienie daje +populację (ścieżka `camp_rescue` [F]). **Fabuła:** jeńcy to
    okup za ciszę (§3 Garrok), prowadzeni do Hold.

### F. Drobne wypełniacze (każdy model najwyżej 2×, inny w każdym biomie)
20. **Skrytki biomowe** (10 modeli, po 2 na biom), ukryte w obszarach pustych 3–5:
    - las: wydrążony pień z zawiniątkiem; linia wnyków kłusownika;
    - pustynia: zakopany dzban przy kopczyku; zasypana juka wielbłąda;
    - skały: kopczyk z niszą; worek górnika pod nawisem;
    - śnieg: zamarznięty tobołek na nartach; skrzynka z łodzi rozbitków;
    - bagno: zatopiona skrzynka na palu; kosz rybaka.

    **Funkcja:** loot z puli skrzyń [F `chest.rs`, tier wg odległości] + mini-discovery
    [F `attach_story`].

## 3. Kontrakt danych (wspólny dla pakietów)

Nowe ID przedmiotów w `crates/core/src/inventory.rs`:
- **składniki:** `honeycomb`, `toad_glow`, `vulture_quill`, `antlion_chitin`;
- **wywary:** `bog_draught`, `wolfsbane`, `hornet_balm`, `sleep_smoke`;
- **broń:** `ring_cleaver` (dmg 26).

Nowe flagi w `WorldFlags` (klucz → i64):
- `witch_trades`, `witch_open`, `witch_favour`;
- `graveyard_desecrated`;
- `tobin_rescued`;
- `outcast_alive`;
- `eyrie_cleared`;
- `ram_burned_day`;
- `sheep_count`.

## 4. Rozszerzenie fabuły

Wszystkie rozszerzenia są **opcjonalne (PULL)** i żadne nie zmienia beatu kanonu. Przed
Rozdz. 10 orki mówią bez napisów.

| Rozszerzenie | Historia (krótko) | Podpięcie pod kanon |
|---|---|---|
| **Old Seffa** | Zielarka i akuszerka z pierwszego pokolenia ludu Pashy. Idris wygnał ją, bo **obmywała i grzebała zmarłych orków**: jako jedyny człowiek odprawia ich pogrzeby i dlatego orki jej nie tykają. Zna prawo żelaznego głosu, ale „nikt jej nie pytał”. | **Rozdz. 3:** w noc gorączki Pipa można (opcjonalnie) pójść po wywar. Seffa daje go i nasłuchuje ciszy od strony fortu, kiwając głową (ziarno B, bez słów). **Rozdz. 4:** Hamid poznaje ją („Auntie Seffa”), drzwi się otwierają. **Rozdz. 5:** Hamid w drodze wspomina, za co ją wygnano. **Rozdz. 12:** to ona prowadzi Maud do szamanki-wdowy. |
| **Field of the Answered** | Cmentarz tych, którzy „odpowiedzieli” na dzwon. Każda noc dokłada kopiec. | Ziarno **B** i **Rozdz. 10** (*„My brother answered last winter”*); **Rozdz. 6** (ekspedycja). Po zwrocie B gracz rozumie, że sam kopał te groby. |
| **The Unanswering** | Wojownik, który nie odpowiedział na wezwanie. Według prawa jest nikim, a jego młot jest połamany. | Ziarno **prawa żelaznego głosu** (§2); **Rozdz. 10** z napisami: *„I did not answer. So I am no one.”*; **Akt IV:** dołącza do ludu Garroka (BREAK). |
| **Skarn's Ring / Hrolk** | Młodzi berserkerzy Skarna trenują wojnę jako sposób życia. | Ziarno **Skarna** (§3) przed **Rozdz. 11** (krwawa wojna). W BREAK Hrolk stoi przy Skarnie w nocnej fazie. |
| **The Ram Yard** | Orki odpowiadają na nasze mury taranem. | **Akt III:** lustro taranu Crane'a („oba ludy budują to samo”). |
| **Salt Caravan** | Codzienny handel Pashy, którego nikt nie zauważa, dopóki nie zniknie. | **Rozdz. 5** (zerwanie handlu = koniec karawan); §11 p.19; **Rozdz. 8:** Hamid poznaje kupca z karawany. |
| **Tobin** | Chłopiec okrętowy z szalupy z igloo. | Ziarno **B** z prologu (dzwon okrętowy); **Rozdz. 7:** Tobin rozpoznaje dzwon okrętowy w obozie Crane'a i blednie. |
| **Pasture / Butts / Beacon** | Codzienność kolonii pod murami. | **Rozdz. 5** (kradzieże owiec), **Rozdz. 4** (muster), **Rozdz. 9** (pobór), **Rozdz. 11** (beacon gaśnie, gdy Wat trzyma bramę). |

Czego **nie robimy**: drugiego dzwonu, nowej strony Anselma (5 etapów jest zamkniętych) ani
kaplicy czy kościoła. Seffa nie jest Bog Hag (strażnik) i plotka *„eats fingers”* (`story_witch`)
myli je celowo.

## 5. Pakiety pracy (4 równoległe, po ~60–90 min)

**Krok 0 (koordynator, ~30 min, przed startem agentów).** Robi wspólne rzeczy, żeby pakiety nie
dotykały tych samych plików:
- `interaction.rs`: generyczny komponent `Interactable { prompt, radius }` + wiadomość
  `Interacted(Entity)`, bez nowych wariantów `InteractKind` per pakiet;
- `economy.rs` + `core/shop_catalog.rs`: zasób `ShopVendor { Market, Witch, Caravan }` + puste
  katalogi;
- `core/inventory.rs`: wszystkie ID z §3;
- `savegame.rs`: `world_flags: BTreeMap<String, i64>` (`#[serde(default)]`) + zasób
  `WorldFlags` (snapshot / apply / reset przy New Game);
- `siege.rs`: zasób `NightMods { extra_berserkers, nights_left }` czytany przy budowie fali;
- test `density_report` (siatka 40 u, liczba zaplanowanych miejsc w komórce, puste komórki
  wypisane) jako twardy audyt §1.

**Dotknięcia jednoliniowe dozwolone każdemu pakietowi:** `main.rs` (plugin), `worldmap.rs`
(wywołanie `plan()` obok `wild_sites::plan` + populate w fazie 32), `poi.rs`
(`planned_footprints`). Kolejność merge: K0 → WP2 → WP1 → WP3 → WP4. Konflikty będą tylko
sąsiednimi liniami.

| Pakiet | Zakres (§2) | Pliki na wyłączność | Blender |
|---|---|---|---|
| **WP1 Orki** | 1–5, 17, 19 | `camps.rs`, `core/threat.rs` (mapowanie `ThreatKind → CampKind`), nowe `war_party.rs` (eskorta, słupy, wygnaniec), `compass.rs` | `ork_camps.py` (+5 layoutów), `ork_folk.py` (wygnaniec, słupy) |
| **WP2 Bagno** | 6, 7 (+ katalog Witch) | nowe `witch.rs`, `ork_graveyard.rs`; `landmarks.rs` (meta i lore Witch's Hut); `wild_sites.rs` (wycięcie Barrows); treść katalogu Witch w `shop_catalog.rs` | `swamp_folk.py` (Seffa, kamień wymiany, kopce, żałobnicy) |
| **WP3 Dzicz** | 8–12, 18, 20 | nowe `oddities.rs` (5 stworzeń), `stashes.rs`, `castaway.rs`; `player/combat.rs` + `player/arts.rs` (jedna linia `With<Oddity>`); `stories_cold.rs` (ślady sań); `chest.rs` (pula łupu dla skrytek, tylko odczyt API) | `oddities.py`, `stashes.py` |
| **WP4 Łąka** | 13–16 | `meadow.rs`, nowe `pasture.rs`, `drill_yard.rs`, `watch_beacon.rs`, `caravan.rs`; `core/town_store.rs` (człon pastwiska); `village_life.rs` (spoty ćwiczeń); `rival.rs` (kradzież owiec, bramka karawan); treść katalogu Caravan | `meadow_kit.py` (owce, zagroda, kulochwyty, beacon), `caravan.py` (muły, juki) |

**Zasady dla każdego pakietu** (CLAUDE.md):
- systemy symulacji mają `.run_if(in_state(Modal::None))`;
- encje świata są tagowane `BiomeEntity`;
- każdy stan gracza idzie przez `WorldFlags` (round-trip sejwu + reset przy New Game);
- napisy w grze są po angielsku, krótkie i bez wykładu;
- weryfikacja: `cargo test` (planer trafia w biom, nie nachodzi na inne sceny) + jedno ujęcie
  `FOREST_SHOT` na pakiet; modele osobno przez `FOREST_VIEW`;
- gry nie uruchamia się do „grania”. Kryterium odbioru: test `density_report` pokazuje, że obszary
  1–5 z §1 mają co najmniej jeden punkt interaktywny.
