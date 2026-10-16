from typing import Any, Dict, List, Optional
from pydantic import BaseModel
from fastapi import HTTPException, status
from app.models.schemas.cognitive import CapabilityDeclaration
from app.services.ai.cognitive.capability_registry import capability_registry


class CapabilityPolicyDecision(BaseModel):
    allowed: bool
    capability_id: str
    capability: CapabilityDeclaration
    violations: List[str] = []


class CapabilityExecutionError(HTTPException):
    def __init__(self, code: str, message: str, capability_id: str):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": code,
                "message": message,
                "capability_id": capability_id,
            },
        )


class CapabilityExecutionPolicy:
    """
    Centralized execution policy evaluator for the QUEBET AI Cognitive Layer.
    Strictly server-authoritative: LLM/client outputs can NEVER override registry invariants.
    """

    @classmethod
    def evaluate(
        cls,
        capability_id: str,
        tenant_id: str,
        plan_tenant_id: str,
        actor_permissions: Optional[List[str]] = None,
        execution_policy: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> CapabilityPolicyDecision:
        violations: List[str] = []

        # 1. Resolve server-authoritative declaration
        declaration = capability_registry.get(capability_id)
        if not declaration:
            raise CapabilityExecutionError(
                code="UNKNOWN_CAPABILITY",
                message=f"Capability '{capability_id}' is not recognized in the CapabilityRegistry.",
                capability_id=capability_id,
            )

        # 2. Multi-Tenant isolation
        if tenant_id != plan_tenant_id:
            raise CapabilityExecutionError(
                code="TENANT_ISOLATION_VIOLATION",
                message="Tenant cannot execute capability on foreign tenant plan.",
                capability_id=capability_id,
            )

        # 3. Check Cognitive Execution Allowed
        if not declaration.cognitive_execution_allowed:
            raise CapabilityExecutionError(
                code="COGNITIVE_CAPABILITY_NOT_ALLOWED",
                message=f"Autonomous cognitive execution is prohibited for capability '{capability_id}'. It requires human initiation.",
                capability_id=capability_id,
            )

        # 4. Check Human Gate Requirement
        if declaration.human_gate_required:
            raise CapabilityExecutionError(
                code="COGNITIVE_CAPABILITY_NOT_ALLOWED",
                message=f"Capability '{capability_id}' is human-gated and cannot be invoked autonomously.",
                capability_id=capability_id,
            )

        # 5. Strict Read-Only Non-Mutation Policy (Phase 2 Wave 1 / 1.1)
        if declaration.mutates_state:
            raise CapabilityExecutionError(
                code="COGNITIVE_CAPABILITY_NOT_ALLOWED",
                message=f"Capability '{capability_id}' declares state mutation. Cognitive executor operates in read-only mode.",
                capability_id=capability_id,
            )

        # 6. Check Active Status
        if declaration.status != "ACTIVE":
            raise CapabilityExecutionError(
                code="CAPABILITY_INACTIVE",
                message=f"Capability '{capability_id}' is currently {declaration.status}.",
                capability_id=capability_id,
            )

        # 7. Check Required Permissions
        if actor_permissions is not None:
            for perm in declaration.required_permissions:
                if perm not in actor_permissions and "*:*" not in actor_permissions:
                    raise CapabilityExecutionError(
                        code="INSUFFICIENT_PERMISSIONS",
                        message=f"Actor lacks required permission '{perm}' for capability '{capability_id}'.",
                        capability_id=capability_id,
                    )

        return CapabilityPolicyDecision(
            allowed=True,
            capability_id=capability_id,
            capability=declaration,
            violations=[],
        )
