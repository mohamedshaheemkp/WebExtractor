from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from typing import Any


class RepetitionDetector:

    def detect(
        self,
        root: dict[str, Any],
    ) -> dict[str, Any]:

        groups = defaultdict(list)

        self._walk(
            root,
            groups,
        )

        repeated = {}

        for signature, nodes in groups.items():

            if len(nodes) < 2:
                continue

            repeated[signature] = {
                "count": len(nodes),
                "nodes": nodes,
            }

        return repeated

    def _walk(
        self,
        node: dict[str, Any] | None,
        groups: dict,
    ):

        if not node:
            return

        signature = self._signature(
            node
        )

        groups[signature].append(
            {
                "tag": node.get("tag"),
                "id": node.get("id"),
                "classes": node.get(
                    "classes",
                    [],
                ),
                "text": node.get(
                    "text",
                    "",
                )[:100],
            }
        )

        for child in node.get(
            "children",
            [],
        ):
            self._walk(
                child,
                groups,
            )

    def _signature(
        self,
        node: dict[str, Any],
    ) -> str:

        normalized = {
            "tag": node.get("tag"),
            "classes": sorted(
                node.get(
                    "classes",
                    [],
                )
            ),
            "child_tags": [
                child.get("tag")
                for child in node.get(
                    "children",
                    [],
                )
            ],
        }

        raw = json.dumps(
            normalized,
            sort_keys=True,
        )

        return hashlib.sha1(
            raw.encode("utf-8")
        ).hexdigest()
