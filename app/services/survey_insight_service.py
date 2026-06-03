from collections import defaultdict, Counter
from pathlib import Path


class SurveyInsightService:

    def __init__(self, surveys, agent_registry):
        self.surveys = surveys
        self.agent_registry = agent_registry

    def _csat(self, osat):
        try:
            return round(float(osat) * 10, 2)
        except Exception:
            return 0

    def _clean_comment(self, comment):
        if comment is None:
            return ""

        comment = str(comment).strip()

        if comment.lower() in ["nan", "none", ""]:
            return ""

        return comment

    def _classify(self, csat):
        if csat >= 90:
            return "Promoter"

        if csat >= 70:
            return "Neutral"

        return "Detractor"

    def _detect_theme(self, text):
        text_lower = str(text).lower()

        themes = {
            "Shipping / Delivery": [
                "shipping", "delivery", "delivered", "package",
                "shipment", "lost", "tracking", "arrived"
            ],
            "Returns / Exchanges": [
                "return", "exchange", "refund", "credit",
                "label", "mail back"
            ],
            "Agent Service": [
                "helpful", "kind", "nice", "patient",
                "professional", "friendly", "excellent"
            ],
            "Resolution": [
                "resolved", "fixed", "solution", "solved",
                "helped", "issue"
            ],
            "Policy / Promo": [
                "policy", "promotion", "discount", "coupon",
                "price", "adjustment", "sale"
            ],
            "Website / System": [
                "website", "online", "app", "system",
                "email", "password", "login"
            ],
            "Product / Order": [
                "order", "item", "size", "color",
                "product", "stock"
            ],
            "Communication": [
                "explained", "understand", "clear",
                "confusing", "communication"
            ]
        }

        detected = []

        for theme, keywords in themes.items():
            if any(keyword in text_lower for keyword in keywords):
                detected.append(theme)

        if not detected:
            detected.append("Other")

        return detected

    def build_insights(self):
        total = len(self.surveys)

        promoters = []
        neutrals = []
        detractors = []

        theme_counter = Counter()
        promoter_themes = Counter()
        detractor_themes = Counter()

        agent_breakdown = defaultdict(
            lambda: {
                "surveys": 0,
                "csat_total": 0,
                "promoters": 0,
                "neutrals": 0,
                "detractors": 0,
                "comments": []
            }
        )

        voc_positive = []
        voc_negative = []

        for survey in self.surveys:
            csat = self._csat(survey.score)
            classification = self._classify(csat)
            comment = self._clean_comment(survey.comment)

            agent = self.agent_registry.find_agent(survey.agent_id)

            agent_name = agent.name if agent else survey.agent_name

            row = {
                "contact_id": survey.contact_id,
                "agent_id": survey.agent_id,
                "agent_name": agent_name,
                "csat": csat,
                "comment": comment,
                "brand": survey.brand,
                "top_reason": survey.top_reason,
                "disposition": survey.disposition,
                "classification": classification
            }

            agent_data = agent_breakdown[survey.agent_id]
            agent_data["surveys"] += 1
            agent_data["csat_total"] += csat

            if comment:
                agent_data["comments"].append(comment)

            themes = self._detect_theme(
                f"{comment} {survey.top_reason} {survey.disposition}"
            )

            for theme in themes:
                theme_counter[theme] += 1

            if classification == "Promoter":
                promoters.append(row)
                agent_data["promoters"] += 1

                for theme in themes:
                    promoter_themes[theme] += 1

                if comment:
                    voc_positive.append(row)

            elif classification == "Detractor":
                detractors.append(row)
                agent_data["detractors"] += 1

                for theme in themes:
                    detractor_themes[theme] += 1

                if comment:
                    voc_negative.append(row)

            else:
                neutrals.append(row)
                agent_data["neutrals"] += 1

        for agent_id, data in agent_breakdown.items():
            data["avg_csat"] = round(
                data["csat_total"] / data["surveys"],
                2
            )

        return {
            "total_surveys": total,
            "promoters": promoters,
            "neutrals": neutrals,
            "detractors": detractors,
            "theme_counter": theme_counter,
            "promoter_themes": promoter_themes,
            "detractor_themes": detractor_themes,
            "agent_breakdown": agent_breakdown,
            "voc_positive": voc_positive,
            "voc_negative": voc_negative
        }

    def load_ai_prompt(self):
        prompt_file = Path("app/prompts/survey_insights_prompt.md")

        if not prompt_file.exists():
            raise FileNotFoundError(
                f"Prompt file not found: {prompt_file}"
            )

        return prompt_file.read_text(encoding="utf-8")

    def export_markdown_report(self, output_path):
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        insights = self.build_insights()

        total = insights["total_surveys"]
        promoters = len(insights["promoters"])
        neutrals = len(insights["neutrals"])
        detractors = len(insights["detractors"])

        avg_csat = 0

        if total:
            all_rows = (
                insights["promoters"]
                + insights["neutrals"]
                + insights["detractors"]
            )

            avg_csat = round(
                sum(item["csat"] for item in all_rows) / total,
                2
            )

        lines = []

        lines.append("# Survey Insights Report")
        lines.append("")
        lines.append("## 1. CSAT Overview")
        lines.append("")
        lines.append(f"- Total surveys: {total}")
        lines.append(f"- Average CSAT: {avg_csat}")
        lines.append(f"- Promoters: {promoters}")
        lines.append(f"- Neutrals: {neutrals}")
        lines.append(f"- Detractors: {detractors}")
        lines.append("")

        lines.append("## 2. Top VOC Themes")
        lines.append("")

        for theme, count in insights["theme_counter"].most_common():
            lines.append(f"- {theme}: {count}")

        lines.append("")

        lines.append("## 3. Promoter Drivers")
        lines.append("")

        for theme, count in insights["promoter_themes"].most_common():
            lines.append(f"- {theme}: {count}")

        lines.append("")

        lines.append("## 4. Detractor Drivers")
        lines.append("")

        for theme, count in insights["detractor_themes"].most_common():
            lines.append(f"- {theme}: {count}")

        lines.append("")

        lines.append("## 5. Positive VOC Samples")
        lines.append("")

        for item in insights["voc_positive"][:15]:
            lines.append(
                f"- Contact {item['contact_id']} | "
                f"{item['agent_name']} | "
                f"CSAT {item['csat']}: "
                f"{item['comment']}"
            )

        lines.append("")

        lines.append("## 6. Negative VOC Samples")
        lines.append("")

        for item in insights["voc_negative"][:15]:
            lines.append(
                f"- Contact {item['contact_id']} | "
                f"{item['agent_name']} | "
                f"CSAT {item['csat']}: "
                f"{item['comment']}"
            )

        lines.append("")

        lines.append("## 7. Agent Breakdown")
        lines.append("")

        for agent_id, data in insights["agent_breakdown"].items():
            agent = self.agent_registry.find_agent(agent_id)
            agent_name = agent.name if agent else agent_id

            lines.append(f"### {agent_name}")
            lines.append(f"- Surveys: {data['surveys']}")
            lines.append(f"- Avg CSAT: {data['avg_csat']}")
            lines.append(f"- Promoters: {data['promoters']}")
            lines.append(f"- Neutrals: {data['neutrals']}")
            lines.append(f"- Detractors: {data['detractors']}")
            lines.append("")

        lines.append("## 8. User Story Drafts")
        lines.append("")
        lines.append(
            "- As a customer, I want clear expectations about my order or return, "
            "so that I do not need to contact support again."
        )
        lines.append(
            "- As a customer, I want agents to explain policies clearly, "
            "so that I understand what options are available."
        )
        lines.append(
            "- As a customer, I want my issue resolved in the first interaction, "
            "so that I feel confident continuing with the brand."
        )
        lines.append(
            "- As a supervisor, I want to identify repeated detractor drivers, "
            "so that I can coach agents based on real customer feedback."
        )
        lines.append(
            "- As an operations leader, I want to know which processes generate dissatisfaction, "
            "so that I can prioritize improvements."
        )
        lines.append("")

        lines.append("## 9. PMCE AI Prompt for Interpretation")
        lines.append("")

        try:
            ai_prompt = self.load_ai_prompt()
            lines.append(ai_prompt)
        except Exception as e:
            lines.append(f"Prompt could not be loaded: {e}")

        lines.append("")

        output_path.write_text(
            "\n".join(lines),
            encoding="utf-8"
        )

        return output_path