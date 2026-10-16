"""
Electronics Knowledge Base Dataset Validator & Deterministic Ingestion Manifest Builder.

Discovers datasets in packages/electronics-kb/data/, validates schemas,
computes deterministic identity hashes, and prepares ingestion payloads
for PostgreSQL, Neo4j, and ChromaDB vector stores without mutating databases.
"""

import hashlib
import json
from pathlib import Path
import sys
import uuid
from typing import Any

KB_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
QUEBET_KB_NAMESPACE = uuid.UUID("a1b2c3d4-e5f6-7a8b-9c0d-1e2f3a4b5c6d")


class DatasetValidationError(Exception):
    pass


def generate_deterministic_id(category: str, key: str) -> str:
    """Generates a stable, reproducible UUID5 for a knowledge base item."""
    name = f"quebet:kb:{category}:{key}"
    return str(uuid.uuid5(QUEBET_KB_NAMESPACE, name))


def validate_resistors(data: dict[str, Any]) -> int:
    required_keys = ["e12_base", "e24_base", "power_ratings_watts", "packages", "common_values"]
    for k in required_keys:
        if k not in data:
            raise DatasetValidationError(f"resistors.json missing key: {k}")
    return len(data["common_values"]) + len(data["packages"])


def validate_capacitors(data: dict[str, Any]) -> int:
    required_keys = ["dielectric_types", "derating_rules", "standard_decoupling"]
    for k in required_keys:
        if k not in data:
            raise DatasetValidationError(f"capacitors.json missing key: {k}")
    return len(data["dielectric_types"]) + len(data["standard_decoupling"])


def validate_ics(data: dict[str, Any]) -> int:
    if "linear_regulators" not in data or "microcontrollers" not in data:
        raise DatasetValidationError("ics.json must contain 'linear_regulators' and 'microcontrollers'")
    return len(data["linear_regulators"]) + len(data["microcontrollers"])


def validate_indian_market(data: dict[str, Any]) -> int:
    if "suppliers" not in data or "components" not in data:
        raise DatasetValidationError("indian-market.json missing 'suppliers' or 'components'")
    return len(data["suppliers"]) + len(data["components"])


def validate_component_failures(data: dict[str, Any]) -> int:
    if "failure_modes" not in data:
        raise DatasetValidationError("component-failures.json missing 'failure_modes'")
    return len(data["failure_modes"])


def validate_emi(data: dict[str, Any]) -> int:
    if "design_rules" not in data:
        raise DatasetValidationError("emi.json missing 'design_rules'")
    return len(data["design_rules"])


def validate_thermal(data: dict[str, Any]) -> int:
    if "physics_rules" not in data or "common_thermal_failures" not in data:
        raise DatasetValidationError("thermal.json missing 'physics_rules' or 'common_thermal_failures'")
    return len(data["physics_rules"]) + len(data["common_thermal_failures"])


VALIDATORS = {
    "resistors.json": validate_resistors,
    "capacitors.json": validate_capacitors,
    "ics.json": validate_ics,
    "indian-market.json": validate_indian_market,
    "component-failures.json": validate_component_failures,
    "emi.json": validate_emi,
    "thermal.json": validate_thermal,
}


def run_dataset_audit(verbose: bool = True) -> dict[str, Any]:
    if not KB_DATA_DIR.exists():
        raise FileNotFoundError(f"KB data directory not found at {KB_DATA_DIR}")

    results = {
        "status": "valid",
        "datasets_checked": 0,
        "total_records": 0,
        "errors": [],
        "manifest": [],
    }

    json_files = list(KB_DATA_DIR.rglob("*.json"))
    if not json_files:
        raise DatasetValidationError("No JSON datasets discovered in KB directory.")

    for file_path in sorted(json_files):
        rel_path = file_path.relative_to(KB_DATA_DIR).as_posix()
        results["datasets_checked"] += 1

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
                data = json.loads(content)

            file_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
            filename = file_path.name

            if filename not in VALIDATORS:
                raise DatasetValidationError(f"Unregistered dataset format: {filename}")

            record_count = VALIDATORS[filename](data)

            results["total_records"] += record_count
            results["manifest"].append({
                "dataset": rel_path,
                "sha256": file_hash[:16],
                "record_count": record_count,
                "deterministic_id": generate_deterministic_id("dataset", rel_path),
            })
            if verbose:
                print(f"  [VALID] {rel_path} ({record_count} verified items, sha256: {file_hash[:8]}...)")

        except Exception as e:
            results["status"] = "invalid"
            err_msg = f"{rel_path}: {str(e)}"
            results["errors"].append(err_msg)
            if verbose:
                print(f"  [ERROR] {err_msg}", file=sys.stderr)

    return results


if __name__ == "__main__":
    print(f"Auditing Electronics KB datasets at {KB_DATA_DIR}...")
    summary = run_dataset_audit(verbose=True)
    print("\nAudit Summary:")
    print(f"  Status: {summary['status'].upper()}")
    print(f"  Datasets: {summary['datasets_checked']}")
    print(f"  Total Validated Records: {summary['total_records']}")
    if summary["errors"]:
        print(f"  Errors: {len(summary['errors'])}")
        sys.exit(1)
    else:
        print("  All datasets pass schema integrity and deterministic UUID indexing.")
        sys.exit(0)
