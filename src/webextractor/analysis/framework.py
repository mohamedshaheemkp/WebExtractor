from __future__ import annotations

from webextractor.model.asset import Asset


class FrameworkDetector:
    """Detects frontend framework, site builder, or CMS from assets and HTML."""

    @staticmethod
    def detect(assets: list[Asset], html_content: str = "") -> str:
        signatures = {
            "Framer": [
                "framerusercontent.com",
                "events.framer.com",
                "framer.app",
                "__framer__",
                "framercms",
            ],
            "Next.js": [
                "_next/static",
                "__NEXT_DATA__",
                "_next/image",
            ],
            "Webflow": [
                "webflow.com",
                "website-files.com",
                "webflow.js",
                "w-nav",
            ],
            "React": [
                "react.production.min.js",
                "react-dom",
                "_reactRootContainer",
            ],
            "Vue": [
                "vue.min.js",
                "vue.runtime",
                "data-v-",
            ],
            "WordPress": [
                "wp-content",
                "wp-includes",
                "wp-json",
            ],
            "Shopify": [
                "cdn.shopify.com",
                "Shopify.theme",
            ],
        }

        combined_text = html_content.lower() + " " + " ".join(a.url.lower() for a in assets)

        for framework, hints in signatures.items():
            for hint in hints:
                if hint.lower() in combined_text:
                    return framework

        return "Standard HTML/JS"
