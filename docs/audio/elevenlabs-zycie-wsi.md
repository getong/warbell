# ElevenLabs: życie zamku i przedmieść (VO + SFX)

Kodowi gry odpowiadają klucze `life_*`: pliki trafiają do `assets/audio/vo/life/<klucz>.ogg` i `assets/audio/sfx/life/<klucz>.ogg`.

## Jak generować

- **Model:** Eleven v3, Stability „Natural”. Tagi w nawiasach kwadratowych to audio tagi v3.
- **Format pracy:** jedna generacja na głos. Wklej cały blok danego głosu: każda kwestia w osobnym akapicie, bez numerów i kluczy (są tu tylko dla porządku).
- **Pliki:** prześlij mi jeden mp3 na głos, np. `man_a.mp3`, `woman_a.mp3` (albo jeden plik ze wszystkim po kolei). Potnę po ciszy i przypiszę w kolejności z tabel.
- **Nieudana kwestia:** jeśli któraś wyjdzie źle, wygeneruj sam ten akapit osobno i dopisz w nazwie pliku jej klucz.
- **Odgłosy (SFX):** generuj w *Sound Effects*, każdy osobno, z podaną długością. Prompt Influence ≈ 0.4.

## Użyte głosy (ElevenLabs, 2026-10-12) — NIE ZMIENIAĆ przy dogrywkach

| ID | Głos ElevenLabs (biblioteka) |
|---|---|
| `man_a` | **Darby Skelm** — Witty and Sarcastic |
| `woman_a` | **MoanElisa** — Sultry, Dark, Velvet |
| `vendor` | **Luna** — bubbly BFF, bright, cheery |
| `elder` | **Alder** — Warm, Raspy and Comforting |
| `child` | **Omar J** — Very Young Storyteller |
| `guard` | **Wilf** — Cheerful, Quirky & Northern |

Model Eleven v3; ustawienia z nazwy pliku: speed 0.89, stability 0.34, similarity 0.75 (`sp89_s34_sb75_v4`).
Ten sam spis jest w `assets/audio/vo/life/VOICES.md` i przy kluczach `life_*` w `src/audio/lines.rs`.

**Brakujące w nagraniu (generator pominął, do dogrania tym samym głosem):** `life_m_chat_2` (Darby Skelm), `life_w_chat_2` (MoanElisa).

## Głosy (pierwotny brief)

| ID | Postać | Voice Design prompt (albo podobny głos z biblioteki) |
|---|---|---|
| `man_a` | chłop, robotnik, 40+ | ten sam co dotychczasowi wieśniacy (**„Victor — deep”**), żeby wieś brzmiała spójnie |
| `woman_a` | gospodyni, ~45 | *„Earthy middle-aged Englishwoman from a poor rural village, warm but blunt, slightly hoarse, dry humour, natural pace”* |
| `vendor` | przekupka na targu, ~25 | *„Bright, quick-witted young Englishwoman, market trader, cheeky and persuasive, clear projecting voice”* |
| `elder` | starzec | *„Very old rural Englishman, thin raspy voice, slow, a little wheezy, fond of complaining”* |
| `child` | dziecko ~9 lat | *„Energetic 9-year-old child, playful, breathless, giggly, English village accent”* (jeśli generator odmówi głosu dziecka, weź najjaśniejszy młody głos z biblioteki i podnieś go o +3 półtony; resztę zrobię w grze) |
| `guard` | strażnik, ~35 | *„Gruff tired English soldier, low voice, clipped sentences, sardonic”* |

---

## man_a: chłop
| klucz | tekst |
|---|---|
| `life_m_greet_1` | [respectful] M'lord. |
| `life_m_greet_2` | [tired] Morning, Ser Godric. Or what's left of it. |
| `life_m_greet_3` | [sarcastic] Ah, the armour's out for a walk. Good day to it. |
| `life_m_buy_1` | [suspicious] How much for the bread? |
| `life_m_buy_2` | [outraged] Three pennies? For that? It's mostly air! |
| `life_m_buy_3` | [grumbling] Fine. Fine. Robbery, but fine. |
| `life_m_buy_4` | [hopeful] Any salt today? |
| `life_m_chat_1` | Did you hear the bell last night? [sighs] Course you did. Everyone hears the bell. |
| `life_m_chat_2` | Fence is down again by the barley. Third time. |
| `life_m_chat_3` | [chuckles] He fell asleep on the woodpile. Snoring like a bear. |
| `life_m_chat_4` | [lowered voice] They say the knight never takes that helmet off. Not even to eat. |
| `life_m_sit` | [groans] Oh, my back. Oh, that's better. |
| `life_m_stand` | [grunts] Right. Up we get. |
| `life_m_eat` | [chewing] Hm. Stale. Again. |
| `life_m_work_1` | [effort] Hup! |
| `life_m_work_2` | [effort grunt] Come on, you stubborn thing! |
| `life_m_work_3` | [exhales heavily] That's the last of it. Till tomorrow. |
| `life_m_yawn` | [yawns] Hhhaaah. Too early for living. |
| `life_m_laugh` | [laughs heartily] |
| `life_m_dusk` | [uneasy] Sun's going. Best get inside. |
| `life_m_kid` | [shouting] Oi! Get down off that cart! |

## woman_a: gospodyni
| klucz | tekst |
|---|---|
| `life_w_greet_1` | [warm] Ser Godric. Mind the chickens. |
| `life_w_greet_2` | [dry] Oh, it's you. Wipe your boots. |
| `life_w_buy_1` | [haggling] Two eggs and the cabbage. And not the one with the worm. |
| `life_w_buy_2` | [firm] I'll give you two pennies. Not a crumb more. |
| `life_w_buy_3` | [satisfied] Pleasure doing business. Mostly. |
| `life_w_chat_1` | [gossiping] She's walking out with the cooper's boy. The cooper's boy! |
| `life_w_chat_2` | Need rain for the beans. And none of us need orks. |
| `life_w_chat_3` | [laughs] He thinks I didn't see him with the ale. I see everything. |
| `life_w_chat_4` | [worried] Pip's not sleeping. Up the tower at all hours with that rope. |
| `life_w_laundry` | [sighs] Wash it, hang it, it rains. Every single time. |
| `life_w_sweep` | [muttering] Dust, mud, dust, mud. |
| `life_w_water` | [effort] Hnn. Heavier every day, this bucket. |
| `life_w_call_kid` | [calling out] Tom! Supper! Now, not in a minute! |
| `life_w_scold` | [stern] What did I say about the well? |
| `life_w_dusk` | [calling] Shutters! Everyone, shutters! |
| `life_w_laugh` | [laughs] |
| `life_w_sit` | [sighs contentedly] Ah. Five minutes. |

## vendor: przekupka na targu
| klucz | tekst |
|---|---|
| `life_v_call_1` | [calling out] Bread! Fresh bread! Fresh-ish! |
| `life_v_call_2` | [calling out] Cabbages, onions, turnips the orks missed! |
| `life_v_call_3` | [calling out] Pots! Good pots! Don't leak! Much! |
| `life_v_haggle_1` | [cheeky] Three pennies, love. Times are hard. |
| `life_v_haggle_2` | [mock offended] Two? You'll starve me! [sighs] Fine. Two and a half. |
| `life_v_haggle_3` | [sweetly] For you? Same price as everyone. But I'll smile. |
| `life_v_sold` | [cheerful] Done! Mind how you go. |
| `life_v_hero_1` | [flirty] Shiny armour like that, you can afford the good loaf. |
| `life_v_hero_2` | [teasing] Does the knight eat? Or does he just glare at bread? |
| `life_v_slow` | [bored] Quiet day. Even the flies are thinking twice. |
| `life_v_laugh` | [laughs brightly] |

## elder: starzec
| klucz | tekst |
|---|---|
| `life_e_greet` | [squinting] Eh? Oh. The knight. Taller than I thought. |
| `life_e_chat_1` | [reminiscing] In my day we had proper winters. Snow up to your ears. |
| `life_e_chat_2` | [grumbling] Young ones. No patience. Couldn't wait for a kettle. |
| `life_e_chat_3` | [quietly] My grandfather said this fort was cursed. Never said why. |
| `life_e_doze` | [snores softly] Mm. Mmm. [snorts awake] I'm awake! |
| `life_e_whittle` | [humming tunelessly] Hmm-hmm, hmm-hmm. |
| `life_e_cough` | [coughs] Damp. It's always the damp. |
| `life_e_stand` | [groans] Up. Up. Bones like dry sticks. |
| `life_e_laugh` | [wheezy laugh] |

## child: dziecko
| klucz | tekst |
|---|---|
| `life_c_tag` | [excited] Tag! You're it! |
| `life_c_unfair` | [whining] Not fair! You cheated! |
| `life_c_run` | [giggling, breathless] Can't catch me! |
| `life_c_knight_1` | [awed whisper] Look. It's the knight. |
| `life_c_knight_2` | [curious] Is it hot in there? In the helmet? |
| `life_c_knight_3` | [excited] Can I hold the sword? Just once? |
| `life_c_mum` | [calling] Mu-um! He pushed me! |
| `life_c_laugh` | [laughs uncontrollably] |
| `life_c_hide` | [whispering] Shh! I'm hiding! |
| `life_c_count` | [loudly] One, two, three, four, five... coming! |

## guard: strażnik
| klucz | tekst |
|---|---|
| `life_g_greet_1` | [curt] M'lord. |
| `life_g_greet_2` | [dry] All quiet. For now. |
| `life_g_patrol` | [muttering] Wall, wall, more wall. Lovely wall. |
| `life_g_gate` | [firm] Gate shuts at dusk. No exceptions. |
| `life_g_kid` | [stern] You. Off the rampart. Now. |
| `life_g_yawn` | [yawns] Hhh. Who scheduled the dawn so early. |
| `life_g_dusk` | [alert] Bell's soon. Torches lit, eyes open. |

---

## SFX (Sound Effects, każdy osobno)
| klucz | prompt | długość |
|---|---|---|
| `life_sfx_coins` | a few copper coins dropped and slid across a wooden market counter, close | 1.5 s |
| `life_sfx_purse` | small leather coin purse jingling as it is tied shut | 1.2 s |
| `life_sfx_bench_sit` | person sitting down heavily on an old wooden bench, wood creak | 1.0 s |
| `life_sfx_bench_stand` | person getting up from a creaky wooden bench, cloth rustle | 1.0 s |
| `life_sfx_stool` | wooden stool scraping on packed dirt floor | 0.8 s |
| `life_sfx_bread` | tearing a crusty loaf of bread by hand | 1.0 s |
| `life_sfx_mug` | wooden tankard set down on a wooden table, liquid slosh | 0.8 s |
| `life_sfx_pour` | pouring ale from a clay jug into a wooden cup | 2.0 s |
| `life_sfx_well` | medieval well winch cranking with rope creak, then bucket splash far below | 4.0 s |
| `life_sfx_bucket` | carrying a full wooden bucket of water, sloshing, footsteps on dirt | 2.5 s |
| `life_sfx_sweep` | straw broom sweeping a dirt doorstep, slow strokes | 3.0 s, loop |
| `life_sfx_laundry` | shaking out a wet linen sheet and pinning it on a line, flap | 2.0 s |
| `life_sfx_rug_beat` | beating a hanging rug with a wicker beater, three thumps | 2.0 s |
| `life_sfx_hammer` | hammering a nail into timber, four strikes | 2.0 s |
| `life_sfx_saw` | hand saw cutting a wooden plank, steady strokes | 3.0 s, loop |
| `life_sfx_whittle` | knife whittling a small piece of wood, soft scrapes | 2.5 s, loop |
| `life_sfx_grain` | handful of grain scattered on dirt, chickens clucking and pecking | 3.0 s |
| `life_sfx_sack` | heavy grain sack thrown onto a shoulder, thump and cloth | 1.0 s |
| `life_sfx_basket` | wicker basket set down on the ground, creak | 0.8 s |
| `life_sfx_door` | heavy medieval wooden cottage door opening on iron hinges | 1.5 s |
| `life_sfx_door_shut` | heavy wooden cottage door closing with a latch | 1.2 s |
| `life_sfx_shutters` | wooden window shutters swung closed and barred | 1.5 s |
| `life_sfx_cart` | wooden hand cart rolling slowly on a dirt track, wheel creak | 4.0 s, loop |
| `life_sfx_dice` | bone dice rolled on a wooden table, men murmur | 2.0 s |
| `life_sfx_chatter` | small group of medieval villagers chatting and laughing quietly outdoors, no clear words | 8.0 s, loop |
| `life_sfx_market` | busy small medieval village market, distant haggling, livestock, no clear words | 10.0 s, loop |
| `life_sfx_hen` | single hen clucking nearby | 1.5 s |
