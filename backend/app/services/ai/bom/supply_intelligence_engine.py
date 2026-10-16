from datetime import datetime, timezone
from typing import Any
from app.models.db.bom import PartAvailabilityStatus, PartLifecycleStatus


class BOMSupplyIntelligenceEngine:
    """
    Evaluates dynamic multi-source supply-chain data, temporal observations, and lifecycle status.
    Strict Invariants:
    - AVAILABLE != ENGINEERING_COMPATIBLE
    - CHEAPER != BETTER
    - HIGHER_STOCK != BETTER
    - ZERO SYNTHETIC SCORING
    - Multi-source conflicts must be represented explicitly (CONFLICTING).
    - Preserves temporal observation timestamps.
    """

    @classmethod
    def evaluate_availability(
        cls,
        supply_sources: list[dict[str, Any]],
    ) -> tuple[str, int, list[str]]:
        """
        Determines overall availability and detects supplier conflicts.
        Returns:
          (availability_status, total_stock, conflict_notes)
        """
        if not supply_sources:
            return PartAvailabilityStatus.UNKNOWN.value, 0, []

        has_in_stock = False
        has_out_of_stock = False
        total_stock = 0
        conflict_notes: list[str] = []

        for src in supply_sources:
            stock = int(src.get("stock", src.get("stock_quantity", 0)) or 0)
            supplier = src.get("supplier", "Unknown Supplier")
            total_stock += stock
            if stock > 0:
                has_in_stock = True
            else:
                has_out_of_stock = True

        if has_in_stock and has_out_of_stock:
            # Multi-source conflict: one supplier has stock, another has none
            in_suppliers = [s.get("supplier") for s in supply_sources if int(s.get("stock", s.get("stock_quantity", 0)) or 0) > 0]
            out_suppliers = [s.get("supplier") for s in supply_sources if int(s.get("stock", s.get("stock_quantity", 0)) or 0) == 0]
            conflict_notes.append(
                f"Multi-source stock discrepancy: available at {', '.join(in_suppliers)}, but out-of-stock at {', '.join(out_suppliers)}."
            )
            return PartAvailabilityStatus.CONFLICTING.value, total_stock, conflict_notes

        if total_stock > 50:
            return PartAvailabilityStatus.IN_STOCK.value, total_stock, []
        elif total_stock > 0:
            return PartAvailabilityStatus.LIMITED_STOCK.value, total_stock, []
        else:
            return PartAvailabilityStatus.OUT_OF_STOCK.value, 0, []

    @classmethod
    def evaluate_supply_sources(cls, supply_sources: list[dict[str, Any]]) -> dict[str, Any]:
        avail_status, total_stock, conflict_notes = cls.evaluate_availability(supply_sources)
        return {
            "availability_status": avail_status,
            "total_stock": total_stock,
            "has_conflict": avail_status == PartAvailabilityStatus.CONFLICTING.value,
            "conflict_notes": conflict_notes,
        }

    @classmethod
    def normalize_lifecycle(cls, raw_status: str | None) -> PartLifecycleStatus:
        str_val = cls.normalize_lifecycle_status(raw_status)
        return PartLifecycleStatus(str_val)

    @classmethod
    def normalize_lifecycle_status(cls, raw_status: str | None) -> str:
        """
        Maps manufacturer datasheet lifecycle declaration to canonical categorical lifecycle status.
        Never infers EOL or OBSOLETE from stock level.
        """
        if not raw_status:
            return PartLifecycleStatus.UNKNOWN.value

        norm = raw_status.strip().upper()
        if norm in ("ACTIVE", "PRODUCTION", "RECOMMENDED"):
            return PartLifecycleStatus.ACTIVE.value
        elif norm in ("PREVIEW", "NEW", "ANNOUNCED", "FUTURE"):
            return PartLifecycleStatus.PREVIEW.value
        elif norm in ("NRND", "NOT_RECOMMENDED", "NOT RECOMMENDED FOR NEW DESIGNS"):
            return PartLifecycleStatus.NRND.value
        elif norm in ("EOL", "END_OF_LIFE", "LAST_BUY", "DISCONTINUED_SOON"):
            return PartLifecycleStatus.EOL.value
        elif norm in ("OBSOLETE", "DISCONTINUED", "PHASE_OUT"):
            return PartLifecycleStatus.OBSOLETE.value
        else:
            return PartLifecycleStatus.UNKNOWN.value

    @classmethod
    def summarize_pricing_structure(cls, supply_sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        Structures dynamic tiered pricing observations across suppliers with timestamp provenance.
        Strictly prohibits composite cost scores or 'winner' annotations.
        """
        pricing_data: list[dict[str, Any]] = []
        for src in supply_sources:
            if src.get("unit_price") is not None:
                pricing_data.append(
                    {
                        "supplier": src.get("supplier", "UNKNOWN"),
                        "unit_price": float(src.get("unit_price", 0.0)),
                        "currency": src.get("currency", "USD"),
                        "qty_break": int(src.get("qty_break", 1)),
                        "observed_at": src.get("observed_at") or datetime.now(timezone.utc).isoformat(),
                        "source": src.get("source_url") or src.get("source_trust", "COMMERCIAL_OBSERVATION"),
                    }
                )
        return pricing_data
