#!/usr/bin/env python3
"""Bulk upload resumes to Resume Matcher.

Usage:
    python bulk_upload.py --api-url http://localhost:8000 --cohort-id <ID> --folder ./resumes/
    python bulk_upload.py --api-url http://localhost:8000 --cohort-id <ID> --csv students.csv --folder ./resumes/

CSV format (optional, maps filenames to student IDs):
    filename,student_id,name,email
    john_doe.pdf,student_001,John Doe,john@college.edu

Without CSV, filenames are used as student IDs (e.g., student_001.pdf -> student_001).
"""

import argparse
import csv
import os
import sys
import time
from pathlib import Path

try:
    import requests
except ImportError:
    print("ERROR: 'requests' library required. Install with: pip install requests")
    sys.exit(1)


def create_cohort(api_url: str, name: str) -> str:
    """Create a new cohort and return its ID."""
    res = requests.post(f"{api_url}/api/v1/admin/cohorts", json={"name": name})
    res.raise_for_status()
    data = res.json()
    print(f"✓ Created cohort: {data['name']} ({data['cohort_id']})")
    return data["cohort_id"]


def add_students(api_url: str, cohort_id: str, students: list[dict]) -> None:
    """Add students to a cohort."""
    res = requests.post(
        f"{api_url}/api/v1/admin/cohorts/{cohort_id}/students",
        json={"students": students},
    )
    res.raise_for_status()
    data = res.json()
    print(f"✓ Added {len(data['students'])} students to cohort")


def upload_resume(api_url: str, filepath: Path, user_id: str) -> dict:
    """Upload a single resume file."""
    with open(filepath, "rb") as f:
        files = {"file": (filepath.name, f, "application/pdf")}
        headers = {"X-User-ID": user_id}
        res = requests.post(
            f"{api_url}/api/v1/resumes/upload", files=files, headers=headers
        )
    if res.status_code == 200:
        data = res.json()
        return {"status": "ok", "resume_id": data.get("resume_id", "?")}
    else:
        return {"status": "error", "error": res.text[:200]}


def main():
    parser = argparse.ArgumentParser(description="Bulk upload resumes to Resume Matcher")
    parser.add_argument("--api-url", default="http://localhost:8000", help="Backend API URL")
    parser.add_argument("--cohort-id", help="Existing cohort ID (omit to create new)")
    parser.add_argument("--cohort-name", help="Name for new cohort")
    parser.add_argument("--folder", required=True, help="Folder containing resume PDFs")
    parser.add_argument("--csv", help="CSV file mapping filenames to student details")
    parser.add_argument("--delay", type=float, default=1.0, help="Delay between uploads (seconds)")
    args = parser.parse_args()

    folder = Path(args.folder)
    if not folder.is_dir():
        print(f"ERROR: Folder not found: {folder}")
        sys.exit(1)

    # Collect PDF files
    pdf_files = sorted(folder.glob("*.pdf")) + sorted(folder.glob("*.PDF"))
    docx_files = sorted(folder.glob("*.docx")) + sorted(folder.glob("*.DOCX"))
    all_files = pdf_files + docx_files

    if not all_files:
        print(f"ERROR: No PDF/DOCX files found in {folder}")
        sys.exit(1)

    print(f"Found {len(all_files)} resume files")

    # Create or use existing cohort
    cohort_id = args.cohort_id
    if not cohort_id:
        name = args.cohort_name or f"Resume Cohort {time.strftime('%Y-%m-%d')}"
        cohort_id = create_cohort(args.api_url, name)

    # Load CSV mapping if provided
    filename_map: dict[str, dict] = {}
    if args.csv:
        with open(args.csv) as f:
            reader = csv.DictReader(f)
            for row in reader:
                filename_map[row["filename"]] = {
                    "user_id": row.get("student_id", row.get("roll_number", row["filename"].rsplit(".", 1)[0])),
                    "name": row.get("name", row["filename"].rsplit(".", 1)[0].replace("_", " ").title()),
                    "email": row.get("email"),
                    "college": row.get("college"),
                    "roll_number": row.get("roll_number"),
                }

    # Build student list and upload
    students_to_create = []
    upload_plan = []

    for filepath in all_files:
        fname = filepath.name
        if fname in filename_map:
            info = filename_map[fname]
        else:
            stem = fname.rsplit(".", 1)[0]
            info = {
                "user_id": stem,
                "name": stem.replace("_", " ").title(),
                "email": f"{stem}@cohort.local",
            }
        students_to_create.append(info)
        upload_plan.append((filepath, info["user_id"]))

    # Create students (ignore errors for existing students)
    if students_to_create:
        try:
            add_students(args.api_url, cohort_id, students_to_create)
        except Exception as e:
            print(f"⚠ Some students may already exist: {e}")

    # Upload resumes
    print(f"\nUploading {len(upload_plan)} resumes...")
    success = 0
    failed = 0

    for i, (filepath, user_id) in enumerate(upload_plan, 1):
        print(f"  [{i}/{len(upload_plan)}] {filepath.name} -> {user_id}...", end=" ")
        try:
            result = upload_resume(args.api_url, filepath, user_id)
            if result["status"] == "ok":
                print(f"✓ (resume_id: {result['resume_id']})")
                success += 1
            else:
                print(f"✗ ({result['error'][:80]})")
                failed += 1
        except Exception as e:
            print(f"✗ ({str(e)[:80]})")
            failed += 1

        if i < len(upload_plan):
            time.sleep(args.delay)

    print(f"\n{'─' * 50}")
    print(f"Done! {success} uploaded, {failed} failed")
    print(f"Cohort ID: {cohort_id}")
    print(f"View dashboard: http://localhost:3000/admin")


if __name__ == "__main__":
    main()
