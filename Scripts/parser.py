from pathlib import Path
import re


MARKDOWN_FILE = Path("Data/Markdown/TeamJV_MAY.md")


def load_markdown(path: Path) -> str:
    return path.read_text(
        encoding="utf-8",
        errors="ignore"
    )


def clean_text(text: str) -> str:
    text = text.replace("\\n", "\n")
    text = text.replace("\\r", "")
    text = text.replace("\\t", " ")

    while "\\\\" in text:
        text = text.replace("\\\\", "\\")

    text = text.replace("\\", "")

    return text


def extract_sections(content: str):
    sections = re.findall(
        r"SECTION\s+\d+.*?(?=SECTION\s+\d+|$)",
        content,
        flags=re.DOTALL
    )

    return sections


def search_keywords(content: str, keywords, limit=5):
    lines = content.splitlines()

    for keyword in keywords:
        print(f"\n\n===== {keyword} =====")

        matches = [
            i for i, line in enumerate(lines)
            if keyword.lower() in line.lower()
        ]

        if not matches:
            print("No matches found.")
            continue

        for match in matches[:limit]:
            start = max(match - 2, 0)
            end = min(match + 5, len(lines))

            for line in lines[start:end]:
                print(line)

            print("-" * 100)


def main():
    raw_content = load_markdown(MARKDOWN_FILE)
    content = clean_text(raw_content)

    print(f"Loaded {len(content):,} characters")

    keywords = [
        "CSAT",
        "QA",
        "Attendance",
        "Adherence",
        "Agent",
        "Score",
        "Detractor",
        "Monitor",
        "Coaching",
        "Risk",
    ]

    search_keywords(content, keywords)

    sections = extract_sections(content)

    print("\n" + "=" * 100)
    print(f"Found {len(sections)} sections")
    print("=" * 100)

    for i, section in enumerate(sections[:5], start=1):
        print("\n" + "=" * 100)
        print(f"SECTION BLOCK {i}")
        print("=" * 100)
        print(section[:1000])


if __name__ == "__main__":
    main()
    