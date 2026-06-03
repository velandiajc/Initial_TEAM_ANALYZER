from pathlib import Path

content = Path(
    "Data/Markdown/TeamJV_MAY.md"
).read_text(
    encoding="utf-8",
    errors="ignore"
)

content = content.replace("\\n", "\n")
content = content.replace("\\", "")

lines = content.splitlines()

for i, line in enumerate(lines):
    if "Team Performance Overview" in line:
        print("\nFOUND TEAM PERFORMANCE OVERVIEW\n")
        print("=" * 100)

        for x in range(i, min(i + 100, len(lines))):
            print(lines[x])

        break
    