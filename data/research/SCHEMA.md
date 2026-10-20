# Research schema (one JSON file per research group)

File = JSON array of race objects:

```json
[
  {
    "race_id": "kraj-ba | mesto-bratislava | mc-stare-mesto (lowercase, ascii, hyphen)",
    "name": "Bratislavský samosprávny kraj | Bratislava | Staré Mesto",
    "office": "predseda VUC | primator | starosta",
    "incumbent": {"name": "...", "since": 2022, "party_2022": "...", "running_2026": true},
    "history": {
      "2022": {
        "turnout_pct": 46.1,
        "registered_voters": 123456,
        "valid_votes": 56789,
        "results": [{"name": "...", "party": "nominating parties or NEKA", "votes": 12345, "pct": 41.2}],
        "source": "https://volby.statistics.sk/..."
      },
      "2017 or 2018": { "...same shape..." }
    },
    "candidates_2026": [
      {
        "name": "Titles Firstname Surname (as on ballot)",
        "ballot_no": 1,
        "party": "exact nomination: party / coalition, or NEKA (nezávislý)",
        "endorsed_by": "parties that support but do not formally nominate, if known",
        "incumbent": false,
        "withdrew": false,
        "prior_runs": "e.g. 2022 BSK 2nd with 18.3 %",
        "profile": "1 sentence: current/previous office, notability"
      }
    ],
    "candidates_source": ["url", "..."],
    "polls": [
      {"pollster": "AKO", "fieldwork": "2026-09-20/2026-09-27", "n": 1000, "sponsor": "...",
       "results": {"Candidate name": 34.0}, "undecided_pct": 20, "source": "url"}
    ],
    "odds": [
      {"bookmaker": "Tipsport", "date": "2026-10-18", "odds": {"Candidate name": 1.25}, "source": "url"}
    ],
    "key_events": [{"date": "2026-09-30", "text": "...", "source": "url"}],
    "notes": "free text: dynamics, scandals, coalition deals, endorsements, anything that matters for forecasting"
  }
]
```

Rules:
- Every number needs a source URL. Never invent. If something is unknown, use `null` and say so in `notes`.
- Candidate list must be COMPLETE (all registered candidates, including minor ones), because vote shares must sum to 100 %.
- Prefer ŠÚ SR (volby.statistics.sk) for historical results and official registered candidate lists (2026 lists on volby.statistics.sk or the municipal/regional election commission's site).
- Withdrawn candidates: keep them with `"withdrew": true` + date + source (in SK they stay on the ballot if withdrawn after printing; votes for them are not counted).
