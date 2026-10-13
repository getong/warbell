# Kampania Warbell — fabuła wysokopoziomowa (design, draft v2)

> Dokument po polsku dla autora; wszystko, co pada **w grze**, zostaje po angielsku (imiona i
> tytuły poniżej są już angielskie). To jest **szkielet fabuły + plan wdrożenia**, nie dialogi.
>
> **Relacja do starszych speców:** `2026-07-01-kampania-misja-1-design.md` traktował trailer jako
> źródło prawdy dla tonu i obsady. **Ten dokument to uchyla** — kampania jest niezależna od
> trailera. Obecne misje (`crates/core/src/campaign.rs`, `docs/gameplay-cycles.md`) **też nie są
> wiążące** i zostaną wycięte. Z istniejącego kodu bierzemy tylko mechaniki.
>
> **v2 (2026-10-11):** przegląd dziur logicznych. Rejestr poprawek jest w §11.
>
> **v2.1 (2026-10-14, decyzje autora):** (1) **Prolog zaczyna się na statku** — gracz gra Wata jako
> giermka, widzi Harrowa, a katastrofę i śmierć Harrowa ogląda w czterech klatkach z pioruna. Zwrot A
> jest więc tajemnicą przed *światem* (Idris demaskuje w Rozdz. 8, wieś dowiaduje się w Rozdz. 11),
> nie przed graczem — ironia dramatyczna zamiast zagadki. Ziarna A z §5 zostają jako ziarna *dla
> świata*. (2) **Dzwon ma umknąć** — do Rozdz. 10 żadna scena nie jest o dzwonie, a każde ziarno B ma
> głośniejsze fałszywe wyjaśnienie (rytuał szamanów / Korona / Pasha). Rozpisane w
> `2026-10-13-kampania-scenariusz-design.md` §1.5 i §3b.

---

## 1. Czego się nauczyliśmy z dobrych kampanii (i co z tego bierzemy)

| Źródło | Lekcja | Jak to stosujemy |
|---|---|---|
| **RDR2** | Bohater ze skazą + powolny, zasłużony łuk odkupienia; humor żyje w obozie, a tragedia w fabule; **bohater umiera, gra trwa dalej** z kimś innym. | Wat ma tajemnicę i winę; wieczory przy ogniu; śmierć Wata w Rozdz. 11 i przejęcie gry przez Maud. |
| **Spec Ops: The Line / BioShock** | Najmocniejszy zwrot akcji to taki, w którym **współwinny jest gracz**, bo robił to własnymi rękami. | Zwrot B: noc przychodzi, bo **ty dzwonisz**. |
| **Frostpunk** | „Gotowana żaba”: małe, rozsądne decyzje prowadzą do potworności; na końcu pada pytanie „czy było warto?”. | Edykty Korony: każdy z osobna jest rozsądny, razem tworzą reżim. |
| **Warcraft III** | Kampania RTS jest dobra, gdy każda misja ma **inny cel**, a nie tylko „zbuduj i przetrwaj”. | Każdy rozdział ma inną noc albo inny typ misji. |
| **Ogólnie o zwrotach** | Zwrot ma zaskakiwać w chwili, gdy pada, i być oczywisty z perspektywy czasu. Postacie muszą być wiarygodne, niekoniecznie sympatyczne. | Każdy zwrot ma w §5 listę ziaren. **Nikt nie działa głupio**, a każda postać ma rozsądny powód (§11). |

**Ton:** ironia jest sposobem, w jaki *postacie* radzą sobie ze strachem. Gra nie żartuje sobie z
własnej fabuły. Na początku jest dużo suchego humoru, z każdym aktem żartów jest mniej, a w finale
prawie wcale. Nigdy nie wstawiamy puenty w moment tragedii.

---

## 2. Premisa

Korona wysyła czterdziestu osadników, żeby odbudowali opuszczony fort na dzikiej wyspie **Kell**.
Prowadzi ich słynny rycerz **Ser Godric Harrow**. Każdego zmierzchu, zgodnie z królewskim
statutem, biją w dzwon wojenny i co noc z bagien schodzą orki. Ani rycerz nie jest tym, za kogo
się podaje, ani dzwon nie służy temu, czemu miał służyć.

Temat przewodni: **imię i dzwon**. Oba są symbolami, które ktoś narzucił, a ludzie giną, żeby
je podtrzymać.

### Plan Korony (prawda, którą gracz poznaje po kawałku)
Wyspa ma dwie rodzime potęgi, które Korona chce usunąć: **orki** w zatrutym bagnie (Gnashfang,
gdzie żadna armia nie wejdzie) i **Pashę** na pustyni (pod jego piaskiem leży Zatopiona Piramida,
na którą Korona ma chrapkę). Plan ma trzy kroki:
1. **Dzwon wywabia orki z bagna na mury**, gdzie się wykrwawiają. Do tego potrzebna jest kolonia
   jako przynęta: chłopi są tańsi od żołnierzy, a przy okazji zasiedlają ziemię.
2. **Gdy orki są wykrwawione**, przypływa Crane z wojskiem, żeby dokończyć dzieła i napuścić
   kolonię na Pashę.
3. **Wyspa należy do Korony**, a osadnicy są do spisania na straty.

Sto lat temu Korona próbowała tego samego z pierwszą kolonią i przegrała: orki wygrały. Raporty
gubernatora dotarły do stolicy, a ludziom powiedziano, że kolonię zabiła „gorączka”.

**Prawo żelaznego głosu** jest starsze od ludzi. Klany orków same biły w żelazne gongi, gdy
wypowiadały sobie wojnę. Każde uderzenie to nowe wyzwanie, na które trzeba odpowiedzieć tej samej
nocy, a wódz, który nie odpowie, traci tron. Sam „żelazny głos” jest święty i nikt go nie dotyka,
dlatego dzwon pierwszej kolonii przetrwał sto lat nietknięty. Przez te sto lat na wyspie panował
spokój i nikt nie dzwonił.

---

## 3. Obsada (kto czego chce i czego się boi)

### Wat — bohater („Ser Godric Harrow”)
- **Prawda:** syn kowala i od 15 lat **giermek Harrowa** („Royal Footman”, czyli model, który
  mamy w grze). Harrow ginie na plaży w noc katastrofy. Wat z pomocą Maud zakłada jego zbroję, bo
  bez rycerza czterdziestu przerażonych ludzi rozbiegłoby się po lesie pełnym orków. Zna każdy
  pasek tej zbroi, bo zapinał ją codziennie.
- **Dlaczego nikt się nie zorientował:** Harrow podczas rejsu nie wychodził z kajuty, a osadnicy
  widzieli go raz, z daleka, na nabrzeżu. Maud puszcza plotkę, że Ser Godric dostał na plaży
  toporem w gardło i w twarz. To tłumaczy chrypę, zamknięty hełm i milczenie.
- **Wina:** był przy Harrowie w **Tessarine**. Miasto się poddało, Harrow przyjął kapitulację, a
  potem kazał je spalić. Wat stał dwa kroki za nim i nic nie zrobił.
- **Chce:** utrzymać ludzi przy życiu. **Boi się:** że gdy zdejmie hełm, wszystko się rozpadnie,
  i że jest tchórzem.
- **Głos/ton:** suchy, zmęczony, autoironiczny. Mówi o „Ser Godricu” w trzeciej osobie, bo to rola.
- **Łuk:** kłamstwo z dobrych powodów → zasłużenie na imię → wyznanie prawdy → śmierć jako on sam.

### Maud — sołtyska (reeve)
- Wdowa po czterdziestce, przeżyła dwa głody i zarazę. **Pomogła Watowi zapiąć zbroję na plaży**,
  więc jest wspólniczką od pierwszej minuty. To ona wymyśla plotkę o ranie gardła i twarzy.
- Publicznie z niego kpi (*„He laid three stones. Then he supervised.”*), bo z kogoś, z kogo się
  śmieją, nikt się nie przygląda uważnie. Czyta mu na głos wszystkie listy, bo Wat nie umie czytać
  („Ser Godric's eyes, since the blow”).
- **Chce:** żeby wieś przetrwała. W Akcie IV przejmuje grę.

### Pip — dzwonnik (12 lat)
- Sierota. Dzwon to pierwsza rzecz w życiu, która jest *jego*. Dzwoni z dumą o każdym zmierzchu.
- Po wyznaniu Wata (Rozdz. 11) **wyjmuje z dzwonu serce (klapę) i chowa je**. To jego
  dorastanie, a w finale trzyma klucz do wyboru. Pip **nie ginie**.

### Hamid — karawaniarz Pashy (nowa postać łącząca wątki)
- Uwolniony z orkowej klatki w Rozdz. 4. Ranny zostaje w wiosce. Jako kupiec, który latami
  handlował z orkami, **zna ich mowę**.
- **Funkcje fabularne:** umawia rozmowę z Pashą (Rozdz. 5); jako jedyny twierdzi, że najazd w
  Rozdz. 8 *nie był dziełem ludzi Idrisa* (wieś bierze to za stronniczość); tłumaczy Garroka
  (Rozdz. 10), co uzasadnia napisy pod mową orków (§7); w Akcie IV jest posłańcem do Idrisa.
- Ciche ziarno zwrotu B: nuci orkowe pieśni i krzywi się, gdy Pip dzwoni.

### Lord Commissioner Edwin Crane — człowiek Korony
- Przypływa w Rozdz. 7 z trzema statkami, zbożem, lekarstwami i trzydziestoma żołnierzami.
  Uprzejmy, nigdy nie podnosi głosu i rzeczywiście dostarcza to, co obiecuje.
- **Wie wszystko** (plan z §2). Zapytany o pierwszą kolonię mówi „gorączka”. Gracz, który czytał
  Anselma, wie, że to kłamstwo: pierwsze ziarno jego nieuczciwości.
- **Chce:** wykonać rozkaz i dostać za to lordostwo. To nie jest sadysta, tylko urzędnik.
- Po zwrocie A trzyma Wata w szachu i **nie ujawnia** prawdy, bo potrzebuje „Ser Godrica”, za
  którym ludzie pójdą na mury.

### Garrok Gnashfang — Warlord
- Stary, jednooki, zmęczony **więzień prawa**. Każde uderzenie dzwonu zmusza go do wojny, a
  jeśli nie odpowie, syn go obali i poprowadzi orki bez litości.
- Wspólną mowę zna z handlu z Pashą (przez Hamida).
- **Jeńcy:** orki biorą ludzi żywcem jako *okup za ciszę*, bo prawo przewiduje wymianę, gdy
  wzywający ustąpi. Nikt nigdy nie przyszedł negocjować, tylko z mieczem. *„We kept your people
  alive. For trade. You never came to trade.”*
- **Chce:** żeby dzwon zamilkł. **Boi się:** własnego syna.

### Skarn — syn Garroka, czempion berserkerów
- Urodził się w czasie wojny pierwszej kolonii i wojna dała mu wszystko. W pokoju byłby nikim.
  Lustro Crane'a po drugiej stronie.

### Pasha Idris — władca pustyni (istniejący rywal AI)
- Wygnany książę-kupiec. Osiadł na Kell 30 lat przed Koroną, handluje z orkami i nigdy nie miał z
  nimi wojny. **Nie zna prawa żelaznego głosu** (*„They told me once. I thought it was a story.”*).
- **Twarzą w twarz z Harrowem spotkał się raz**, przy kapitulacji Tessarine, dzień przed spaleniem
  miasta, w którym zginął jego syn. Dlatego potrafi poznać, że to nie ten człowiek.
- **Jego wersja wydarzeń (fałszywa, ale logiczna):** odkąd przypłynęła Korona, orki szaleją i
  atakują też jego karawany na swoich szlakach wojennych. Widzi, że rycerz Harrowa pali orkowe
  obozy. Wniosek: rzeźnik przypłynął podbić wyspę.
- **Najpierw rozmawia** (Rozdz. 5) i żąda końca „wojny z orkami”. Wat odpowiada, że to orki
  przychodzą do nich. Każdy uważa, że drugi kłamie. Wat nie może przeprosić za Tessarine, bo gra
  Harrowa, więc milczy, a Idris słyszy pogardę. **Konflikt rodzi maska.**
- **Eskalacja stopniowa:** ostrzeżenie → zerwanie handlu → wypady na spichlerz, bydło i
  wartowników. Jego ludzie **nikogo nie zabijają, jeśli nie muszą, i oszczędzają dzieci**. Ofiary
  ma dopiero najazd w Rozdz. 8, a ten zorganizował Crane (§4).
- To on **demaskuje Wata** (zwrot A). Jego AI zmienia postawę zależnie od fabuły (§6.4).

### Brother Anselm — głos z przeszłości
- Kronikarz pierwszej kolonii. Strony jego dziennika leżą w ruinach po wyspie.

---

## 4. Struktura: prolog + 4 akty, 12 rozdziałów

Rozdział to kamień milowy, nie każda noc. Pomiędzy nimi grają zwykłe noce. Około 25 nocy i 6–7 h (tempo w §12). Po
kampanii odblokowuje się **tryb sandbox** (obecne nieskończone noce).

### PROLOG — „Landfall” (Wreck Cove, zachodnie wybrzeże, §6.1)
Sztorm. Statek idzie na rafę, a marynarze **biją na alarm w dzwon okrętowy** (ziarno B). Gramy
**zakutą postacią w hełmie** na plaży: krótki tutorial walki z orkami z pobliskiego obozu, we mgle
i w deszczu. Ktoś pada w falach. Fala zabiera ciało w prostym kaftanie, a Maud odwraca wzrok
gracza. Czterdziestka ocalałych wierzy, że giermek „Wat” utonął.

Świt: rycerz ma pieczętowane rozkazy. Maud odczytuje na głos część jawną: *„Make for the old fort
of Saint Ottilie. Restore it. Ring the King's bell at every dusk.”* Druga koperta jest zalakowana
pieczęcią **„For the Lord Commissioner's eyes only”** i od tej chwili leży w ekwipunku przez całą
grę. Marsz w głąb wyspy (cięcie i krótki odcinek grywalny) prowadzi do ruin fortu w środku wyspy.

### AKT I — „The Toll”
1. **Stones.** Ruiny fortu z kamienną wieżą i **wiszącym w niej dzwonem pierwszej kolonii**,
   nietkniętym od stu lat. Budowa, ekonomia, zawody, Maud. Pip odkopuje sznur i zostaje
   dzwonnikiem. Pierwszy zmierzch, pierwszy dzwon, pierwsza noc.
2. **Torches.** Podpalacze idą na farmę.
3. **The Ritual.** Obóz szamanów do rozbicia za dnia. Pip dostaje gorączki. Maud: *„The boy's
   sick. It's one night.”* Dzwon milczy i ta noc jest **cicha** (oskryptowana, ziarno B). Rano
   wszyscy mówią o szczęściu.
4. **The Muster.** Pospolite ruszenie i rajd na obóz z klatkami. Wśród uwolnionych jest **Hamid**.
   *Mechaniki Aktu I:* budowa, ekonomia, zawody, noc/dzwon, obrona, muster, jeńcy.

### AKT II — „The Wilds”
5. **Sand and Salt.** Hamid umawia spotkanie z Pashą pod białą flagą. Idris żąda końca „wojny z
   orkami” i rozmowa się nie klei (§3). Na koniec, patrząc na herb: *„I knew the man who wore that
   crest.”* Zrywa handel i zaczyna się eskalacja (bez ofiar).
6. **The Old Colony.** Ekspedycja po biomach: landmarki, rune trials, strony dziennika Anselma,
   opcjonalni Starzy (strażnicy). W zatopionej kaplicy na bagnach leży ostatnia strona Anselma i
   **szkic dzwonu z inskrypcją, tą samą, którą widać na dzwonie w forcie.** Kronikarz pisze, że
   orki *„came only after we rang, and the Governor will not let us stop”*. Środek zdania jest
   rozmyty przez wodę, a czytelne zostają tylko te dwa kawałki.
7. **The Commissioner.** Statki Crane'a przybijają do **Wreck Cove**, obok wraku. Wchodzą Edykty
   Korony, a pierwszy z nich to *nie wolno uciszać dzwonu*. Crane pyta o depesze. Wat **zataja zalakowaną
   kopertę** i mówi, że przepadła we wraku, bo boi się, że w środku jest rysopis Harrowa. Crane
   wzrusza ramionami: *„A pity.”* (ziarno: on już wie, co w niej jest). **Ziarno B, które
   wiedzie do Crane'a:** pierwszej nocy żołnierz dla żartu uderza w wyłowiony z piasku dzwon
   okrętowy, a obóz Korony w zatoce zostaje zaatakowany. Rano Crane spokojnie wydaje rozkaz: *„See
   that no one touches that bell again.”*
8. **Northern Dog.** Wielki nocny najazd na wieś: spłonął spichlerz, zginęło sześć osób, a na
   miejscu leży pustynna szabla. To **fałszywa flaga**: zrobili to żołnierze Crane'a w przebraniu.
   Hamid upiera się, że *„our men don't kill like this”*, ale nikt mu nie wierzy. Wieś żąda
   odwetu, Crane daje żołnierzy. Szturm na twierdzę Pashy. Idris klęczy w swojej sali i mówi:
   *„My men did not burn your granary. And you are not Harrow. Harrow was taller. Harrow would
   have killed me already. Who are you?”* **ZWROT A.** Wat zdejmuje hełm. W sali są tylko Maud,
   Crane i kilku jego żołnierzy, a wieś nie wie. *Wybór:* oszczędzić albo stracić Idrisa.
   Pod wpływem tego, co usłyszał, gracz może później uwierzyć, że Idris mówił prawdę o spichlerzu.

### AKT III — „The Hold”
9. **Under the Helm.** Na zewnątrz hełm wraca na głowę. Prywatnie, przy ognisku z Maud, Wat
   siedzi bez niego. Crane w cztery oczy: *„A deserter in a dead knight's armour. The Crown hangs
   men for less. But the Crown needs Ser Godric. Gnashfang falls this month.”* Taran i balisty,
   edykty zaostrzają się (pobór, dzwon również o świcie, jeńcy na statki).
10. **Gnashfang.** Wyłom w twierdzy. Garnizon przy bramie jest nieliczny, bo orki wykrwawiły się
    na naszych murach, co znaczy, że plan Korony działa. Za bramą nie ma armii, tylko głodne
    miasto, starcy i młode orki w norach. Garrok na tronie nie walczy. Hamid tłumaczy. **ZWROT B**
    (§5). Garrok podaje liczbę uderzeń dzwonu, bo orki je liczą (*„they're counting”*). Proponuje
    rozejm: *uciszcie dzwon, a oddamy waszych ludzi i przestaniemy przychodzić*. Spotkanie ma się
    odbyć pod kamiennym kręgiem, na świętej ziemi.
11. **The Stones.** Rozmowy o świcie. Kusznicy Crane'a zabijają Garroka podczas rozejmu, bo pokój
    zatrzymałby wykrwawianie orków, zanim Hold padnie. Skarn ogłasza krwawą wojnę, która według
    prawa **nie potrzebuje dzwonu**. Wat wraca i dopiero teraz **łamie pieczęć koperty z prologu**,
    tej, którą zataił przed Crane'em. Maud czyta ją na głos. W środku jest plan Korony i
    podpis Harrowa: rycerz wiedział, że prowadzi ludzi na rzeź, i miał za to dostać wyspę.
    Wat zwołuje wieś: *„My name is Wat. I carried his shield. Ser Godric died on the beach — and
    he knew what this bell was for.”* Odmawia dzwonienia. Pip wyjmuje serce dzwonu i znika.
    Crane: *„The Crown does not reinforce deserters.”* Wycofuje żołnierzy do zatoki. W nocy
    przychodzi Skarn. **ZWROT C:** Wat trzyma bramę, żeby ludzie zdążyli schronić się w forcie, i
    ginie. O świcie orki się wycofują. Kamera przechodzi na Maud.

### AKT IV — „The Last Toll”
12. **Maud.** Grasz jako Maud. Wieś jest okaleczona, a żarty się skończyły. Zbierasz sojuszników:
    - **Idris**, jeśli żyje: Hamid zanosi mu list z koperty. Plan Korony mówi wprost: *„turn the
      colonists upon the Pasha by any means”*, a Idris rozumie, kto spalił spichlerz.
    - **Lud Garroka**, który nie chce iść za Skarnem. Widzieli, że człowiek odmówił wezwania i
      zginął za to. Prowadzi ich szamanka, wdowa po Garroku.
    - **Uwolnieni jeńcy.**

    Crane wraca z ultimatum: *„Ring the bell tonight, or the colony is in rebellion.”*
    **Wybór na wieży. Pip trzyma serce dzwonu:**
    - **RING:** Pip wkłada serce z powrotem i dzwoni. Prawo zmusza **każdy** klan do odpowiedzi,
      także lud Garroka. Wszystkie orki z wyspy przychodzą pod mury, gdzie czeka cała armia
      Korony. Do świtu orków już nie ma. Osada jest bezpieczna. Crane zostaje gubernatorem, na
      rynku staje pomnik „Ser Godrica Harrowa”, a Pip dzwoni o każdym zmierzchu do końca życia,
      choć nikt już nie przychodzi.
    - **BREAK:** Maud i Pip rozbijają dzwon młotami. Bez żelaznego głosu prawo nie wiąże już
      nikogo, więc lud Garroka może stanąć po naszej stronie. Finał ma dwie fazy: **w nocy Skarn**
      (krwawa wojna), **o świcie wojsko Crane'a** (karna ekspedycja przeciw „buntownikom”). Jeśli
      przetrwasz, z brązu dzwonu odlewa się lemiesz i tablica na pusty grób „giermka, który utonął”.
      Stary napis zostaje zatarty, a nowy brzmi: **„WAT. FOOTMAN.”** Maud: *„He laid three
      stones. We laid the rest.”*
    - Żadna opcja nie jest „dobra”. RING daje bezpieczeństwo pod butem i ludobójstwo, BREAK
      niepewną wolność. Karta końcowa pokazuje: *ile razy zadzwonił dzwon — i ile razy sam to
      rozkazałeś.*

---

## 5. Zwroty akcji i ich ziarna

**A — „Kim jesteś?” (Rozdz. 8).** Rycerz to giermek w cudzej zbroi.
Ziarna: twarzy nigdy nie widać; plotka o ranie gardła i twarzy; Maud czyta mu listy („his eyes”);
myli herby innych rodów; mówi o sobie w trzeciej osobie; animacja poprawiania naramiennika (zbroja
jest za luźna w ramionach); pusty grób „utopionego giermka Wata”; Idris w Rozdz. 5; linijka
*„Half of them don't know my name. Good.”*

**B — „Dzwon nas woła” (Rozdz. 10).**
Ziarna (wszystkie ciche): dzwon okrętowy w prologu; cicha noc gorączki Pipa; inskrypcja z dziennika
Anselma zgadza się z naszym dzwonem; zdanie Anselma *„came only after we rang”*; Hamid krzywi się
na dźwięk dzwonu; okrzyki orków *„iron voice calls!”*; incydent z dzwonem okrętowym w obozie Crane'a
i jego spokojny rozkaz; Crane mówi „gorączka”, choć Anselm pisze o orkach; orki nigdy nie atakują
wieży z dzwonem (tabu).
**Zmyła:** Pasha nie ma oblężeń, bo „handluje, a nie zabija”.

**Dlaczego osadnicy dzwonią dalej (nikt tu nie jest głupi):**
1. Pierwszy atak, na plaży, wydarzył się, zanim ktoś znalazł dzwon w forcie. Dzwonu okrętowego
   bijącego w chaosie sztormu nikt nie łączy z orkami.
2. Statut każe dzwonić, *żeby zwołać obrońców*. Dzwon „działa”, bo obrońcy zawsze są na murach,
   zanim przyjdą orki. Osadnicy mylą przyczynę ze skutkiem.
3. Kontrprzykład jest jeden (gorączka Pipa), a wokół jest dużo przemocy niezwiązanej z dzwonem.
4. To rozkaz króla, a podszywający się pod rycerza nie może zwracać na siebie uwagi Korony. Od
   Rozdz. 7 obowiązuje edykt.
5. Do Rozdz. 10 nie da się uciszyć dzwonu w mechanice (§6.2), więc gracz nie przetestuje zwrotu.

**C — Śmierć Wata (Rozdz. 11).** Ginie jako on sam, z imieniem, po wyznaniu, broniąc ludzi, których
okłamywał.

**Domknięcie: zalakowana koperta.** Leży w ekwipunku od prologu do Rozdz. 11. Spina A (Harrow był
potworem, za którego Wat się podawał), B (Korona wiedziała) i zdradę Crane'a.

---

## 6. Plan wdrożenia: mapa, mechaniki, kolejność

### 6.1 Mapa

**Stan faktyczny** (`worldmap.rs`, `MAP_SCALE` 2.6): wyspa to elipsa około ±185 (X) × ±138 (Z)
jednostek. **Fort leży w środku (origin), 140–185 jednostek od każdego brzegu.** Twierdza Pashy
stoi przy NE wybrzeżu w `rival::RIVAL_CENTRE` ≈ (78, −104). Hold jest na południu, w rozszerzeniu
Blight (`ork_fortress::CENTRE`). Biomy: śnieg NW, pustynia NE, skały E, las SW/W, bagno S.

**Wniosek:** lądowanie „przy zamku” jest geometrycznie niemożliwe, a na NE brzegu, przy pustyni,
siedzi Pasha. **Lądujemy na przeciwległym, zachodnim brzegu, w lesie.** Fort w środku wyspy to
fabularnie plus: „old fort of Saint Ottilie” w głębi lądu i marsz przez las w prologu.

| Miejsce | Gdzie (do potwierdzenia ujęciem) | Do zrobienia |
|---|---|---|
| **Wreck Cove** (plaża lądowania, potem przystań Korony) | **zachodnie wybrzeże, biom lasu, ok. (−165, 40)**. Od fortu ~170 u, **od Pashy ~280 u**, czyli na drugim końcu wyspy | **zmiana kształtu brzegu:** wcięta zatoka (odwrotność `nw_headland`), pas piasku, rafa ze skałami, wrak statku, rozbite łodzie. Od Rozdz. 7: molo, 3 statki, obóz Korony, dzwon okrętowy w piasku |
| **King's Road** | Wreck Cove → fort | szlak (system dróg już jest: `biome_road_target`, `pass_trails_world`); marsz z prologu, potem trasa Crane'a |
| **Fort Saint Ottilie** | origin | stan „ruina” na starcie i odbudowa w Akcie I; **kamienna wieża z dzwonem** przy `castle::BELL_POS` zamiast dzisiejszej drewnianej ramy; pusty grób „Wata” przy bramie |
| **Ruiny pierwszej kolonii** | po biomach + zatopiona kaplica na bagnach | strony Anselma podpięte pod istniejące vignettes/landmarki; kaplica jako nowy landmark |
| **Twierdza Pashy** | NE, bez zmian lokalizacji | sala tronowa lub dziedziniec na scenę demaskowania; szlak karawan Pasha ↔ obóz orków |
| **Wykopalisko Korony** | Sunken Pyramid | Akt III–IV: rusztowania i robotnicy po upadku Pashy |
| **Gnashfang Hold** | bez zmian lokalizacji | dobudować **miasto** za bramą: chaty, nory, kotły, ludność niebojowa, sala tronowa |
| **Kamienny krąg** | trilithon | rozbudować w krąg z zaroślami pod zasadzkę |

**Powiększanie wyspy nie jest potrzebne.** Potrzebna jest tylko **zmiana linii brzegowej**
zachodniego wybrzeża (zatoka), bo dziś brzeg to gładka elipsa. Jeśli kiedyś powiększymy mapę, to
pod nowe treści, nie pod tę fabułę.

### 6.2 Dzwon jako serce gry

Dziś noc startuje sama po `PREP_DURATION` (195 s), a **E przy dzwonie** (oraz N) przyspiesza ją
(`siege.rs::siege_controls`). Zostawiamy to, zmieniając interpretację:
- **Koniec timera = Pip dzwoni o zmierzchu** (NPC idzie do wieży i ciągnie za sznur;
  `castle::swing_bell` już jest).
- **E przy dzwonie = gracz rozkazuje zadzwonić wcześniej.**
- **Licznik:** `rings_total` i `rings_ordered`, zapisywane w sejwie. Garrok podaje `rings_total`
  (orki liczą uderzenia, a nie to, kto ciągnął). Karta końcowa pokazuje oba.
- **Do Rozdz. 10 nie da się uciszyć dzwonu.** Po Rozdz. 10 pojawia się akcja *Silence the bell*
  z kosztem w postaci gniewu Korony. Od Rozdz. 11 przychodzi Skarn mimo ciszy.
- **Noc bez fali** w `siege.rs` (gorączka Pipa, cisza po Rozdz. 10).
- **Każdy żelazny głos wywołuje odpowiedź lokalną:** dzwon okrętowy w prologu i w obozie Crane'a
  ściąga orki z najbliższego obozu (`camps.rs`), a nie z Hold.
- **Tabu:** orki nie atakują wieży z dzwonem (wykluczyć ją z celów AI oblężenia).

### 6.3 Nowe systemy (fundament)

1. **Silnik kampanii** (zamiast `campaign.rs`): rozdziały → beaty → triggery (strefa, flaga,
   świt/zmierzch, śmierć NPC, boss) → akcje (scena, rozmowa, spawn, flaga, cel, `NightScript`).
   Rozdziały opisane danymi (RON). Flagi w core i w sejwie (persist + reset z CLAUDE.md).
2. **Sceny T2 i rozmowy T1** (§8) na bazie `cinematic.rs`, `demo.rs` i `audio/director.rs`.
3. **Postacie nazwane** (Maud, Pip, Hamid, Crane, Idris, Garrok, Skarn, szamanka): unikalne,
   chronione fabularnie, skryptowalne.
4. **Napisy z imieniem mówiącego** w `subtitles.rs`.
5. **Dziennik / kodeks** (J log): strony Anselma, karty postaci; **przedmiot fabularny**
   (zalakowana koperta) w satchelu, którego nie da się sprzedać ani wyrzucić.
6. **Tłumaczenie ork-mowy** od Rozdz. 10 (§7).

### 6.4 Zmiany w istniejących mechanikach

- **Śmierć gracza przed Rozdz. 11 to NIE sukcesja.** Jeśli dziedzic przejmie grę w Rozdz. 5, fabuła
  o Wacie się sypie. Zamiast tego *„Ser Godric is down”*: wieśniacy znoszą bohatera do fortu, a on
  budzi się o świcie. Kosztuje to zasoby z tego dnia i życie jednego wieśniaka, który go
  wyniósł. Przegrana nastąpi tylko, gdy padnie fort. Sukcesja jest **oskryptowana raz**
  (Wat → Maud). W Akcie IV śmierć Maud oznacza powrót do autosave'u ze świtu. **W sandboxie
  sukcesja zostaje bez zmian.**
- **Bohater:** model w hełmie (publicznie aż do Rozdz. 11) i bez hełmu (prywatne sceny od Rozdz. 8,
  publicznie od Rozdz. 11). Imię w UI: „Ser Godric” → „Wat” od Rozdz. 11. Barki przepisane.
- **Maud grywalna (Akt IV):** własny model, ten sam kontroler. **Największy koszt assetowy.**
- **Pasha AI (`rival.rs`):** stany `Wary → Warned → Harassing → Defeated → Spared/Executed →
  Allied`. W `Harassing` cele są niekrwawe (spichlerz, bydło, wartownicy), a dzieci oszczędzone.
  Dzisiejsze „zburz twierdzę za nagrodę” w Rozdz. 8 zmienia się w „zdobądź twierdzę i zdecyduj o
  losie Idrisa”. W BREAK jego żołnierze walczą po naszej stronie.
- **Orki:** w Akcie III frakcja się dzieli na lud Garroka i ludzi Skarna. Nowe modele niebojowe
  (starcy, młode, uciekają). Z Garrokiem się nie walczy. Skarn to boss finału (reużyć `warlord.rs`).
  Jeńcy w klatkach zyskują sens fabularny: to okup za ciszę.
- **Korona (nowa frakcja):** Crane, żołnierze i kusznicy (istniejące modele w barwach Korony).
  Najazd z fałszywą flagą to oskryptowana noc z „pustynnymi” żołnierzami.
- **Edykty Korony:** od Rozdz. 7 karta po świcie (przyjmij / odrzuć) z efektami na ekonomię,
  populację i noce. Liczą się w epilogu.
- **Warunek zwycięstwa:** w kampanii zabicie Warlorda nie kończy gry. W sandboxie zostaje.
- **Wardens → Starzy:** opcjonalni. Ich zabicie podnosi agresję orków.
- **Barki per akt:** od żartów przez zmęczenie do ciszy.
- **Tryb Sandbox** jako osobna pozycja w menu.

### 6.5 Co wycinamy

- `crates/core/src/campaign.rs` i jego użycie w `quest.rs`, `campaign_verify.rs`, VO kampanii
  „Sully” (`docs/campaign-voice.json`).
- Spec Misji 1 (`2026-07-01-…`) oznaczamy jako zastąpiony.
- Linie VO sprzeczne z fabułą (np. *„The Warlord's down… It's finally over.”*). Potrzebny przegląd
  `audio/lines.rs`.

### 6.6 Kolejność prac

| M | Zakres | Grywalne na końcu |
|---|---|---|
| **M0 Fundament** | silnik kampanii, flagi, sejw; dzwon z licznikiem, noc bez fali, „lokalne” dzwony, tabu wieży; „Ser Godric is down” zamiast sukcesji; `SceneScript`, rozmowy, napisy z imionami; **prototyp sceny prologu** | prolog na klipie |
| **M1 Akt I** | Wreck Cove (zmiana brzegu), King's Road, fort w ruinach z kamienną wieżą, Maud/Pip/Hamid, cicha noc, ogniska | Prolog + Rozdz. 1–4 |
| **M2 Akt II** | relacje Pashy, kaplica i Anselm, przystań i Crane, edykty, incydent z dzwonem okrętowym, fałszywa flaga, demaskowanie z wyborem | do Rozdz. 8 |
| **M3 Akt III** | miasto w Hold, Garrok, tłumaczenie, krąg i zasadzka, koperta, śmierć Wata | do Rozdz. 11 |
| **M4 Akt IV** | Maud grywalna, sojusznicy, dwufazowy finał BREAK, finał RING, epilogi, sandbox | cała kampania |

**Ryzyka:** grywalna Maud, niebojowe orki, jakość scen bez mimiki. Prototyp sceny powstaje w M0.

---

## 7. „Tłumaczenie” ork-mowy

Przez dwa akty barki orków to warkot i łamana wspólna mowa. Od Rozdz. 10 Hamid tłumaczy Garroka,
a gra od tej chwili **podpisuje te same dźwięki**: *„Not tonight. The iron voice again.”*, *„My
brother answered last winter. He did not come back.”*, *„Tell the little ones we hunt.”* Koszt to
głównie teksty i flaga. Gracz zabił setki orków i nagle słyszy, co mówili.

---

## 8. Cutscenki: co realnie zbuduje agent Opus

Mamy `cinematic.rs`, `demo.rs`, `subtitles.rs`, `audio/director.rs`, DoF i grade. **Nie mamy
lip-synca ani mimiki** i zakładamy, że nie będziemy mieć.

| Poziom | Co to jest | Użycie |
|---|---|---|
| **T0 Dispatch** | karta, napis i VO, gracz ma kontrolę (istnieje) | cele, zapowiedzi |
| **T1 Walk-and-talk / ognisko** | VO 2–3 postaci w trakcie gry, bez zmiany kamery | **80% fabuły** |
| **T2 Scena** | letterbox, 3–6 ujęć, aktorzy z istniejącymi animacjami, VO, pominięcie spacją; data-driven `SceneScript` (RON), weryfikacja przez `FOREST_CLIP` | ~9 scen: Prolog, Statut, Pasha, Demaskowanie, Hold, Krąg, Koperta/wyznanie, Śmierć Wata, Finał |

**Reżyseria pod ograniczenia:** hełmy, kaptury, dystans, sylwetki pod ogniem, ujęcia przez ramię,
dłonie zamiast twarzy, cięcie na reakcję otoczenia. Brak twarzy Wata jest **ziarnem zwrotu A**:
pierwsze ujęcie jego twarzy w Rozdz. 8 ma ciężar właśnie dlatego, że wcześniej go nie było.

---

## 9. Obsada głosowa (ElevenLabs)

| Postać | Kierunek głosu |
|---|---|
| Wat | męski, 40, chropowaty (fabularnie „rana gardła”), zmęczony, suchy dowcip |
| Maud | kobiecy, 40–50, ludowy, deadpan; w finale bez ironii |
| Pip | chłopięcy, entuzjastyczny |
| Hamid | męski, 30–40, ciepły, szybki, z akcentem południa |
| Crane | męski, wykształcony, miękki, nigdy nie podnosi głosu |
| Garrok | bardzo niski, powolny, z chrypą; ork-mowa (konlang) + łamana wspólna |
| Skarn | młodszy, warczący, szybki |
| Szamanka (wdowa) | kobiecy, stary, ork-mowa |
| Idris | 60, ciepły baryton, gorycz zamiast krzyku |
| Anselm | szept lektora dziennika |
| Wieśniacy / orki / żołnierze | pule barków **per akt** |

Każda linia ma transkrypt w komentarzu przy kluczu klipu (`audio/lines.rs`).

---

## 10. Otwarte decyzje

1. **Liczba wyborów:** proponuję 2 wybory finałowe (los Idrisa, RING/BREAK), a edykty i Starzy
   kolorują epilog.
2. **Śmierć Wata na stałe** (rekomenduję) czy przeżycie w RING.
3. **Nazwy** (Kell, Saint Ottilie, Wreck Cove, Wat, Maud, Pip, Hamid, Crane, Garrok, Skarn, Idris,
   Tessarine) są robocze.

---

## 11. Rejestr dziur logicznych (v1 → v2)

| # | Dziura w v1 | Poprawka w v2 |
|---|---|---|
| 1 | Plaża „przy zamku”, a fort jest w środku wyspy, 140–185 u od brzegu; NE brzeg zajmuje Pasha | Lądowanie w **Wreck Cove** na zachodnim brzegu (~280 u od Pashy) + marsz King's Road do fortu (§6.1) |
| 2 | Skąd na dzikiej wyspie zamek i dzwon? | To fort i dzwon **pierwszej kolonii**. Korona wysłała osadników właśnie tam, a statut mówi „ring the King's bell” |
| 3 | Dwa dzwony (zamkowy i pęknięty na bagnach) mieszały się | Jeden dzwon: ten w forcie. Ziarnem jest **inskrypcja** w dzienniku Anselma |
| 4 | Dlaczego orki przez sto lat nie zniszczyły dzwonu? | Żelazny głos jest **tabu**. Orki go nie dotykają i nie atakują wieży |
| 5 | Zbroja płytowa w 5 minut, w ciemności, w pojedynkę? | Wat zapinał ją codziennie, a pomaga mu Maud, która od pierwszej minuty jest wspólniczką |
| 6 | Dlaczego 40 osób nie poznaje, że to nie Harrow (wzrost, głos)? | Harrow siedział w kajucie, ludzie widzieli go raz z daleka; plotka o ranie gardła i twarzy tłumaczy chrypę i hełm |
| 7 | Ciało Harrowa na plaży | Zabiera je fala. Osadnicy myślą, że utonął giermek, i stawiają mu pusty grób, który wraca w epilogu |
| 8 | Skąd Idris wie, że Harrow był wyższy? | Spotkał go twarzą w twarz przy kapitulacji Tessarine |
| 9 | Dlaczego Wat, nastawiony pokojowo, szturmuje Pashę? | **Fałszywa flaga Crane'a** (spichlerz, sześciu zabitych). Wieś żąda odwetu. Hamid ostrzega, ale nikt mu nie wierzy |
| 10 | Po co Koronie przynęta, skoro orki nie atakują bez dzwonu? | Korona chce **wytępić** orki i usunąć Pashę. Dzwon wywabia orki z niedostępnego bagna na mury (§2) |
| 11 | Skąd Korona wie o dzwonie? | Z raportów gubernatora pierwszej kolonii; ludziom powiedziano „gorączka” |
| 12 | Dlaczego Crane przypływa dopiero w Rozdz. 7? | Taki jest plan: najpierw chłopi wykrwawiają orki, potem wojsko dokańcza |
| 13 | Skąd Wat zna plan Korony? | Zalakowana koperta od prologu w ekwipunku. Wat łamie pieczęć w Rozdz. 11 i dowiaduje się, że Harrow wiedział |
| 14 | Demaskowanie przy wieśniakach kłóciło się z szantażem Crane'a („to plotka”) | W sali są tylko Maud, Crane i kilku żołnierzy. Wieś dowiaduje się dopiero z wyznania w Rozdz. 11 |
| 15 | Model bez hełmu „od Rozdz. 8” zdradzał sekret publicznie | Bez hełmu tylko prywatnie od Rozdz. 8, publicznie od Rozdz. 11 |
| 16 | Szaman uczy Maud orkowego w jeden dzień | Tłumaczy **Hamid**, kupiec, który latami handlował z orkami |
| 17 | Garrok mówi wspólną mową — skąd? | Z handlu z Pashą |
| 18 | Po co orki trzymają jeńców, skoro „tylko odpowiadają na wezwanie”? | To okup za ciszę według ich prawa. Nikt nie przyszedł negocjować |
| 19 | Dlaczego orki atakowały karawany Pashy, jeśli Pasha nie dzwonił? | W wojnie każdy obcy na szlaku wojennym jest wrogiem. Idris przypisuje to Koronie |
| 20 | Skarn przychodzi bez dzwonu — sprzeczne z prawem? | Zabicie na świętej ziemi to **krwawa wojna**, która według prawa nie potrzebuje wezwania |
| 21 | Żołnierze Korony „patrzą z murów”, a fort pada? | Crane **wycofuje** żołnierzy do zatoki (*„The Crown does not reinforce deserters”*) |
| 22 | W finale Crane kontroluje dzwon, więc wybór Maud nic nie znaczy | Pip wyjmuje i chowa **serce dzwonu**. Bez niego nikt nie zadzwoni |
| 23 | RING vs BREAK: po co dzwonić, skoro Skarn i tak przyjdzie? | Dzwon zmusza **każdy** klan, także lud Garroka, do odpowiedzi. RING to ludobójstwo wszystkich orków, BREAK to walka tylko ze Skarnem i Koroną |
| 24 | Dlaczego lud Garroka pomaga ludziom po zabiciu wodza? | Wiedzą, że strzelała Korona. Widzieli człowieka, który odmówił wezwania i zginął. Po rozbiciu dzwonu prawo ich już nie wiąże |
| 25 | **Sukcesja przed Rozdz. 11 łamie fabułę** (dziedzic w Rozdz. 5 = brak Wata) | Przed Rozdz. 11 „Ser Godric is down” z kosztem. Sukcesja jest oskryptowana raz. W sandboxie zostaje |
| 26 | Garrok podawał liczbę rozkazów gracza, której nie mógł znać | Garrok podaje wszystkie uderzenia (orki je liczą). Rozkazy gracza pokazuje dopiero karta końcowa |
| 27 | Anselm: „wyrwana strona” była tanim chwytem | Strona jest zalana. Czytelne zostają dwa fragmenty: *„came only after we rang”* i *„the Governor will not let us stop”*, czyli lustro Crane'a |

---

## 12. Tempo: długość, co ile sceny, co je wywołuje

### 12.1 Zegar gry (stan faktyczny)
Dzień (`PREP_DURATION`) trwa **195 s**. Noc trwa do wybicia fali, typowo **2–4 min**, a schodzenie
nieba od zmierzchu do świtu zajmuje ~100 s. **Jeden cykl dzień+noc to ok. 6–7 min.** W rozdziałach
wyprawowych (5, 6, 10) dzień się wydłuża przez istniejący `prep_mul` (×2–3), żeby zdążyć dojść i
wrócić. Jeśli dzwon zabije, gdy bohater jest daleko, wieś broni się sama milicją. To dobre źródło
napięcia, a nie błąd.

### 12.2 Długość kampanii (realna, nie marketingowa)
| Część | Noce | Czas |
|---|---|---|
| Prolog | 1 (plaża) | 15–20 min |
| Akt I (Rozdz. 1–4) | ~7 | ~1,5 h |
| Akt II (Rozdz. 5–8) | ~10 | ~2,5 h |
| Akt III (Rozdz. 9–11) | ~5 | ~1,5–2 h |
| Akt IV (Rozdz. 12 + epilog) | 2–3 | ~1 h |
| **Razem** | **~25 nocy** | **~6–7 h** (gracz, który eksploruje i gra wolne noce: 8–10 h) |

> Korekta wobec v1, gdzie było „8–12 h”: przy 6–7 min na cykl i ~25 nocach rdzeń zajmuje 6–7 h.

### 12.3 Trzy rodzaje wyzwalaczy
1. **PUSH (świat dzieje się sam)** odpala się o świcie po spełnieniu warunku poprzedniego beatu,
   najpóźniej po N wolnych nocach. Przykłady: gorączka Pipa, przypłynięcie Crane'a, fałszywa flaga,
   ultimatum. Gwarantuje to, że fabuła rusza nawet u gracza, który tylko się broni.
2. **PULL (gracz idzie tam, gdzie jest historia)** odpala się przy wejściu w strefę. Przykłady:
   parlament z Pashą, kaplica Anselma, sala tronowa Hold, kamienny krąg. Gracz sam decyduje, kiedy
   ruszyć. Znacznik celu i delikatne przypomnienia w barkach (np. Maud po 2 nocach zwłoki).
3. **EDGE (krawędzie pętli)** to zmierzch (dzwon), świt (wypłata, ognisko) i stan walki (próg HP
   bossa, zdobyta brama, wybity obóz).

**Zasady nienaruszalne:**
- **Sceny T2 nigdy w trakcie walki** (tylko świt, dzień albo wejście w strefę bez wrogów w
  zasięgu). W nocy wyłącznie barki i T0.
- **Jedyne wyjątki to śmierć Wata (Rozdz. 11) i zasadzka w kręgu.** Obie są oskryptowane, a walka
  jest ich częścią.
- Każdą scenę T2 da się pominąć, a każdą rozmowę T1 przerwać (wraca przy następnym ognisku).

### 12.4 Rytm rozdziału
`świt: scena lub ognisko → dzień: cel rozdziału (T0 + T1 w drodze) → zmierzch: dzwon → noc
specyficzna dla rozdziału → świt: wypłata` + 0–3 wolne noce (gracz buduje, eksploruje, słucha
ognisk). Wolne noce między rozdziałami to oddech. Rozdziały PUSH mają limit wolnych nocy, PULL nie.

### 12.5 Oś czasu scen
| Rozdz. | Scena T2 (długość) | Wyzwalacz | T1 (rozmowy) |
|---|---|---|---|
| Prolog | Sztorm i wrak (60–90 s) | nowa gra | — |
| Prolog | Maud czyta rozkazy (60 s) | koniec walki na plaży (PUSH) | marsz King's Road: Maud, Pip |
| Prolog | Fort i dzwon w wieży (30 s) | wejście w strefę fortu (PULL) | — |
| 1 | Pierwszy dzwon (20 s) | pierwszy zmierzch (EDGE) | Pip i sznur, Maud i budowa |
| 2–4 | — | — | ogniska; gorączka Pipa (PUSH); Hamid po uwolnieniu |
| 5 | Parlament z Pashą (90–120 s) | strefa białej flagi (PULL) | Hamid w drodze o pustyni |
| 6 | Zatopiona kaplica (45 s) | strefa kaplicy (PULL) | czytania Anselma (podniesienie strony) |
| 7 | Statki w zatoce (60–90 s) | świt po Rozdz. 6 + limit 2 nocy (PUSH) | Crane przy forcie, karta edyktu |
| 8 | Demaskowanie (120 s) | sala tronowa po zdobyciu twierdzy (PULL) | — |
| 9 | — | — | ognisko Wat–Maud bez hełmu; Crane w cztery oczy (PUSH) |
| 10 | Sala tronowa Hold, Garrok (2–3 min, najdłuższa) | strefa tronu po wyłomie (PULL) | Hamid tłumaczy w marszu powrotnym |
| 11 | Zasadzka w kręgu (60 s) | strefa kręgu o świcie (PULL) | — |
| 11 | Koperta i wyznanie (90 s) | powrót do fortu (PULL) | — |
| 11 | Śmierć Wata (45 s) | oskryptowana: brama + czas / próg HP | — |
| 12 | Ultimatum Crane'a (45 s) | świt po śmierci Wata (PUSH) | zbieranie sojuszników (Idris, szamanka) |
| 12 | Wieża: wybór (60 s) | strefa wieży (PULL) | — |
| 12 | Epilog RING / BREAK (2 min) | koniec ostatniej nocy | — |

**Bilans:** ~16 scen T2, razem **~15–18 min** filmów na 6–7 h gry (około 4%). Średnio jedna
scena co ~25 min, ale celowo nierówno: gęsto w prologu (wciągnięcie) i w Rozdz. 10–12
(kulminacja), rzadko w Akcie I i w Rozdz. 9 (gra i oddech). Rozmowy T1 wypadają co ~5–10 min, a
ogniska po każdym świcie są opcjonalne (0,5–1 min).
