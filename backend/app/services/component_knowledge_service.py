import json
from pathlib import Path
from typing import Any

KB_DIR = Path(__file__).resolve().parent.parent.parent.parent / "packages" / "electronics-kb" / "data"


class ComponentKnowledgeService:
    """
    Retrieval service for validated electronics domain knowledge datasets.
    Provides structured specs for resistors, capacitors, ICs, Indian-market availability,
    and failure mode engineering rules.
    """

    def __init__(self, data_dir: Path | None = None) -> None:
        self.data_dir = data_dir or KB_DIR
        self._cache: dict[str, Any] = {}

    def _load_json(self, rel_path: str) -> dict[str, Any]:
        if rel_path in self._cache:
            return self._cache[rel_path]

        file_path = self.data_dir / rel_path
        if not file_path.exists():
            return {}

        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            self._cache[rel_path] = data
            return data

    def get_resistors(self) -> dict[str, Any]:
        return self._load_json("components/resistors.json")

    def get_capacitors(self) -> dict[str, Any]:
        return self._load_json("components/capacitors.json")

    def get_ics(self) -> dict[str, Any]:
        return self._load_json("components/ics.json")

    def get_indian_market(self) -> dict[str, Any]:
        return self._load_json("components/indian-market.json")

    def get_component_failures(self) -> dict[str, Any]:
        return self._load_json("failure-modes/component-failures.json")

    def get_emi_rules(self) -> dict[str, Any]:
        return self._load_json("failure-modes/emi.json")

    def get_thermal_rules(self) -> dict[str, Any]:
        return self._load_json("failure-modes/thermal.json")

    def search_components(self, query: str) -> list[dict[str, Any]]:
        """Searches ICs, common resistors, and capacitors for matches."""
        q = query.lower().strip()
        results: list[dict[str, Any]] = []

        # 1. Search ICs
        ics_data = self.get_ics()
        for reg in ics_data.get("linear_regulators", []):
            if q in reg.get("part_number", "").lower() or q in reg.get("type", "").lower():
                results.append({"category": "linear_regulator", **reg})

        for mcu in ics_data.get("microcontrollers", []):
            if q in mcu.get("part_number", "").lower() or q in mcu.get("manufacturer", "").lower():
                results.append({"category": "microcontroller", **mcu})

        # 2. Search Indian Market
        mkt_data = self.get_indian_market()
        for item in mkt_data.get("components", []):
            if q in item.get("generic_name", "").lower() or q in item.get("part_number", "").lower():
                results.append({"category": "indian_market", **item})

        return results


component_knowledge_service = ComponentKnowledgeService()
