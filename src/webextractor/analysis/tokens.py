from __future__ import annotations

from collections import Counter
from typing import Any


class DesignTokenExtractor:
    """
    Extract recurring visual values from the rendered DOM.

    Values are evidence gathered from computed styles.
    They are not assumed to be the original design tokens.
    """

    def extract(
        self,
        root: dict[str, Any],
    ) -> dict[str, Any]:

        nodes = []

        self._walk(root, nodes)

        return {
            "colors": self._colors(nodes),
            "typography": self._typography(nodes),
            "spacing": self._spacing(nodes),
            "radii": self._radii(nodes),
            "layout": self._layout(nodes),
        }

    def _walk(
        self,
        node: dict[str, Any] | None,
        result: list[dict[str, Any]],
    ):

        if not node:
            return

        result.append(node)

        for child in node.get(
            "children",
            [],
        ):
            self._walk(child, result)

    def _colors(
        self,
        nodes: list[dict[str, Any]],
    ):

        values = Counter()

        for node in nodes:

            styles = node.get(
                "styles",
                {},
            )

            for key in (
                "color",
                "backgroundColor",
            ):

                value = styles.get(key)

                if value:
                    values[value] += 1

        return [
            {
                "value": value,
                "usage": count,
            }
            for value, count in values.most_common()
        ]

    def _typography(
        self,
        nodes: list[dict[str, Any]],
    ):

        families = Counter()
        sizes = Counter()
        weights = Counter()
        line_heights = Counter()

        for node in nodes:

            styles = node.get(
                "styles",
                {},
            )

            if styles.get("fontFamily"):
                families[
                    styles["fontFamily"]
                ] += 1

            if styles.get("fontSize"):
                sizes[
                    styles["fontSize"]
                ] += 1

            if styles.get("fontWeight"):
                weights[
                    styles["fontWeight"]
                ] += 1

            if styles.get("lineHeight"):
                line_heights[
                    styles["lineHeight"]
                ] += 1

        return {
            "families": self._counter(
                families
            ),
            "sizes": self._counter(
                sizes
            ),
            "weights": self._counter(
                weights
            ),
            "line_heights": self._counter(
                line_heights
            ),
        }

    def _spacing(
        self,
        nodes: list[dict[str, Any]],
    ):

        padding = Counter()
        margin = Counter()

        for node in nodes:

            styles = node.get(
                "styles",
                {},
            )

            if styles.get("padding"):
                padding[
                    styles["padding"]
                ] += 1

            if styles.get("margin"):
                margin[
                    styles["margin"]
                ] += 1

        return {
            "padding": self._counter(
                padding
            ),
            "margin": self._counter(
                margin
            ),
        }

    def _radii(
        self,
        nodes: list[dict[str, Any]],
    ):

        radii = Counter()

        for node in nodes:

            value = (
                node.get("styles", {})
                .get("borderRadius")
            )

            if value:
                radii[value] += 1

        return self._counter(radii)

    def _layout(
        self,
        nodes: list[dict[str, Any]],
    ):

        displays = Counter()
        positions = Counter()

        for node in nodes:

            styles = node.get(
                "styles",
                {},
            )

            if styles.get("display"):
                displays[
                    styles["display"]
                ] += 1

            if styles.get("position"):
                positions[
                    styles["position"]
                ] += 1

        return {
            "display": self._counter(
                displays
            ),
            "position": self._counter(
                positions
            ),
        }

    @staticmethod
    def _counter(
        counter: Counter,
    ):

        return [
            {
                "value": value,
                "usage": count,
            }
            for value, count in counter.most_common()
        ]


# Backward-compatible alias
TokenExtractor = DesignTokenExtractor
