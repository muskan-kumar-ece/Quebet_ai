import hashlib
import re
from typing import Any


class SpiceModelRegistry:
    """
    Registry and security validator for SPICE device models and subcircuits (.model, .subckt).
    Provides built-in models for standard semiconductors and validates custom models.
    """

    # Built-in models verified for safety and standard SPICE compliance
    BUILT_IN_MODELS: dict[str, str] = {
        # Standard switching diode
        "1N4148": ".model 1N4148 D (IS=2.682n RS=0.5664 N=1.752 BV=100 IBV=100u CJO=4p VJ=0.75 M=0.333 TT=5.76n)",
        # Rectifier diode
        "1N4001": ".model 1N4001 D (IS=14.11n RS=0.03389 N=1.984 BV=50 IBV=10u CJO=51.17p VJ=0.3905 M=0.3541 TT=5.04u)",
        # Zener diode (5.1V)
        "BZX84C5V1": ".model BZX84C5V1 D (IS=1e-15 RS=0.5 N=1 BV=5.1 IBV=5m CJO=400p)",
        # NPN General Purpose BJT
        "2N2222": ".model 2N2222 NPN (IS=14.34f XTI=3 EG=1.11 VAF=74.03 BF=255.9 NE=1.307 ISE=14.34f IKF=0.2847 XTB=1.5 BR=6.092 NC=2 ISC=0 IKR=0 RC=1 CJC=7.306p MJC=0.3416 VJC=0.75 FC=0.5 CJE=22.01p MJE=0.377 VJE=0.75 TR=46.91n TF=411.1p ITF=0.6 VTF=1.7 XTF=3 RB=10)",
        "2N3904": ".model 2N3904 NPN (IS=1E-14 VAF=100 BF=300 IKF=0.4 XTB=1.5 BR=4 CJC=4E-12 CJE=8E-12 RB=20 RC=0.1 RE=0.1 TR=100E-9 TF=400E-12)",
        # PNP General Purpose BJT
        "2N3906": ".model 2N3906 PNP (IS=1E-14 VAF=100 BF=200 IKF=0.4 XTB=1.5 BR=4 CJC=4.5E-12 CJE=10E-12 RB=20 RC=0.1 RE=0.1 TR=100E-9 TF=400E-12)",
        # N-Channel MOSFET
        "2N7000": ".model 2N7000 NMOS (VTO=2.1 KP=0.12 RD=1.2 RS=1.2 CBD=25p CBS=25p CGDO=20p CGSO=20p)",
    }

    @classmethod
    def validate_model_text(cls, spice_text: str) -> tuple[bool, str | None]:
        """Validates that model text conforms to safety and format standards."""
        if not spice_text or not spice_text.strip():
            return False, "Model text cannot be empty"

        # Security check: disallow shell escape sequences, backticks, pipes, semicolons, command chaining, path traversal
        forbidden = [r"\.sys", r"\bshell\b", r"`", r"\|", r";", r"&&", r"\$\(", r"\.\./", r"\.\.\\"]
        for pattern in forbidden:
            if re.search(pattern, spice_text, re.IGNORECASE):
                return False, f"Model definition contains forbidden security token: {pattern}"

        # Disallow dangerous .include and .lib directives to prevent file inclusion
        if re.search(r"^\s*(\.include|\.lib)\b", spice_text, re.IGNORECASE | re.MULTILINE):
            return False, ".include and .lib directives are not permitted in isolated model definitions"

        # Must define .model or .subckt
        has_model = bool(re.search(r"^\s*\.model\b", spice_text, re.IGNORECASE | re.MULTILINE))
        has_subckt = bool(re.search(r"^\s*\.subckt\b", spice_text, re.IGNORECASE | re.MULTILINE))

        if not (has_model or has_subckt):
            return False, "Model text must define either a .model or .subckt block"

        if has_subckt:
            has_ends = bool(re.search(r"^\s*\.ends\b", spice_text, re.IGNORECASE | re.MULTILINE))
            if not has_ends:
                return False, ".subckt block must terminate with .ends"

        return True, None

    MODEL_PROVENANCE_METADATA: dict[str, dict[str, Any]] = {
        "1N4148": {
            "component": "Fast Switching Diode",
            "part_number": "1N4148",
            "model_source": "Standard Berkeley SPICE 3f5 / ngspice reference library",
            "source_revision": "SPICE-3F5-STD",
            "is_manufacturer_certified": False,
            "classification": "GENERIC_REFERENCE_MODEL",
            "applicability": "GENERAL_FUNCTIONAL_SIMULATION",
        },
        "1N4001": {
            "component": "1A General Purpose Rectifier",
            "part_number": "1N4001",
            "model_source": "Standard Berkeley SPICE 3f5 / ngspice reference library",
            "source_revision": "SPICE-3F5-STD",
            "is_manufacturer_certified": False,
            "classification": "GENERIC_REFERENCE_MODEL",
            "applicability": "GENERAL_FUNCTIONAL_SIMULATION",
        },
        "BZX84C5V1": {
            "component": "5.1V Zener Diode",
            "part_number": "BZX84C5V1",
            "model_source": "Generic behavioral Zener SPICE model",
            "source_revision": "GENERIC-ZENER-V1",
            "is_manufacturer_certified": False,
            "classification": "GENERIC_REFERENCE_MODEL",
            "applicability": "VOLTAGE_REGULATION_MOCK",
        },
        "2N2222": {
            "component": "NPN Small Signal Transistor",
            "part_number": "2N2222",
            "model_source": "Standard Berkeley SPICE 3f5 / ngspice reference library",
            "source_revision": "SPICE-3F5-STD",
            "is_manufacturer_certified": False,
            "classification": "GENERIC_REFERENCE_MODEL",
            "applicability": "GENERAL_FUNCTIONAL_SIMULATION",
        },
        "2N3904": {
            "component": "NPN General Purpose Transistor",
            "part_number": "2N3904",
            "model_source": "Standard Berkeley SPICE 3f5 / ngspice reference library",
            "source_revision": "SPICE-3F5-STD",
            "is_manufacturer_certified": False,
            "classification": "GENERIC_REFERENCE_MODEL",
            "applicability": "GENERAL_FUNCTIONAL_SIMULATION",
        },
        "2N3906": {
            "component": "PNP General Purpose Transistor",
            "part_number": "2N3906",
            "model_source": "Standard Berkeley SPICE 3f5 / ngspice reference library",
            "source_revision": "SPICE-3F5-STD",
            "is_manufacturer_certified": False,
            "classification": "GENERIC_REFERENCE_MODEL",
            "applicability": "GENERAL_FUNCTIONAL_SIMULATION",
        },
        "2N7000": {
            "component": "N-Channel Small Signal MOSFET",
            "part_number": "2N7000",
            "model_source": "Level 1 Shichman-Hodges generic model",
            "source_revision": "GENERIC-NMOS-L1",
            "is_manufacturer_certified": False,
            "classification": "GENERIC_REFERENCE_MODEL",
            "applicability": "SWITCHING_FUNCTIONAL_SIMULATION",
        },
    }

    @classmethod
    def get_model(cls, part_or_model_name: str) -> str | None:
        """Retrieves a verified SPICE model by part number or model name."""
        clean = part_or_model_name.strip().upper()
        return cls.BUILT_IN_MODELS.get(clean)

    @classmethod
    def get_model_metadata(cls, part_or_model_name: str) -> dict[str, Any] | None:
        """Retrieves verified model provenance metadata without fabricating manufacturer claims."""
        clean = part_or_model_name.strip().upper()
        meta = cls.MODEL_PROVENANCE_METADATA.get(clean)
        if not meta:
            return None
        model_text = cls.get_model(clean) or ""
        return {
            **meta,
            "model_content": model_text,
            "model_digest": hashlib.sha256(model_text.strip().encode("utf-8")).hexdigest(),
        }

    @classmethod
    def compute_model_digest(cls, models: list[str]) -> str:
        """Computes a deterministic SHA-256 digest of attached model definitions."""
        if not models:
            return hashlib.sha256(b"NO_MODELS").hexdigest()
        sorted_models = sorted(m.strip() for m in models if m.strip())
        content = "\n".join(sorted_models).encode("utf-8")
        return hashlib.sha256(content).hexdigest()
