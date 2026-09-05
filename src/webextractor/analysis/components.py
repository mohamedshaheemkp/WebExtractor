from __future__ import annotations

import re
from bs4 import BeautifulSoup

from webextractor.model.component import ComponentNode


class ComponentAnalyzer:
    """Dissects webpage DOM into cohesive semantic components."""

    @staticmethod
    def analyze_components(html_content: str) -> list[ComponentNode]:
        soup = BeautifulSoup(html_content, "lxml")
        body = soup.find("body") or soup

        detected_components: list[ComponentNode] = []

        # 1. Navbar / Header
        nav = soup.find(["nav", "header"])
        if nav:
            links = [a.get_text().strip() for a in nav.find_all("a") if a.get_text().strip()]
            detected_components.append(
                ComponentNode(
                    name="Navbar",
                    category="navbar",
                    tag_name="header",
                    text_content=nav.get_text()[:100],
                    props={"links": links[:6] or ["Home", "Projects", "About", "Contact"]},
                )
            )

        # 2. Main sections
        sections = soup.find_all(["section", "article", "div"])
        meaningful_sections = []
        for sec in sections:
            cls = " ".join(sec.get("class", [])) if isinstance(sec.get("class"), list) else (sec.get("class") or "")
            sec_id = sec.get("id") or ""
            text = " ".join(sec.stripped_strings)
            headings = [h.get_text().strip() for h in sec.find_all(["h1", "h2", "h3"]) if h.get_text().strip()]

            if len(text) > 30 and (headings or cls or sec_id):
                meaningful_sections.append((sec, cls.lower(), sec_id.lower(), headings, text))

        seen_names = set()
        if nav:
            seen_names.add("Navbar")

        default_names = ["Hero", "Projects", "About", "Capabilities", "Voice", "Journey", "Toolkit", "Footer"]

        for idx, (el, cls, sec_id, headings, text) in enumerate(meaningful_sections[:8]):
            combined_tag = cls + " " + sec_id + " " + " ".join(headings).lower()
            name = None

            if "hero" in combined_tag or idx == 0:
                name = "Hero"
                cat = "hero"
            elif "project" in combined_tag or "work" in combined_tag or "case" in combined_tag:
                name = "Projects"
                cat = "card"
            elif "about" in combined_tag or "bio" in combined_tag:
                name = "About"
                cat = "section"
            elif "capabilit" in combined_tag or "service" in combined_tag or "feature" in combined_tag:
                name = "Capabilities"
                cat = "section"
            elif "voice" in combined_tag or "testimonial" in combined_tag:
                name = "Voice"
                cat = "section"
            elif "journey" in combined_tag or "timeline" in combined_tag or "story" in combined_tag:
                name = "Journey"
                cat = "section"
            elif "tool" in combined_tag or "stack" in combined_tag or "skill" in combined_tag:
                name = "Toolkit"
                cat = "section"
            elif "footer" in combined_tag:
                name = "Footer"
                cat = "footer"
            else:
                for candidate in default_names:
                    if candidate not in seen_names:
                        name = candidate
                        break
                if not name:
                    name = f"Section_{idx + 1}"
                cat = "section"

            if name in seen_names and name != "Section":
                name = f"{name}_{idx + 1}"
            seen_names.add(name)

            title = headings[0] if headings else name
            desc = text[:250].replace("\n", " ").strip()

            detected_components.append(
                ComponentNode(
                    name=name,
                    category=cat,
                    tag_name="section",
                    text_content=desc,
                    props={"title": title, "description": desc, "headings": headings},
                )
            )

        # Ensure at least Hero and Footer exist if page had sparse markup
        if "Hero" not in seen_names:
            detected_components.insert(
                1 if nav else 0,
                ComponentNode(
                    name="Hero",
                    category="hero",
                    tag_name="section",
                    props={"title": "Modern Digital Experience", "description": "High-fidelity reconstructed experience."},
                ),
            )
        if "Footer" not in seen_names:
            detected_components.append(
                ComponentNode(
                    name="Footer",
                    category="footer",
                    tag_name="footer",
                    props={"title": "Footer", "description": "All rights reserved."},
                )
            )

        return detected_components
