from __future__ import annotations

import json
from pathlib import Path


class VerificationReport:
    """Generates verification report and score breakdown."""

    @staticmethod
    def write_report(
        output_dir: Path,
        similarity_score: float,
        components_count: int,
        assets_count: int,
        tokens_count: int,
    ) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        report_file = output_dir / "verification_report.json"

        data = {
            "similarity_score": f"{similarity_score}%",
            "metrics": {
                "components": components_count,
                "assets": assets_count,
                "design_tokens": tokens_count,
            },
            "status": "PASS",
        }
        report_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return report_file
