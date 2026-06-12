from pathlib import Path
import re
import json

from app.services.pci_redaction_service import PCIRedactionService

TRANSCRIPTS_FOLDER = Path("Data/CALLS/TRANSCRIPTS")
OUTPUT_FOLDER = Path("Data/CALLS/ANALYZED")
OUTPUT_FOLDER.mkdir(parents=True, exist_ok=True)

RUBRIC = {
    "Greeting": {
        "weight": 11,
        "checks": {
            "Signature greeting": ["great day", "my name is"],
            "Agent identified self": ["my name is"],
            "Asked customer name": ["who do i have", "speaking with today"],
        },
    },
    "Acknowledge Customer": {
        "weight": 20,
        "checks": {
            "Active listening": ["correct", "right", "it was an order", "placed on"],
            "Empathy / positive tone": ["happy to help", "of course", "excellent"],
            "Ownership": ["i'll be happy", "let me", "i can", "i'm going to"],
            "Professional tone": ["please", "thank you", "ma'am"],
        },
    },
    "Service": {
        "weight": 30,
        "checks": {
            "Verification": ["phone number", "email", "verify your profile"],
            "Policy / process followed": ["refund", "place that order", "shipping charge"],
            "Customer kept informed": ["looks like", "let me go ahead", "i can see"],
            "Resolution provided": ["order has been issued", "confirmation", "order number"],
        },
    },
    "Sales / UPT": {
        "weight": 19,
        "checks": {
            "Upsell attempted": ["suggest", "bracelet", "additional", "package deal"],
            "Relevant offer": ["make a gorgeous addition", "go with that"],
        },
    },
    "Documentation & Wrap-up": {
        "weight": 20,
        "checks": {
            "Order recap": ["total", "shipping", "billing", "address"],
            "Confirmation / order number": ["order number", "confirmation"],
            "Additional assistance": ["anything else", "else i can assist"],
            "Signature closing": ["lovely speaking", "thank you", "have a good day"],
        },
    },
}


def load_transcript(path):
    raw = path.read_text(encoding="utf-8", errors="ignore")
    return PCIRedactionService().redact(raw)


def clean_text(text):
    text = text.lower()
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def extract_agent_name(filename):
    match = re.search(r"CXone recording_(.*?)_", filename)
    if match:
        return match.group(1).replace("_", " ")
    return "Unknown Agent"


def evaluate_check(text, keywords):
    matched = [kw for kw in keywords if kw in text]
    return len(matched) > 0, matched


def calculate_qa_score(text):
    section_results = {}
    total_score = 0

    for section, data in RUBRIC.items():
        checks = data["checks"]
        weight = data["weight"]

        passed = 0
        total_checks = len(checks)
        check_details = {}

        for check_name, keywords in checks.items():
            result, matched = evaluate_check(text, keywords)
            if result:
                passed += 1

            check_details[check_name] = {
                "result": "Yes" if result else "No",
                "matched_keywords": matched,
            }

        section_score = (passed / total_checks) * weight
        total_score += section_score

        section_results[section] = {
            "weight": weight,
            "passed": passed,
            "total_checks": total_checks,
            "section_score": round(section_score, 2),
            "details": check_details,
        }

    return round(total_score, 2), section_results


def get_risk_level(score):
    if score >= 90:
        return "Low Risk"
    if score >= 80:
        return "Moderate Risk"
    if score >= 70:
        return "High Risk"
    return "Critical Risk"


def get_opportunities(section_results):
    opportunities = []

    for section, data in section_results.items():
        for check_name, detail in data["details"].items():
            if detail["result"] == "No":
                opportunities.append(f"{section} - {check_name}")

    return opportunities


def generate_auditor_notes(score, opportunities):
    if not opportunities:
        return (
            "Strong interaction. The associate demonstrated proper call structure, "
            "ownership, verification, resolution, sales attempt, recap, and signature closing."
        )

    top_ops = "; ".join(opportunities[:4])

    return (
        f"The call was handled appropriately overall, with a QA score of {score}%. "
        f"Main opportunities identified: {top_ops}. The associate should continue focusing "
        "on making each required behavior explicit during the call to ensure consistency "
        "with the QA rubric and improve customer experience."
    )


def generate_coaching_summary(score, risk, opportunities):
    if not opportunities:
        return (
            "Reinforce current best practices. The associate should continue applying "
            "ownership language, clear verification, relevant sales positioning, recap, "
            "and branded signature closing."
        )

    return (
        f"QA performance is currently at {score}% with a {risk} classification. "
        f"The coaching focus should be: {', '.join(opportunities[:3])}. "
        "Supervisor should review the call with the associate, reinforce the expected behavior, "
        "and align on one measurable action for the next monitored interaction."
    )


def generate_markdown(transcript_file):
    pci_service = PCIRedactionService()
    raw = load_transcript(transcript_file)
    text = clean_text(raw)

    agent_name = extract_agent_name(transcript_file.name)
    score, section_results = calculate_qa_score(text)
    risk = get_risk_level(score)
    opportunities = get_opportunities(section_results)

    lines = []

    lines.append(f"# QA Call Analysis - {agent_name}")
    lines.append("")
    lines.append(f"**Source File:** `{transcript_file.name}`")
    lines.append(f"**QA Score:** {score}%")
    lines.append(f"**Risk Level:** {risk}")
    lines.append("")

    lines.append("## Section Score Breakdown")
    lines.append("")
    lines.append("| Section | Weight | Passed | Score |")
    lines.append("|---|---:|---:|---:|")

    for section, data in section_results.items():
        lines.append(
            f"| {section} | {data['weight']} | "
            f"{data['passed']}/{data['total_checks']} | "
            f"{data['section_score']} |"
        )

    lines.append("")
    lines.append("## Detailed QA Results")
    lines.append("")

    for section, data in section_results.items():
        lines.append(f"### {section}")
        for check_name, detail in data["details"].items():
            lines.append(f"- **{check_name}:** {detail['result']}")
        lines.append("")

    lines.append("## Opportunities")
    lines.append("")

    if opportunities:
        for op in opportunities:
            lines.append(f"- {op}")
    else:
        lines.append("- No major QA opportunities detected.")

    lines.append("")
    lines.append("## Auditor Notes")
    lines.append("")
    lines.append(generate_auditor_notes(score, opportunities))

    lines.append("")
    lines.append("## Coaching Summary")
    lines.append("")
    lines.append(generate_coaching_summary(score, risk, opportunities))

    lines.append("")
    lines.append("## Copy/Paste QA Form Notes")
    lines.append("")
    lines.append("```")
    lines.append(f"QA Score: {score}%")
    lines.append(f"Risk Level: {risk}")
    lines.append("")
    lines.append("Auditor Notes:")
    lines.append(generate_auditor_notes(score, opportunities))
    lines.append("")
    lines.append("Coaching Recommendation:")
    lines.append(generate_coaching_summary(score, risk, opportunities))
    lines.append("```")

    lines.append("")
    lines.append("## Transcript")
    lines.append("")
    lines.append(raw)

    safe_stem = pci_service.redact_filename_component(transcript_file.stem)
    output_file = OUTPUT_FOLDER / f"{safe_stem}_qa_analysis.md"
    output_file.write_text(
        pci_service.redact("\n".join(lines)),
        encoding="utf-8",
    )

    json_output = OUTPUT_FOLDER / f"{safe_stem}_qa_analysis.json"
    payload = pci_service.redact_structure(
        {
            "agent": agent_name,
            "source_file": transcript_file.name,
            "qa_score": score,
            "risk_level": risk,
            "opportunities": opportunities,
            "section_results": section_results,
            "auditor_notes": generate_auditor_notes(score, opportunities),
            "coaching_summary": generate_coaching_summary(score, risk, opportunities),
        }
    )
    json_output.write_text(
        json.dumps(
            payload,
            indent=4,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    return output_file


def main():
    transcript_files = list(TRANSCRIPTS_FOLDER.glob("*.md"))

    if not transcript_files:
        print("No transcript files found.")
        return

    for transcript_file in transcript_files:
        print(f"Analyzing: {transcript_file.name}")
        output = generate_markdown(transcript_file)
        print(f"Saved: {output}")

    print("\nDone.")


if __name__ == "__main__":
    main()
