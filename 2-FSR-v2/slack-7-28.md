Fix: bullet items appearing as section headings in chunk metadata (doc bdd56c7a, ESN 298464)

Found the root cause — the heading detection in our PDF parser was treating ALL-CAPS bullet list items (like • 1469-2R1-DC EMERGENCY PUMP RECOMMENDATIONS) as section headings, since Python's isupper() ignores the • character. This caused section_2 to be populated with bullet text instead of actual section titles.

Two fixes applied:

Parser (parsing.py) — bullet-prefixed lines (•, -, *, –, etc.) are now explicitly excluded from heading detection upstream
Chunker (chunking.py) — added a second-layer filter to drop any bullet-prefixed or (preamble) values that slip through before they reach chunk metadata
This should fix section_2 = "• 2022 1469-2R1-DC EMERGENCY PUMP RECOMMENDATIONS" and section_2 = "INLET SYSTEM" (that one was a wrapped bullet line fragment). The "No Section" issue on some chunks is a separate char-offset alignment gap — will look at that independently.