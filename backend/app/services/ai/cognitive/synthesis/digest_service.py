import hashlib
import json
from typing import Any, Dict


class ContextDigestService:
    """
    Computes canonical, reproducible SHA-256 digests over synthesized engineering contexts.
    
    INVARIANTS:
    - Two identical logical contexts produce identical digests.
    - Any revision increment or structural mutation produces a different digest.
    - Collections, IDs, and keys are canonically sorted and normalized.
    """

    @classmethod
    def calculate_canonical_digest(cls, context_dict: Dict[str, Any]) -> str:
        """
        Produces a canonical SHA-256 digest of the normalized logical context.
        """
        normalized = cls._normalize_value(context_dict)
        canonical_json = json.dumps(
            normalized,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        )
        return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()

    @classmethod
    def _normalize_value(cls, val: Any) -> Any:
        if isinstance(val, dict):
            # Exclude transient database IDs, timestamps, or volatile digests when computing content hash
            ignored_keys = {"created_at", "updated_at", "deleted_at", "canonical_digest"}
            normalized_dict = {}
            for k, v in val.items():
                if k not in ignored_keys:
                    normalized_dict[k] = cls._normalize_value(v)
            return normalized_dict
        elif isinstance(val, list):
            normalized_list = [cls._normalize_value(item) for item in val]
            # Try to sort deterministic objects by 'id' or serialized value if applicable
            try:
                return sorted(
                    normalized_list,
                    key=lambda x: str(x.get("id") if isinstance(x, dict) and "id" in x else x),
                )
            except Exception:
                return normalized_list
        else:
            return val
