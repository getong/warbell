# Village-life VO voices (ElevenLabs v3, 2026-10-12)

Re-takes and new `life_*` lines MUST use the same voice per prefix:

| prefix | role | ElevenLabs voice |
|---|---|---|
| `life_m_*` | peasant man | Darby Skelm — Witty and Sarcastic |
| `life_w_*` | housewife | MoanElisa — Sultry, Dark, Velvet |
| `life_v_*` | market vendor | Luna — bubbly BFF, bright, cheery |
| `life_e_*` | old man | Alder — Warm, Raspy and Comforting |
| `life_c_*` | child | Omar J — Very Young Storyteller |
| `life_g_*` | guard | Wilf — Cheerful, Quirky & Northern |

Settings: speed 0.89, stability 0.34, similarity 0.75. Script: `docs/audio/elevenlabs-zycie-wsi.md`.
Processing: cut per line, per-voice gain to -16 LUFS, quiet lines lifted to >= -24 LUFS, limiter -1 dBFS, mono 44.1 kHz Vorbis q5.
Missing (not in the take): `life_w_chat_2`.

Two-hander dialogues `life_dlg_*` (script: `docs/audio/elevenlabs-dialogi-wsi.md`), man side recorded 2026-10-15:
the man lines of dialogues 01–08 are Darby Skelm; those of 12, 13, 16, 17, 18 plus `life_dlg_08_9` and
`life_m_chat_2` are **Richie**. Re-take `life_dlg_08_9` and `life_m_chat_2` with Darby Skelm (voice switches otherwise).
Cut by faster-whisper word alignment + silence, every clip re-transcribed to verify.
