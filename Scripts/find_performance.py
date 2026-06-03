from pathlib import Path

content = Path(
    "Data/Markdown/TeamJV_MAY.md"
).read_text(
    encoding="utf-8",
    errors="ignore"
)

content = content.replace("\\n", "\n")
content = content.replace("\\", "")

keywords = [
    "CSAT",
    "Survey",
    "Attendance",
    "ADH",
    "Adherence",
    "Performance",
    "Scorecard",
    "Agent Name",
    "Team Performance Overview",
]

lines = content.splitlines()

for keyword in keywords:
    print("\n" + "=" * 100)
    print(f"SEARCHING: {keyword}")
    print("=" * 100)

    for i, line in enumerate(lines):
        if keyword.lower() in line.lower():

            start = max(i - 10, 0)
            end = min(i + 30, len(lines))

            for x in range(start, end):
                print(lines[x])

            print("\n" + "-" * 100)
            break
        