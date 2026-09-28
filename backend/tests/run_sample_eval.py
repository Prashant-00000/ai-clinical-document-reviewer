"""
Comprehensive evaluation runner for all synthetic sample documents against /api/analyze.
"""
import json
import sys
from pathlib import Path
import httpx

API_URL = "http://127.0.0.1:8000/api/analyze"
SAMPLES_DIR = Path(__file__).resolve().parent.parent.parent / "samples"


def test_samples():
    # Scanned PDFs require a vision transcription call followed by analysis.
    client = httpx.Client(timeout=180.0)
    results = {}

    samples = [
        ("clean_note.txt", "text", "text"),
        ("clean_note.pdf", "file", "application/pdf"),
        ("incomplete_note.txt", "text", "text"),
        ("inconsistent_note.txt", "text", "text"),
        ("scanned_note.png", "file", "image/png"),
        ("scanned_note.pdf", "file", "application/pdf"),
        ("irrelevant_text.txt", "text", "text"),
    ]

    for filename, kind, mime in samples:
        filepath = SAMPLES_DIR / filename
        print(f"\n==================================================")
        print(f"Testing sample: {filename} ({kind})")
        print(f"==================================================")

        if not filepath.exists():
            print(f"ERROR: {filepath} does not exist!")
            continue

        try:
            if kind == "text":
                text_content = filepath.read_text(encoding="utf-8")
                resp = client.post(API_URL, data={"text": text_content})
            else:
                with open(filepath, "rb") as f:
                    file_bytes = f.read()
                resp = client.post(
                    API_URL,
                    files={"file": (filename, file_bytes, mime)}
                )

            if resp.status_code != 200:
                print(f"FAILED with HTTP {resp.status_code}: {resp.text}")
                results[filename] = {"status_code": resp.status_code, "error": resp.text}
                continue

            data = resp.json()
            report = data.get("report", {})
            status = data.get("status")
            input_type = data.get("input_type")
            summary = report.get("report_summary")
            doc_quality = report.get("document_quality", {})
            inconsistencies = report.get("potential_inconsistencies", [])
            missing_info = report.get("missing_information", [])
            requires_review = report.get("requires_review", [])

            results[filename] = {
                "http_status": resp.status_code,
                "analysis_status": status,
                "input_type": input_type,
                "summary": summary,
                "doc_quality_notes": doc_quality.get("notes"),
                "inconsistencies_count": len(inconsistencies),
                "inconsistencies": [i.get("text") for i in inconsistencies],
                "missing_info_count": len(missing_info),
                "missing_info": [m.get("text") for m in missing_info],
                "requires_review": [r.get("text") for r in requires_review],
            }

            print(f"Status: {status}")
            print(f"Input Type: {input_type}")
            print(f"Summary:\n{summary}")
            if inconsistencies:
                print(f"Flags/Inconsistencies ({len(inconsistencies)}):")
                for inc in inconsistencies:
                    print(f"  • {inc.get('text')}")
            if doc_quality.get("notes"):
                print(f"Quality Notes: {doc_quality.get('notes')}")

        except Exception as exc:
            print(f"Exception during request for {filename}: {exc}")
            results[filename] = {"error": str(exc)}

    out_file = SAMPLES_DIR / "sample_results.json"
    out_file.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"\nSaved full results to {out_file}")


if __name__ == "__main__":
    test_samples()
