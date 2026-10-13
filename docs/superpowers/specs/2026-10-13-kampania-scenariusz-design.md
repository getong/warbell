# Warbell — scenariusz kampanii (dialogi, reżyseria cutscenek, budżet animacji)

**Status:** szkic v1, 2026-10-13. Rozwija plan fabuły z `2026-10-11-centrum-mapy`, `2026-10-11-zamek-v2`,
`2026-10-12-wyspa-opowiada`, `2026-10-13-zywa-wyspa`, `2026-07-01-kampania-misja-1`. Master spec
`2026-10-10-kampania-fabula-design.md`, na który te dokumenty się powołują, **nie istnieje w repo** —
beaty poniżej odtworzono z cytatów w specach pochodnych; tam, gdzie zgadywałem, stoi *(inferred)*.

Tekst w grze: **angielski**. Dokument: polski.

---

## 0. Twarde ograniczenia (żeby nie obiecywać gruszek na wierzbie)

**Animacje postaci.** Mamy w repo Quaternius UAL 1+2 Standard (CC0), 48 klipów wypieczonych na każdym z
14 NPC-ów (`tools/npc_mpfb/export_game.py::CLIPS`). Wszystko, co scenariusz każe NPC-om robić, mieści
się w jednej z trzech puli:

| Pula | Źródło | Status | Przykłady |
|---|---|---|---|
| **A — gotowe** | UAL w `assets/npc/*.glb` | działa dziś | Idle/Walk/Sprint, Idle_Talking, Sitting_* (w tym Sitting_Talking), Idle_FoldArms, Yes, Idle_No, Idle_Rail_Call, Idle_Torch/Lantern, Walk_Carry, Push, Consume, Chest_Open, PickUp_Table, Interact, Fixing_Kneeling, Farm_*, TreeChopping, Sword_*, Punch_*, Hit_Chest/Head/Knockback, Death01, Roll, Crouch_Idle, LayToIdle, Dance |
| **B — do pobrania** | Mixamo (darmowe, nie-CC, OK w grze, nie redystrybuować surowych FBX) → `bake_anims.py` retarget → `NPC_X_*` | 1 dzień pipeline'u | Kneel (hołd), Bow, Salute, Pray, Point, Wave, Beckon, Clap, Cheer, Laugh, Cry, Shrug, Look Around, Surrender (hands up), Death02/03, Collapse, Stumble, Sleeping |
| **C — ręcznie / fizyka / kamera** | nasze | per-scena | walące się budynki, dzwon (jest `castle::swing_bell`), ogień, dym, rozbita łódź, dwuosobowe interakcje (uścisk, przekazanie przedmiotu — **tylko montażem**: cięcie na zbliżenie dłoni + prop) |

Zasady pisania pod to:
- **Żadnych dwuosobowych animacji kontaktowych.** Zamiast uścisku: ujęcie na twarze + cięcie. Zamiast
  wręczenia przedmiotu: prop znika u A, pojawia się u B pod cięciem.
- **Klipy są in-place** (brak root motion) — ruch aktora robi `demo.rs`/`cinematic.rs` przez transform.
- **Rekwizyty w dłoni:** tylko pochodnia, latarnia, miecz, tarcza. Pergamin/kielich/dzwonek = osobna
  encja przyczepiona do kości dłoni (tanie, ale do zrobienia).
- Cutscenki nie wymagają nowych modeli: Maud = `elder_f`, Pip = `boy`, Crane = `merchant` (przebrać
  w ciemny płaszcz — warianty materiałów), Hamid = `rival_kit` oficer, Seffa = `swamp_folk`,
  Anselm = `priest` (tylko w jednej scenie retrospekcji / lub wcale — dziennik), Tobin = `boy`.
- Głosy, SFX, muzyka: generator — nie ograniczają scenariusza.

**Maszyneria w kodzie** (jest): `subtitles.rs` (caption z mówcą, `force`), `cinematic.rs` (F1 director: Wave,
Salute, Point, ArmsCrossed, Cheer, Work, timelapse nieba, marsz orków), `demo.rs` (aktorzy + kamera,
frame-lock), `scenes.rs` (tableau), slow-mo + swing kamery z `succession.rs`, `castle::swing_bell`.
Brakuje: letterbox + lock inputu, kolejka „Shot” (kamera→aktor→linia→czas), fade-to-black. To jeden
moduł `cutscene.rs` (~300 linii) — opisany w §6.

---

## 1. Ton

Jedno zdanie: **Kingdom Come, gdyby komentował je zmęczony człowiek, który wie, że i tak będzie musiał to
odbudować.**

Reguły:
1. **Sarkazm bierze się z pracy, nie z fabuły.** Żarty są o tym, że moat jest „za drogi”, że Korona
   „zapewnia” (formularz), że bohaterstwo nie płaci za kolację. Nigdy o tym, że ktoś umarł.
2. **Jeden żart na scenę, nie trzy.** Scena ma pointę, nie stand-up. Jeśli dwie linie są śmieszne,
   jedna wylatuje.
3. **Śmieszni są ludzie, nie świat.** Świat (wyspa, orki, dzwon) jest traktowany serio. Komedia to
   reakcja ludzi na serio.
4. **Zmęczenie zamiast cynizmu.** Wat nie jest edgy. Jest po prostu po czterdziestce i chce się wyspać.
5. **Nikt nie mówi o twiście.** Dzwon-zew orków nikt nie wypowiada wprost aż do Ch.10. Wcześniej:
   tylko szczegóły, które gracz składa sam (kurhany, kartki Anselma, orki mają imiona).
6. **Mieszkańcy przebijają patos.** Wat zrobi coś heroicznego; wieśniak komentuje, ile to kosztowało.
7. **Krótko.** Linia ≤ 14 słów. Cutscenka ≤ 45 s. Wszystko dłuższe gracz kliknie skip i będzie miał rację.

Kalibracja (z istniejącego VO, zostaje jak jest):
- „Hear the drums? They're not celebrating. They're counting.”
- „I said dig a moat. 'Too dear,' they said.”
- „He laid three stones. Then he supervised.”
- „Bless you for the protection. The screaming at night is a lovely touch.”

---

## 2. Postacie — karty głosu

**WAT (Ser Godric Harrow)** — bohater, narrator. Rozbitek. Przyjął imię utopionego giermka z grobu
na King's Road *(inferred: tożsamość to twist seed, nie wypowiadamy go nigdy — gracz widzi pusty grób
„Godric Harrow, squire” i słyszy, jak ludzie mówią „Ser Godric”; to wystarczy)*.
Głos: niski, zmęczony, krótkie zdania, zero przymiotników. Nie żartuje — stwierdza.
- „Quiet day. I've learned not to trust quiet days.”
- „Heroism doesn't pay for supper.”

**MAUD** — gubernatorka kolonii. Tablica edyktów, atrament, bardzo kompetentna, bardzo bez złudzeń.
Jedyna osoba, która wie więcej niż mówi. Głos: sucho, precyzyjnie, lekki uśmiech w podtekście.
- „A market. Three stalls and a goat. Very royal.”
- „Write it down. If we live, it's a record. If not, it's a will.”

**PIP** — chłopak od dzwonu, ~11 lat. Jedyna szczera osoba na wyspie. Dzwon jest jego całym światem.
Głos: szybki, entuzjastyczny, bez ironii — **on jest kontrapunktem** do wszystkich.
- „Did you hear it? Loudest bell on Kell!”

**CRANE** — agent Korony. Uprzejmy, grzeczny, formularz zawsze gotowy. Nigdy nie kłamie wprost.
Głos: miękki, urzędowy, lekko zachwycony własną uprzejmością.
- „The Crown provides. Sign here, Ser Godric.”
- „Nobody is *conscripting* anybody. We're *inviting*. With a quota.”

**OLD SEFFA** — zielarka ze bagna. Grzebie orcze trupy; dlatego orki ją omijają. Jedyna, która zna
orków jako ludzi. Głos: szorstko, bez patosu, uczciwie.
- „You want a cure or a sermon? Cure's two coppers. Sermon's free. Nobody takes it.”

**HAMID** — wysłannik Paszy. Kupiec-dyplomata, uśmiech na sprzedaż. Zna „Auntie Seffa”.
- „The Pasha sends his regards. And a price list.”

**BROTHER ANSELM** — mnich z pierwszej kolonii sprzed stu lat. Tylko dziennik (kartki po biomach) +
jeden głos z offu przy czytaniu. Styl: kronikarski, coraz krótszy, aż do urwania.

**GARROK / SKARN / HROLK / WARLORD** — orki. Do Ch.10 bez napisów (gracz słyszy tylko krzyki). Od
Ch.10 **napisy włączają się** — to jest beat fabularny: nie zmieniamy orków, zmieniamy słuch gracza.
- Garrok: „Ransom for silence. Gold for the bell. Fair.”
- Skarn: „Iron called. We answered. We always answer.”

**TOBIN** — chłopiec okrętowy, rozbitek w śniegu. „Nine came off the reef. Six walked inland.”

**THE UNANSWERING** — ork-wyrzutek. Jedna scena. „I did not answer. So I am no one.”

---

## 3. Struktura

```
AKT I   THE TOLL        Ch.0 Prolog · Ch.1 First Toll · Ch.2 Torches · Ch.3 Pip's Fever
AKT II  THE WILDS       Ch.4 The Muster · Ch.5 Price List · Ch.6 The Old Colony · Ch.7 Crane's Quay
AKT III THE HOLD        Ch.8 Granary · Ch.9 The Draft · Ch.10 Subtitles · Ch.11 The Bloody War
AKT IV  THE LAST TOLL   Ch.12 Seffa & Maud · Finał (Warlord) · Epilog RING / BREAK
```

Ch.1–3 mapują się 1:1 na istniejącą 3-nocną kampanię z `crates/core/src/campaign.rs` (militia →
captives → farm → bell / torch raiders / ritual camp). Nowe to prolog + cutscenki + Ch.4+.

Format każdej sceny: **Cel gracza** → **Cutscenka** (ujęcia, klipy) → **Dialog** → **Gameplay hook**.
Oznaczenia klipów: `[A:Nazwa]` gotowe, `[B:Nazwa]` Mixamo, `[C:…]` ręcznie/kamera.

---

## AKT I — THE TOLL

### Ch.0 — Prolog: Wreck Cove *(nowe)*

**Cel:** 90 sekund, zero mechanik. Ustawia: morze, dzwon, że Wat nie jest tym, za kogo go wezmą.

**Cutscenka (≈40 s, czarne → fade in):**
1. Czerń. Dźwięk: fale, dzwon okrętowy, nierówno, słabnący. Napis: *„Kell. A Crown colony. Allegedly.”*
2. **Shot 1** — niska kamera na plaży, świt, mgła (`FOREST_TIME≈0.05`). Rozbita łódź `[C: statyczny prop
   wraku + pływające deski]`. Wat leży twarzą w piasku `[A:LayToIdle` zatrzymany na 1. klatce`]`.
3. **Shot 2** — zbliżenie: dłoń Wata zaciska się na piasku. `[A:LayToIdle` od klatki 0 → wstaje`]`.
   Kamera wstaje z nim.
4. **Shot 3** — nad ramieniem: w głębi, na skale, ktoś mały ciągnie za sznur dzwonu okrętowego
   przywiązanego do masztu `[C: dzwon = reuse `castle::swing_bell` na małym meshu; postać `boy` z
   `A:Idle_Rail_Call` w pętli (ręce w górze, ciągnie)]`. To Pip. Dzwoni od nocy.
5. **Shot 4** — Wat idzie w jego stronę `[A:Walk_Loop`, lekko kuleje = speed 0.7`]`. Pip przestaje,
   patrzy `[A:Idle_Loop]`.

**Dialog:**
> PIP: You're alive. I rang all night. Figured someone would hear.
> WAT: Someone did.
> PIP: *(dumny)* Loudest bell on Kell.
> WAT: *(patrzy na wrak)* Only bell on Kell, I'd wager.
> PIP: Not for long. Governor's casting a proper one. Royal pattern.
> WAT: *(pauza)* Of course she is.

6. **Shot 5** — Pip biegnie w górę ścieżki `[A:Sprint_Loop]`, Wat za nim `[A:Walk_Loop]`. Kamera zostaje
   przy wraku, pan w dół na tabliczkę przybitą do deski: *„G. HARROW, squire — lost at sea”*. Cięcie.

**Hook:** `FOREST_DEMO=explore` prowadzi gracza King's Road do zamku; po drodze pusty grób z tą samą
tabliczką (jest w `sites_warm.rs`). Nic nie komentujemy.

---

### Ch.1 — First Toll (noc 1: milicja → klatki → farma → dzwon)

**Cel:** istniejąca Noc 1. Dodajemy dwie krótkie sceny: przyjazd + dzwon.

**Cutscenka A — Brama (≈25 s):** Maud przy tablicy edyktów `[A:Interact` (pisze)`]`, odwraca się
`[A:Idle_FoldArms_Loop]`.

> MAUD: Ser Godric. We'd given you up. The sea usually keeps what it takes.
> WAT: *(bez korekty)* …It made an exception.
> MAUD: Good. Exceptions are all we have left. Militia's in the field. The field's on fire.
> WAT: Where?
> MAUD: *(wskazuje piórem, nie ręką — `[A:Interact]` wystarczy)* Follow the smoke. We've plenty.

Pointa sceny to „It made an exception” — Wat przyjmuje cudze imię jednym zdaniem i nigdy więcej do
tego nie wracamy.

**Gameplay:** jak dziś (`campaign.rs` Night 1). Istniejące VO zostaje:
„They've taken our people. Gather the militia. We're getting them back.” / „You're home. Back to the
fields. Heroism doesn't pay for supper.” / „Food and defenders. Almost looks like I know what I'm doing.”

**Cutscenka B — Pierwsze uderzenie (≈30 s, przed zmierzchem):**
1. Pip na platformie dzwonu `[A:Idle_Rail_Loop]`, Wat wchodzi po schodach.
2. > PIP: She said I ring it. Every dusk. Me.
   > WAT: Then ring it.
   > PIP: What if nobody comes?
   > WAT: *(patrzy na las)* Someone always comes.
3. `[C: castle::swing_bell]`, kamera odjeżdża od wieży w górę i na zewnątrz **nad las** — w ostatniej
   sekundzie w ciemności zapalają się pochodnie `[A:Idle_Torch_Loop` na 6 orkach`]`. Cięcie na HUD nocy.

Istniejące VO: „Time to ring the bell. Invite the neighbours. The ugly ones.” — gra **po** cutscence.

---

### Ch.2 — Torches (noc 2: podpalacze)

**Cel:** jak dziś. Jedna scena poranna po nocy 1.

**Cutscenka (≈20 s):** świt, spalone pole, wieśniak `[A:Fixing_Kneeling]` przy płocie, drugi
`[A:Walk_Carry_Loop]` z deskami. Wat przechodzi.

> FARMER: Bless you for the protection. The screaming at night is a lovely touch.
> WAT: You're welcome.
> FARMER: Wasn't thanking you.
> WAT: I know.

Istniejące VO: „Torch bearers. Keep them off the farms. I prefer my wheat uncooked.”

**Nowy drobny beat (seed twistu):** po nocy, przy padłym orku, wieśniak: „Look. Beads. Carved.” Wat:
„Loot it or bury it. Don't stand there.” — pierwsze „orki mają rzeczy”.

---

### Ch.3 — Pip's Fever (noc 3: rytuał szamanów)

**Cel:** Pip ma gorączkę; dzwon musi zadzwonić. Dzwoni Wat. Rytuał szamanów (istniejąca noc 3).

**Cutscenka A (≈30 s):** izba, Pip leży `[A:LayToIdle` pierwsza klatka, pętla oddechu = subtelny
scale`]`, Maud siedzi `[A:Sitting_Idle_Loop]`, kubek na stole.

> MAUD: Swamp fever. He'll live. Probably. Seffa's mix helps.
> WAT: Seffa.
> MAUD: Witch. Bog. Buries the orks' dead, so they leave her be. Don't ask me how that works.
> WAT: *(bierze kubek `[A:PickUp_Table]`)* Who rings tonight?
> MAUD: *(patrzy na niego)*
> WAT: …Of course.

**Cutscenka B (≈15 s):** Wat na platformie, ciągnie sznur `[A:Idle_Rail_Call]`. Dzwon `[C]`. Z offu, ledwo
słyszalne pod dźwiękiem — pierwszy raz **bębny odpowiadają od razu**. Wat: „Hear the drums? They're not
celebrating. They're counting.” (istniejące VO).

Istniejące VO po nocy: „Ritual broken. Apparently, swords are bad for morale.”

**Koniec Aktu I — tytuł na czerni:** *„ACT II — THE WILDS”*.

---

## AKT II — THE WILDS

### Ch.4 — The Muster (Hamid, klatki, pierwszy Muster K)

**Cel:** nauczyć `K` (zbiórka). Przedstawić Paszę przez Hamida.

**Cutscenka (≈35 s):** karawana przy bramie (`caravan.glb`: muły, kupcy). Hamid `[A:Idle_Talking_Loop]`,
Maud `[A:Idle_FoldArms_Loop]`.

> HAMID: The Pasha sends his regards. And a price list.
> MAUD: We have three stalls and a goat.
> HAMID: *(nieporuszony)* The goat is not on the list. The *bell* is. Bronze fetches well.
> WAT: The bell's not for sale.
> HAMID: Nothing is, Ser Godric. Until it is. *(kłania się `[B:Bow]` — do tego czasu: `[A:Yes]` jako
> skinienie)* Give my love to Auntie Seffa.
> MAUD: *(po jego odejściu)* …Everybody knows the witch but me.

**Gameplay:** quest: orki trzymają jeńców w stilt cage camp → wciśnij K → `war_party.rs`. Istniejące
`FOREST_DEMO=rescue` filmuje klatki (`camps::spawn_cage`, `[A:Sitting_Idle_Loop]` jeńcy).

Po odbiciu, jeniec (istniejące VO trailerowe): „Three weeks I was in there…”. Wat: „You're home. Back to
the fields.”

---

### Ch.5 — Price List (handel z Paszą pęka, owce kradzione)

**Cel:** gospodarka: pastwisko (`pasture.rs`), karawany ustają. Rywal (`rival.rs`) zaczyna rosnąć.

**Bez cutscenki** — tylko tablica edyktów Maud (nowy wpis) + pasterz na pastwisku.

> SHEPHERD BOY: Four sheep gone. Not eaten. *Taken.* Orks don't take. Orks eat.
> WAT: Then it wasn't orks.
> SHEPHERD BOY: *(wzrusza ramionami `[B:Shrug]`; do tego czasu `[A:Idle_No_Loop]`)* Had a desert
> accent, the dog says.

Edykt Maud (tekst na tablicy): *„Caravans suspended. The Pasha regrets. We regret more.”*

---

### Ch.6 — The Old Colony (ekspedycja; kartki Anselma)

**Cel:** eksploracja 5 biomów. Każdy biom = kartka dziennika Anselma (jest w `wyspa-opowiada`:
las→pustynia→skały→śnieg→bagno). Tobin w śniegu.

**Reżyseria kartek:** żadnej cutscenki. Podniesienie kartki `[A:PickUp_Table]` → caption z offu
(ANSELM, głos kronikarza) + pergamin na ekranie. Kolejność jest dowolna; ale kartka 3 (skały, „iron
answered iron”) i kartka 5 (bagno, urwana) są pisane tak, by razem dały twist bez wypowiedzenia go.

Teksty kartek (na pergaminie, VO czyta):
1. **Las — landing.** *„Day 4. Good timber. No natives, the Captain says. The Captain has not walked
   far.”*
2. **Pustynia — pyramid.** *„We trade salt for iron with the people of the south. They will not come
   north of the stones. They do not say why. We did not ask. Salt is cheap.”*
3. **Skały — the bell.** *„The bell is hung. Brother Oswin rang it at dusk, for the Hours. Iron answered
   iron. Nine of us by morning. We rang again. We are learning nothing.”*
4. **Śnieg — hermitage.** *„I have gone north. I have stopped ringing. They have stopped coming. I
   write this down so that someone cleverer than me may understand what I will not.”*
5. **Bagno — drowned chapel (ostatnia, urwana).** *„…came only after we rang. I told the Governor. The
   Governor will not let us stop. He says the Crown must hear the Hours kept. He says—”* *(reszta
   rozmyta wodą)*

**Tobin (śnieg, `castaway.rs`), scena ≈20 s:** siedzi przy ogniu `[A:Sitting_Idle_Loop]`, nie wstaje.
> TOBIN: Nine came off the reef. Six walked inland.
> WAT: And you?
> TOBIN: I counted. Somebody had to.
> WAT: Come to the castle. There's a bell. You'll hate it.
> TOBIN: *(wstaje `[A:Sitting_Exit]`)* Already do.

---

### Ch.7 — Crane's Quay (Korona przybywa)

**Cel:** Crane buduje przystań + Crown depot. Wprowadza „The Crown provides”.

**Cutscenka (≈40 s):** zatoka, nowa łódź `[C: prop]`, Crane schodzi po trapie `[A:Walk_Formal_Loop]`,
dwóch strażników Korony za nim (`guard`, ciemne warianty). Maud i Wat czekają.

> CRANE: Governor. Ser Godric. The Crown provides.
> MAUD: The Crown is eighteen months late.
> CRANE: The Crown is *punctual*. The sea is late. *(wyciąga zwój `[C: prop pergamin w dłoni]`)* A
> quay, a depot, and — ah — a proper bell. Royal pattern. We'll hang it ourselves.
> WAT: We have a bell.
> CRANE: *(uprzejmie)* You have a *noise*, Ser Godric. Sign here.

Wat podpisuje `[A:Interact]`. Cięcie na Pipa na platformie, który słyszał — `[A:Idle_Loop]`, głowa w dół
(blend `Idle_No_Loop` na 30%). Nic nie mówi. To jest cały beat.

**Gameplay:** nowy budynek Korony przy zatoce (plot), dostawy drewna/żelaza za „quota” (edykt).

**Koniec Aktu II — tytuł:** *„ACT III — THE HOLD”*.

---

## AKT III — THE HOLD

### Ch.8 — Granary (fałszywa flaga)

**Cel:** spichlerz płonie w nocy **bez** orków w pobliżu. Gracz widzi ślad do depotu.

**Cutscenka (≈25 s):** noc, spichlerz `[C: ogień + walenie się dachu: istniejący fx + scripted mesh
collapse]`, wieśniacy `[A:Walk_Carry_Loop]` z wiadrami, Maud `[A:Idle_FoldArms_Loop]`.

> MAUD: No drums tonight. No bell. And still a fire.
> WAT: Orks don't skip the drums.
> MAUD: No. They don't. *(pauza)* Crane's men were "inspecting" the stores at dusk.
> WAT: Say it.
> MAUD: I'm the Governor. I don't *say*. I *write*. *(odchodzi)* Find me a reason not to.

**Gameplay:** quest śledczy — ślady (`[C: decals]`) od spichlerza do depotu; w depocie beczka smoły z
Pitch Seep (camp, który gracz zna). Zero dialogu z Crane'em — konfrontacja jest w Ch.9.

---

### Ch.9 — The Draft (edykt poboru + tarany)

**Cel:** Crane ogłasza pobór: milicja idzie na Hold **teraz**, z taranami Korony (`Ram Yard`).
Gracz wybiera: iść (Ch.11 wcześniej, bez przygotowania) czy odmówić (Crane cofa dostawy).

**Cutscenka (≈45 s, najdłuższa):** plac, Crane na skrzyni `[A:Idle_Talking_Loop]`, tłum `[A:Idle_Loop]` ×8,
Maud przy tablicy, Wat z boku. Crane przybija edykt `[A:Interact]`.

> CRANE: Nobody is *conscripting* anybody. We're *inviting*. With a quota.
> VILLAGER (z tłumu): He laid three stones. Then he supervised.
> CRANE: *(ignoruje)* Rams at dawn. The Hold falls in a week. The Crown will remember Kell.
> WAT: The Crown remembers everything. That's what worries me.
> CRANE: *(cicho, tylko do Wata)* The granary was unfortunate. The next one would be… *instructive.*
> Sign, Ser Godric. Or don't. The rams go either way.

Maud, po wszystkim, przy tablicy, odwrócona plecami:
> MAUD: Write it down. If we live, it's a record. If not, it's a will.

**Wybór (prosty):** HUD: *„March with the rams”* / *„Hold the walls”*. Oba prowadzą do Ch.10; różni
się tylko stan gospodarki (Crane cofa dostawy) i czy gracz ma tarany w Ch.11.

---

### Ch.10 — Subtitles (orki dostają napisy)

**Cel:** beat, na którym stoi cała kampania. Mechanicznie: od tej sceny **ork VO ma napisy**.

**Scena (≈35 s), Field of the Answered (`ork_graveyard.rs`), świt:** Wat idzie między kurhanami
`[A:Walk_Loop]`. Dwa orki-żałobnicy `[A:Fixing_Kneeling` → kneel jak jest; docelowo `B:Kneel`]`. Nie
atakują. Seffa stoi obok z łopatą `[A:Idle_Loop` + prop]`.

> SEFFA: Put it away. They're not here for you.
> WAT: They're orks.
> SEFFA: They're *mourning*. You'll have seen it before. You just didn't have the word.
> *(ork żałobnik, pierwszy raz Z NAPISEM:)*
> ORK: My brother answered last winter.
> WAT: …Answered what?
> SEFFA: *(patrzy na niego długo)* You rang it. Every dusk. What did you think it was *for*?

Cięcie na czerń. Dźwięk dzwonu — jeden raz, bardzo daleko. Tytuł: *„Iron answers iron.”*

Potem, przy wyjściu z pola, **The Unanswering** (ork sam, bez broni, `[A:Idle_FoldArms_Loop]`):
> THE UNANSWERING: I did not answer. So I am no one. *(pauza)* You rang well, knight. Loud.

**Gameplay:** od teraz gracz może **nie dzwonić** o zmierzchu (opcja przy dzwonie). Bez dzwonu: noc
cicha, ale Crane karze gospodarkę („The Hours must be kept”). Z dzwonem: jak dotąd. To jest cały
wybór moralny gry — zero ekranu wyboru, tylko sznur.

---

### Ch.11 — The Bloody War (Gnashfang Hold)

**Cel:** istniejący assault (`ork_fortress.rs`, `FOREST_BREACH`). Dwie sceny: Garrok oferuje okup;
Skarn odrzuca.

**Cutscenka A — przed bramą (≈30 s):** Garrok wychodzi sam, `[A:Walk_Loop]`, staje
`[A:Idle_FoldArms_Loop]`. Napisy włączone.

> GARROK: Ransom for silence. Gold for the bell. Fair.
> WAT: And if I say no?
> GARROK: Then Skarn says yes. To the other thing.
> WAT: *(pauza)* …I don't own the bell.
> GARROK: *(odwraca się)* No. It owns you. Same as us.

**Wybór:** zapłać (Hold się otwiera bez walki; Warlord i tak atakuje w nocy — Skarn łamie układ) /
odmów (breach jak dziś). Oba kończą się Warlordem — różni się liczba garnizonu.

**Cutscenka B — breach (≈15 s):** istniejący `stage_breach`. Skarn na murze `[A:Idle_Rail_Call]`:
> SKARN: Iron called. We answered. We always answer.
> HROLK: *(z dołu)* Warlord say march tonight. Warlord say march every night. *(istniejące VO)*

**Koniec Aktu III — tytuł:** *„ACT IV — THE LAST TOLL”*.

---

## AKT IV — THE LAST TOLL

### Ch.12 — Seffa & Maud

**Cel:** przed finałem: Crane wycofuje się do zatoki (depot opuszczony, edykt zerwany). Maud i Seffa w
jednej scenie — dwie kobiety, które wiedziały.

**Cutscenka (≈40 s):** chata Seffy, Maud siedzi `[A:Sitting_Talking_Loop]`, Seffa stoi `[A:Idle_Loop]`,
Wat w drzwiach.

> MAUD: The dispatches went to the capital every spring. "The Hours are kept. The natives answer."
> They *knew*, Wat.
> WAT: *(to pierwszy raz, gdy ktoś mówi „Wat”)*
> MAUD: Oh, I read the ship's manifest the week you walked in. Godric Harrow was five foot two.
> SEFFA: *(bez zainteresowania)* Everybody's somebody else out here. Drink your tea.
> WAT: Crane?
> MAUD: In the bay. Waiting to see who wins. He'll "provide" for whoever does.
> SEFFA: Then win. And then decide what the bell is for. *That's* the job. The Warlord's just the
> noise before it.

---

### Finał — The Warlord

Istniejący boss (`warlord.rs`). Dodajemy tylko: **gong Hold** odpowiada na dzwon gracza o zmierzchu
(jeśli gracz dzwoni), tytuł *„The Last Toll”*, i po śmierci Warlorda istniejące VO: „The Warlord's down.
…It's finally over.” — a **Pip** (lub Tobin, jeśli Pip zginął w sukcesji — `succession.rs` wie):
> PIP: Is it? Dusk's in an hour.

Cięcie na dzwon. Gracz **musi podejść do sznura**. Dwie akcje: *Ring* / *Cut the rope*.

---

### Epilog RING (gracz dzwoni)

Noc mija jak zwykle; orki przychodzą, słabsze. Świt. Rynek: posąg Ser Godrica `[C: prop]`, Crane obok
`[A:Idle_Talking_Loop]`, tłum `[A:Idle_Loop]`, Pip dzwoni `[A:Idle_Rail_Call]`.

> CRANE: The Crown is proud. Sign here.
> WAT: *(podpisuje)*
> VILLAGER: He laid three stones. Then he supervised.
> *(dzwon; z lasu, bardzo daleko, bębny)*
> WAT (V.O.): Quiet day. I've learned not to trust quiet days.

Tytuł: *„KELL. A Crown colony.”* Fade. Napisy końcowe pod bębnami.

### Epilog BREAK (gracz tnie sznur)

Pusta rama dzwonu `[C: prop]`. Kuźnia: kowal `[A:Interact` na kowadle`]`, obok lemiesz z brązu
`[C: prop]`. Crane'a nie ma (łódź na horyzoncie). Garrok przy bramie, bez broni `[A:Idle_FoldArms_Loop]`,
z Seffą. Maud przy tablicy — nowy, ostatni edykt: *„The Hours are no longer kept. Kell regrets
nothing.”*

> PIP: *(przy pustej ramie, cicho)* It was a good bell.
> WAT: It was.
> PIP: What do I do at dusk now?
> WAT: *(odchodzi)* Sleep, Pip. Like a person.

Tytuł: *„KELL.”* (bez „A Crown colony”). Fade. Napisy końcowe w ciszy — tylko morze.

---

## 4. Budżet animacji per scena

| Scena | Pula A (gotowe) | Pula B (Mixamo) | Pula C (ręcznie) |
|---|---|---|---|
| Ch.0 Prolog | LayToIdle, Walk, Sprint, Idle_Rail_Call | — | wrak + mały dzwon (reuse swing_bell), tabliczka |
| Ch.1 A/B | Interact, FoldArms, Rail_Loop/Call, Torch | — | swing_bell (jest) |
| Ch.2 | Fixing_Kneeling, Walk_Carry | — | spalone pole (jest biome fx?) |
| Ch.3 | LayToIdle, Sitting_Idle, PickUp_Table, Rail_Call | — | — |
| Ch.4 | Talking, FoldArms, Yes | Bow | karawana (jest) |
| Ch.5 | Idle_No | Shrug | — |
| Ch.6 | PickUp_Table, Sitting_Idle/Exit | — | pergamin UI |
| Ch.7 | Walk_Formal, Interact, Idle_No blend | — | łódź prop, zwój w dłoni |
| Ch.8 | Walk_Carry, FoldArms | — | **walący się spichlerz** (mesh split + fizyka lub keyframe) |
| Ch.9 | Talking, Interact, Idle ×8 | Point, Cheer/Clap (tłum) | tablica edyktów |
| Ch.10 | Walk, Fixing_Kneeling, FoldArms | **Kneel, Pray** (żałobnicy) | łopata prop |
| Ch.11 | Walk, FoldArms, Rail_Call | — | breach (jest) |
| Ch.12 | Sitting_Talking, Idle | — | — |
| Finał | istniejące | — | gong Hold, akcja *Cut the rope* (lina spada: 1 keyframe) |
| RING | Talking, Rail_Call, Interact | Clap | posąg prop |
| BREAK | Interact (kowal) | — | pusta rama, lemiesz |

**Wniosek:** kampania jest w 85% grywalna na puli A. Z Mixamo potrzeba **6 klipów** (Bow, Shrug,
Point, Clap, Kneel, Pray) — jeden przebieg `bake_anims.py` + re-export 14 NPC-ów. Pula C to 6
propów + jeden efekt (spichlerz). Nic nie wymaga nowego modelu postaci.

Opcjonalnie: UAL Pro (~$10, CC0) może mieć część tych emotek w tym samym rigu — sprawdzić w
`quaternius.com/animviewer.html` przed sięganiem po Mixamo (unika retargetu i kwestii licencji).

---

## 5. Co się nie zmienia (żeby nikt tego nie „naprawił”)

- Noce 1–3 z `crates/core/src/campaign.rs` zostają mechanicznie identyczne; cutscenki są nakładką.
- Istniejące 13 klipów `campaign_*.ogg` zostają i są wplecione (cytowane wyżej); nic nie nagrywamy
  od nowa, dopisujemy.
- Jeden dzwon. Zero kościoła. Twist nigdy nie jest wypowiedziany wcześniej niż Ch.10 — a i tam
  mówi go Seffa pytaniem, nie Wat stwierdzeniem.
- Sukcesja działa w cutscenkach: jeśli Pip/Tobin nie żyją, linia idzie do najbliższego `boy`/`girl`
  looka; jeśli bohater zginął i jest nowy — Maud mówi „Ser Godric” do nowego ciała bez komentarza
  (to jest żart, którego nie tłumaczymy).

---

## 6. Minimalna maszyneria do zbudowania (`src/cutscene.rs`)

Nie projektuję tu implementacji; lista potrzeb, by scenariusz dało się odegrać:

1. `Cutscene { shots: Vec<Shot> }`, `Shot { cam: CamKey (pos/look/fov, ease), actors: [(Entity,
   clip, speed)], line: Option<(Speaker, &str, voice_key)>, hold: f32 }` — sekwencer, timer, skip
   (Esc/Space) z fade.
2. Stan `Modal::Cutscene` (świat zamrożony przez istniejący gate, render leci) + letterbox + ukryty HUD.
3. `subtitles::force` na czas linii; VO przez `audio/director.rs::Speak`.
4. Aktorzy: spawn tymczasowych NPC-ów z danym lookiem w pozycjach sceny (reuse `scenes.rs`
   tableau), despawn po scenie; stali (Maud, Pip) to zwykli villagers z tagiem `Named(Maud)`.
5. Propy jednorazowe (wrak, posąg, pusta rama) jako `BiomeEntity`-podobne, spawnowane per scena.
6. Zapis: `campaign.chapter` + flagi wyborów (`rang_after_ch10`, `paid_garrok`, `marched_with_rams`)
   → `SaveData` (`#[serde(default)]`), reset na New Game. Obowiązek z CLAUDE.md.
7. Harness: `FOREST_CUTSCENE=<id>` → odgrywa scenę pod `FOREST_CLIP` (do trailera i do weryfikacji).

---

## 7. Decyzje (zatwierdzone 2026-10-13)

1. Master spec `2026-10-10-kampania-fabula-design.md` nie istnieje — **ten dokument jest źródłem prawdy**
   dla beatów Ch.0–12 i epilogów.
2. Tożsamość Wata (przyjął imię utopionego giermka Godrica Harrowa) zostaje rozwiązana **jednym zdaniem
   Maud w Ch.12**; wcześniej nigdy nie wypowiadana.
3. RING / BREAK to **dwa trwałe stany świata** w free play po kampanii: po BREAK noce są ciche, Crane
   i depot znikają, quota Korony przestaje obowiązywać; po RING wszystko jak dotąd. Oba stany
   round-tripują save (`SaveData`) i resetują się na New Game.
