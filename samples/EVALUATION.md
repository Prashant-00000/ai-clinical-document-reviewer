# Synthetic Sample Evaluation

These results were collected by submitting each sample to `POST /api/analyze`
with the local Gemini configuration. All sample content is synthetic.

| Sample | Input type | Resulting status | What was flagged | Accuracy note |
|---|---|---|---|---|
| `clean_note.txt` | Text | `completed` | One missing-information item: allergy reaction/severity for NKDA. | The main patient, diagnosis, symptoms, vitals, and medications were extracted consistently with the source. |
| `clean_note.pdf` | Searchable PDF | `completed` | Same allergy reaction/severity documentation item as the text version. | PyMuPDF preserved the text layer and the analysis matched the text sample. |
| `incomplete_note.txt` | Text | `completed` | Missing age, allergies, medication doses/strengths, RR, SpO2. | The explicitly missing fields were identified; no unsupported age, allergy, or dose was fabricated. |
| `inconsistent_note.txt` | Text | `completed_with_warnings` | Penicillin/amoxicillin conflict, HR 300, temperature 20 C, unsupported acute-cystitis diagnosis, and duplicate lisinopril. | The requested contradictions were all surfaced by the rule checks. |
| `scanned_note.png` | Image | `completed` | No consistency flags; image vision extraction used. | The visible patient, migraine diagnosis, vitals, allergy, and medication details were read correctly. The source's photophobia/phonophobia details were omitted from the returned summary. The previous false duplicate-medication finding is fixed: current medication plus its onset plan is treated as one regimen. |
| `scanned_note.pdf` | Image-only PDF | `completed` | No consistency flags; scanned-PDF vision fallback used. | Vision extracted the main patient, migraine, vitals, allergy, and medication details. The source's photophobia/phonophobia details were omitted from the returned summary. The previous false duplicate-medication finding is fixed, and the real Lisinopril duplicate rule remains active. |
| `irrelevant_text.txt` | Text | `no_clinical_content` | No clinical flags. | Correctly returned no clinical content and no fabricated patient, diagnosis, symptom, vital, medication, or allergy data. |

The scanned-PDF result is specifically identified by the quality note:
`PDF appears to be scanned; used vision model for text extraction.`

## Limitations

Duplicate detection uses heuristics and may miss or over-suppress unusual
phrasings. In particular, the current rule treats a medication listed as
current and repeated in a plan with an equivalent "at onset" instruction as
one regimen. This avoids the observed Sumatriptan false positive, but similar
wording could hide a real duplicate or fail to recognize a duplicate written
in a different form. Brand/generic normalization is also limited to a small
set of common aliases.