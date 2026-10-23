import csv
import io

from .models import Question

FIELDS = ["skill", "difficulty", "topic", "prompt", "option_a", "option_b", "option_c", "option_d",
          "answer_key", "explanation", "marks", "active"]
SKILLS = {"sql", "python"}
LEVELS = {"easy", "intermediate", "advanced"}


def import_csv(fileobj):
    """Import questions from a CSV file object. Returns (created, skipped, errors)."""
    raw = fileobj.read()
    text = raw.decode("utf-8-sig") if isinstance(raw, bytes) else raw
    reader = csv.DictReader(io.StringIO(text))
    missing = [f for f in FIELDS[:9] if f not in (reader.fieldnames or [])]
    if missing:
        return 0, 0, [f"Missing columns: {', '.join(missing)}"]

    created, skipped, errors = 0, 0, []
    for n, row in enumerate(reader, start=2):
        row = {k: (v or "").strip() for k, v in row.items() if k}
        row["skill"], row["difficulty"] = row["skill"].lower(), row["difficulty"].lower()
        row["answer_key"] = row["answer_key"].upper()
        if row["skill"] not in SKILLS:
            errors.append(f"Row {n}: skill must be sql or python"); continue
        if row["difficulty"] not in LEVELS:
            errors.append(f"Row {n}: difficulty must be easy, intermediate or advanced"); continue
        if row["answer_key"] not in ("A", "B", "C", "D"):
            errors.append(f"Row {n}: answer_key must be A-D"); continue
        if not row["prompt"] or not all(row[f"option_{c}"] for c in "abcd"):
            errors.append(f"Row {n}: prompt and four options are required"); continue
        if Question.objects.filter(skill=row["skill"], difficulty=row["difficulty"], prompt=row["prompt"]).exists():
            skipped += 1; continue
        marks = int(row.get("marks") or 1) if (row.get("marks") or "1").isdigit() else 1
        Question.objects.create(
            skill=row["skill"], difficulty=row["difficulty"], topic=row.get("topic", ""), prompt=row["prompt"],
            option_a=row["option_a"], option_b=row["option_b"], option_c=row["option_c"], option_d=row["option_d"],
            answer_key=row["answer_key"], explanation=row.get("explanation", ""), marks=marks,
            active=(row.get("active", "1").lower() not in ("0", "false", "no")),
        )
        created += 1
    return created, skipped, errors
