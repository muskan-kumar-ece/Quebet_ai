from typing import Any
from app.services.ai.validators.base import (
    BaseValidator,
    StageResult,
    ValidationErrorItem,
    ValidationStage,
    ValidationStatus,
)


class CircuitSchemaValidator(BaseValidator):
    """
    Deterministic structural validator for circuit graphs.
    Enforces referential integrity, unique reference designators,
    valid pin-to-net connectivity, and malformed value detection.
    """

    @property
    def stage(self) -> ValidationStage:
        return ValidationStage.STAGE_1_SCHEMA

    async def validate(self, payload: dict[str, Any], context: dict[str, Any] | None = None) -> StageResult:
        errors: list[ValidationErrorItem] = []
        components = payload.get("components", [])
        nets = payload.get("nets", [])
        connections = payload.get("connections", [])

        # 1. Check for Duplicate Reference Designators
        seen_refs: set[str] = set()
        comp_ids_or_refs: set[str] = set()

        for idx, comp in enumerate(components):
            ref = comp.get("ref_des") or comp.get("id")
            if not ref:
                errors.append(
                    ValidationErrorItem(
                        code="MISSING_REF_DES",
                        message=f"Component at index {idx} has no reference designator (ref_des)",
                        field_path=f"components[{idx}].ref_des",
                        severity="error",
                    )
                )
                continue

            ref_upper = ref.strip().upper()
            if ref_upper in seen_refs:
                errors.append(
                    ValidationErrorItem(
                        code="DUPLICATE_REF_DES",
                        message=f"Duplicate reference designator '{ref}' detected. Each component must have a unique reference designator.",
                        field_path=f"components[{idx}].ref_des",
                        severity="error",
                    )
                )
            else:
                seen_refs.add(ref_upper)

            comp_id = comp.get("id")
            if comp_id:
                comp_ids_or_refs.add(comp_id)
            comp_ids_or_refs.add(ref)

            # Check for value existence
            val = comp.get("value")
            if not val or not str(val).strip():
                errors.append(
                    ValidationErrorItem(
                        code="MALFORMED_VALUE",
                        message=f"Component '{ref}' has empty or invalid value.",
                        field_path=f"components[{idx}].value",
                        severity="error",
                    )
                )

        # 2. Check Net Definitions
        seen_nets: set[str] = set()
        net_ids_or_names: set[str] = set()

        for idx, net in enumerate(nets):
            net_name = net.get("name")
            if not net_name:
                errors.append(
                    ValidationErrorItem(
                        code="MISSING_NET_NAME",
                        message=f"Net at index {idx} has no name.",
                        field_path=f"nets[{idx}].name",
                        severity="error",
                    )
                )
                continue

            net_upper = net_name.strip().upper()
            if net_upper in seen_nets:
                errors.append(
                    ValidationErrorItem(
                        code="DUPLICATE_NET_NAME",
                        message=f"Duplicate net name '{net_name}' declared.",
                        field_path=f"nets[{idx}].name",
                        severity="error",
                    )
                )
            else:
                seen_nets.add(net_upper)

            net_id = net.get("id")
            if net_id:
                net_ids_or_names.add(net_id)
            net_ids_or_names.add(net_name)

        # 3. Check Connection Referential Integrity
        net_connection_counts: dict[str, int] = {n: 0 for n in net_ids_or_names}

        for idx, conn in enumerate(connections):
            comp_ref = conn.get("component_id") or conn.get("ref_des")
            if comp_ref not in comp_ids_or_refs:
                errors.append(
                    ValidationErrorItem(
                        code="INVALID_COMPONENT_REFERENCE",
                        message=f"Connection at index {idx} references unknown component '{comp_ref}'.",
                        field_path=f"connections[{idx}].component_id",
                        severity="error",
                    )
                )

            pin_num = conn.get("pin_number")
            if not pin_num:
                errors.append(
                    ValidationErrorItem(
                        code="INVALID_PIN_REFERENCE",
                        message=f"Connection at index {idx} on component '{comp_ref}' has no pin_number specified.",
                        field_path=f"connections[{idx}].pin_number",
                        severity="error",
                    )
                )

            target_net = conn.get("net_id") or conn.get("net_name")
            if target_net not in net_ids_or_names:
                errors.append(
                    ValidationErrorItem(
                        code="INVALID_NET_REFERENCE",
                        message=f"Connection at index {idx} references unknown net '{target_net}'.",
                        field_path=f"connections[{idx}].net_id",
                        severity="error",
                    )
                )
            else:
                net_connection_counts[target_net] = net_connection_counts.get(target_net, 0) + 1

        # 4. Check for Dangling Nets (Nets with fewer than 2 endpoints are warnings)
        for net_identifier, count in net_connection_counts.items():
            if count == 1:
                errors.append(
                    ValidationErrorItem(
                        code="DANGLING_NET",
                        message=f"Net '{net_identifier}' connects to only 1 pin. Standard electrical nets require at least 2 nodes.",
                        field_path=f"nets.{net_identifier}",
                        severity="warning",
                    )
                )

        has_critical_errors = any(e.severity == "error" for e in errors)
        status = ValidationStatus.FAILED if has_critical_errors else ValidationStatus.PASSED
        score = 0.0 if has_critical_errors else (0.85 if any(e.severity == "warning" for e in errors) else 1.0)

        return StageResult(
            stage=self.stage,
            status=status,
            score=score,
            errors=errors,
            details={
                "component_count": len(components),
                "net_count": len(nets),
                "connection_count": len(connections),
                "has_errors": has_critical_errors,
            },
            message="Structural validation passed" if not has_critical_errors else f"Structural validation failed with {len(errors)} issues.",
        )


circuit_schema_validator = CircuitSchemaValidator()
