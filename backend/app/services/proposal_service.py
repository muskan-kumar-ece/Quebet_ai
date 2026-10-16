from datetime import datetime, timezone
from typing import Any
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.dependencies import AuthenticatedUser
from app.models.db.component import Component
from app.models.db.connection import Connection
from app.models.db.net import Net
from app.models.db.proposal import EngineeringProposal, ProposalStatus
from app.models.schemas.circuit import (
    ComponentCreate,
    ComponentUpdate,
    ConnectionCreate,
    NetCreate,
    NetUpdate,
)
from app.models.schemas.proposal import ProposalCreate, ProposalResponse
from app.repositories.circuit_repo import circuit_repo
from app.repositories.proposal_repo import proposal_repo
from app.services.ai.validators.base import StageResult, ValidationErrorItem, ValidationStage, ValidationStatus


class ProposalService:
    """
    Manages Engineering Proposals.
    Enforces the core rule: AI and drafts never directly mutate the circuit database.
    Proposals must be validated, reviewed, and approved before being applied.
    Enforces stale proposal protection and post-apply automatic deterministic re-analysis.
    """

    async def create_proposal(
        self,
        db: AsyncSession,
        circuit_id: str,
        proposal_in: ProposalCreate,
        current_user: AuthenticatedUser,
    ) -> ProposalResponse:
        circuit = await circuit_repo.get_by_id(db=db, circuit_id=circuit_id, tenant_id=current_user.tenant_id, owner_id=current_user.id)
        if not circuit:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Circuit not found")

        # Automatically tie to current circuit version if base_revision is default or unspecified
        if not proposal_in.base_revision:
            proposal_in.base_revision = circuit.version

        proposal = await proposal_repo.create(
            db=db,
            circuit_id=circuit_id,
            proposal_in=proposal_in,
            user_id=current_user.id,
            tenant_id=current_user.tenant_id,
        )
        return ProposalResponse.model_validate(proposal)

    async def list_proposals(
        self,
        db: AsyncSession,
        circuit_id: str,
        current_user: AuthenticatedUser,
    ) -> list[ProposalResponse]:
        circuit = await circuit_repo.get_by_id(db=db, circuit_id=circuit_id, tenant_id=current_user.tenant_id, owner_id=current_user.id)
        if not circuit:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Circuit not found")

        proposals = await proposal_repo.list_for_circuit(db=db, circuit_id=circuit_id, tenant_id=current_user.tenant_id, owner_id=current_user.id)
        return [ProposalResponse.model_validate(p) for p in proposals]

    async def get_proposal(
        self,
        db: AsyncSession,
        proposal_id: str,
        current_user: AuthenticatedUser,
    ) -> ProposalResponse:
        proposal = await proposal_repo.get_by_id(db=db, proposal_id=proposal_id, tenant_id=current_user.tenant_id, owner_id=current_user.id)
        if not proposal:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proposal not found")
        return ProposalResponse.model_validate(proposal)

    async def validate_proposal(
        self,
        db: AsyncSession,
        proposal_id: str,
        current_user: AuthenticatedUser,
    ) -> ProposalResponse:
        proposal = await proposal_repo.get_by_id(db=db, proposal_id=proposal_id, tenant_id=current_user.tenant_id, owner_id=current_user.id)
        if not proposal:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proposal not found")

        circuit = await circuit_repo.get_by_id(db=db, circuit_id=proposal.circuit_id, tenant_id=current_user.tenant_id, owner_id=current_user.id)
        if not circuit:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Circuit not found")

        # Stale Check: Base revision must match current circuit revision
        if proposal.base_revision != circuit.version:
            updated = await proposal_repo.update_status(
                db=db,
                proposal=proposal,
                status=ProposalStatus.STALE,
            )
            return ProposalResponse.model_validate(updated)

        # Simulate applying operations in memory
        sim_components = {c.ref_des.upper(): {"ref_des": c.ref_des, "value": c.value, "pins": c.pins} for c in circuit.components}
        sim_nets = {n.name.upper(): n.name for n in circuit.nets}
        errors: list[ValidationErrorItem] = []

        for idx, op in enumerate(proposal.operations):
            op_type = op.get("op_type", "").lower()
            payload = op.get("payload", {})

            if op_type == "add_component":
                ref_des = payload.get("ref_des")
                if not ref_des:
                    errors.append(ValidationErrorItem(
                        code="MISSING_REF_DES",
                        message=f"Operation {idx}: add_component requires ref_des",
                        field_path=f"operations[{idx}].payload.ref_des",
                    ))
                elif ref_des.upper() in sim_components:
                    errors.append(ValidationErrorItem(
                        code="DUPLICATE_REF_DES",
                        message=f"Operation {idx}: ref_des '{ref_des}' already exists in circuit or proposal",
                        field_path=f"operations[{idx}].payload.ref_des",
                    ))
                else:
                    sim_components[ref_des.upper()] = {"ref_des": ref_des, "value": payload.get("value", ""), "pins": payload.get("pins", [])}

            elif op_type in ["update_component", "update_component_value", "replace_component"]:
                ref_des = payload.get("ref_des")
                c_id = payload.get("component_id")
                found = False
                if ref_des and ref_des.upper() in sim_components:
                    found = True
                elif c_id and any(c.id == c_id for c in circuit.components):
                    found = True
                if not found:
                    errors.append(ValidationErrorItem(
                        code="COMPONENT_NOT_FOUND",
                        message=f"Operation {idx}: target component for update does not exist",
                        field_path=f"operations[{idx}].payload",
                    ))

            elif op_type == "add_net":
                name = payload.get("name")
                if not name:
                    errors.append(ValidationErrorItem(
                        code="MISSING_NET_NAME",
                        message=f"Operation {idx}: add_net requires net name",
                        field_path=f"operations[{idx}].payload.name",
                    ))
                else:
                    sim_nets[name.upper()] = name

            elif op_type == "add_connection":
                ref = payload.get("ref_des") or payload.get("component_ref")
                net = payload.get("net_name")
                if ref and ref.upper() not in sim_components:
                    errors.append(ValidationErrorItem(
                        code="INVALID_COMPONENT_REFERENCE",
                        message=f"Operation {idx}: referenced component '{ref}' does not exist in circuit or proposal",
                        field_path=f"operations[{idx}].payload.ref_des",
                    ))
                if net and net.upper() not in sim_nets:
                    errors.append(ValidationErrorItem(
                        code="INVALID_NET_REFERENCE",
                        message=f"Operation {idx}: referenced net '{net}' does not exist in circuit or proposal",
                        field_path=f"operations[{idx}].payload.net_name",
                    ))

        status_result = ValidationStatus.PASSED if not errors else ValidationStatus.FAILED
        stage_result = StageResult(
            stage=ValidationStage.STAGE_1_SCHEMA,
            status=status_result,
            errors=errors,
            warnings=[],
            execution_time_ms=5.0,
            metadata={"simulated_components_count": len(sim_components), "simulated_nets_count": len(sim_nets)},
        )

        new_status = ProposalStatus.VALIDATED if status_result == ValidationStatus.PASSED else ProposalStatus.REJECTED
        updated = await proposal_repo.update_status(
            db=db,
            proposal=proposal,
            status=new_status,
            validation_result=stage_result.model_dump(),
        )
        return ProposalResponse.model_validate(updated)

    async def approve_proposal(
        self,
        db: AsyncSession,
        proposal_id: str,
        current_user: AuthenticatedUser,
    ) -> ProposalResponse:
        # SEC-03: Non-negotiable defense-in-depth enforcement of human authority
        role_norm = (getattr(current_user, "role", "") or "").strip().lower()
        if any(sub in role_norm for sub in ("ai", "bot", "copilot", "assistant", "agent", "autonomous")):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Engineering mutation authorization denied: AI agents and non-human actors possess no engineering decision authority. (AI ENGINEERING AUTHORITY = NONE)",
            )
        from app.core.dependencies import AUTHORIZED_HUMAN_ROLES
        if role_norm not in {r.lower() for r in AUTHORIZED_HUMAN_ROLES}:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Engineering mutation authorization denied: role '{current_user.role}' is not an authorized human engineering role.",
            )

        proposal = await proposal_repo.get_by_id(db=db, proposal_id=proposal_id, tenant_id=current_user.tenant_id, owner_id=current_user.id)
        if not proposal:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proposal not found")

        circuit = await circuit_repo.get_by_id(db=db, circuit_id=proposal.circuit_id, tenant_id=current_user.tenant_id, owner_id=current_user.id)
        if not circuit:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Circuit not found")

        # Stale Check: Base revision must match current circuit revision
        if proposal.base_revision is not None and proposal.base_revision != circuit.version:
            await proposal_repo.update_status(
                db=db,
                proposal=proposal,
                status=ProposalStatus.STALE,
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "PROPOSAL_STALE",
                    "message": f"Proposal is STALE. Base revision ({proposal.base_revision}) does not match current circuit revision ({circuit.version}).",
                    "proposal_revision": proposal.base_revision,
                    "current_circuit_revision": circuit.version,
                    "reason": f"Circuit was modified from version {proposal.base_revision} to version {circuit.version} after proposal was created.",
                    "required_action": "Re-evaluate circuit and generate an updated proposal based on current revision.",
                },
            )

        if proposal.status == ProposalStatus.APPLIED.value:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Proposal is already applied")

        # Stage PROPOSAL_APPROVED audit event atomically
        from app.services.audit_ledger_service import AuditLedgerService
        from app.models.db.audit_ledger import AuditEventType

        audit_service = AuditLedgerService(db)
        await audit_service.record_event(
            project_id=circuit.project_id,
            actor_id=current_user.id,
            actor_role=getattr(current_user, "role", "ENGINEER"),
            event_type=AuditEventType.PROPOSAL_APPROVED,
            entity_type="ENGINEERING_PROPOSAL",
            entity_id=proposal.id,
            entity_revision=proposal.base_revision,
            payload={
                "proposal_id": proposal.id,
                "circuit_id": circuit.id,
                "base_revision": proposal.base_revision,
                "title": proposal.title,
                "operations_count": len(proposal.operations) if proposal.operations else 0,
            },
            tenant_id=current_user.tenant_id,
            commit=False,
        )

        updated = await proposal_repo.update_status(
            db=db,
            proposal=proposal,
            status=ProposalStatus.APPROVED,
            commit=True,
        )
        return ProposalResponse.model_validate(updated)

    async def apply_proposal(
        self,
        db: AsyncSession,
        proposal_id: str,
        current_user: AuthenticatedUser,
    ) -> ProposalResponse:
        # SEC-03: Non-negotiable defense-in-depth enforcement of human authority
        role_norm = (getattr(current_user, "role", "") or "").strip().lower()
        if any(sub in role_norm for sub in ("ai", "bot", "copilot", "assistant", "agent", "autonomous")):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Engineering mutation authorization denied: AI agents and non-human actors possess no engineering decision authority. (AI ENGINEERING AUTHORITY = NONE)",
            )
        from app.core.dependencies import AUTHORIZED_HUMAN_ROLES
        if role_norm not in {r.lower() for r in AUTHORIZED_HUMAN_ROLES}:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Engineering mutation authorization denied: role '{current_user.role}' is not an authorized human engineering role.",
            )

        proposal = await proposal_repo.get_by_id(db=db, proposal_id=proposal_id, tenant_id=current_user.tenant_id, owner_id=current_user.id)
        if not proposal:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proposal not found")

        if proposal.status != ProposalStatus.APPROVED.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Proposal must be APPROVED before applying. Current status is {proposal.status}.",
            )

        circuit = await circuit_repo.get_by_id(db=db, circuit_id=proposal.circuit_id, tenant_id=current_user.tenant_id, owner_id=current_user.id)
        if not circuit:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Circuit not found")

        # Stale Proposal Protection: Base revision must strictly match current circuit revision
        if proposal.base_revision is not None and proposal.base_revision != circuit.version:
            await proposal_repo.update_status(
                db=db,
                proposal=proposal,
                status=ProposalStatus.STALE,
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "PROPOSAL_STALE",
                    "message": f"Proposal is STALE. Base revision ({proposal.base_revision}) does not match current circuit revision ({circuit.version}). Cannot apply stale proposal.",
                    "proposal_revision": proposal.base_revision,
                    "current_circuit_revision": circuit.version,
                    "reason": f"Circuit was modified from version {proposal.base_revision} to version {circuit.version} after proposal was created.",
                    "required_action": "Re-evaluate circuit and generate an updated proposal based on current revision.",
                },
            )

        # Apply operations inside atomic transaction
        try:
            component_cache: dict[str, str] = {c.ref_des.upper(): c.id for c in circuit.components}
            comp_obj_cache: dict[str, Component] = {c.id: c for c in circuit.components}
            net_cache: dict[str, str] = {n.name.upper(): n.id for n in circuit.nets}

            for op in proposal.operations:
                op_type = op.get("op_type", "").lower()
                payload = op.get("payload", {})

                if op_type == "add_component":
                    ref_des = payload.get("ref_des")
                    comp_type = payload.get("component_type", "generic")
                    value = payload.get("value", "")
                    pos_x = float(payload.get("pos_x", 120.0))
                    pos_y = float(payload.get("pos_y", 120.0))
                    pins = payload.get("pins", [])
                    package = payload.get("package")

                    comp, _ = await circuit_repo.add_component(
                        db=db,
                        circuit_id=circuit.id,
                        comp_in=ComponentCreate(
                            ref_des=ref_des,
                            component_type=comp_type,
                            value=value,
                            pins=pins,
                            package=package,
                            created_source="AI_PROPOSAL",
                        ),
                        pos_x=pos_x,
                        pos_y=pos_y,
                        commit=False,
                    )
                    component_cache[ref_des.upper()] = comp.id
                    comp_obj_cache[comp.id] = comp

                elif op_type in ["update_component", "update_component_value", "update_component_rating", "replace_component"]:
                    comp_id = payload.get("component_id") or component_cache.get((payload.get("ref_des") or "").upper())
                    if comp_id and comp_id in comp_obj_cache:
                        comp = comp_obj_cache[comp_id]
                        update_kwargs: dict[str, Any] = {}
                        if payload.get("value"):
                            update_kwargs["value"] = payload.get("value")
                        if payload.get("package"):
                            update_kwargs["package"] = payload.get("package")
                        if payload.get("properties"):
                            meta = dict(comp.metadata_ or {})
                            meta.update(payload.get("properties"))
                            update_kwargs["metadata"] = meta
                        if payload.get("new_value"):
                            update_kwargs["value"] = str(payload.get("new_value"))

                        await circuit_repo.update_component(
                            db=db,
                            component=comp,
                            update_in=ComponentUpdate(**update_kwargs),
                            commit=False,
                        )
                    elif payload.get("must_exist", False):
                        raise ValueError(f"Target component for update not found: {payload.get('ref_des') or comp_id}")

                elif op_type == "remove_component":
                    comp_id = payload.get("component_id") or component_cache.get((payload.get("ref_des") or "").upper())
                    if comp_id and comp_id in comp_obj_cache:
                        await circuit_repo.delete_component(db=db, component=comp_obj_cache[comp_id], commit=False)

                elif op_type == "add_net":
                    name = payload.get("name")
                    net_type = payload.get("net_type", "signal")
                    if name.upper() not in net_cache:
                        net = await circuit_repo.add_net(
                            db=db,
                            circuit_id=circuit.id,
                            net_in=NetCreate(name=name, net_type=net_type),
                            commit=False,
                        )
                        net_cache[name.upper()] = net.id

                elif op_type == "add_connection":
                    comp_ref = payload.get("ref_des") or payload.get("component_ref")
                    comp_id = payload.get("component_id") or component_cache.get(comp_ref.upper() if comp_ref else "")
                    pin_number = str(payload.get("pin_number", ""))
                    net_name = payload.get("net_name")
                    net_id = payload.get("net_id") or net_cache.get(net_name.upper() if net_name else "")

                    if comp_id and net_id and pin_number:
                        existing = await circuit_repo.get_existing_connection(
                            db=db,
                            circuit_id=circuit.id,
                            component_id=comp_id,
                            pin_number=pin_number,
                        )
                        if not existing:
                            await circuit_repo.add_connection(
                                db=db,
                                circuit_id=circuit.id,
                                conn_in=ConnectionCreate(
                                    component_id=comp_id,
                                    pin_number=pin_number,
                                    net_id=net_id,
                                ),
                                commit=False,
                            )

                elif op_type == "remove_connection":
                    comp_id = payload.get("component_id") or component_cache.get((payload.get("ref_des") or "").upper())
                    pin_number = str(payload.get("pin_number", ""))
                    if comp_id and pin_number:
                        existing = await circuit_repo.get_existing_connection(
                            db=db,
                            circuit_id=circuit.id,
                            component_id=comp_id,
                            pin_number=pin_number,
                        )
                        if existing:
                            await circuit_repo.delete_connection(db=db, connection=existing, commit=False)

                elif op_type == "fail_simulation":
                    # Explicit error triggering for rollback testing
                    raise RuntimeError("Forced operation failure during atomic apply transaction")

            # Increment circuit version to produce explicit revision boundary
            circuit.version += 1
            circuit.updated_at = datetime.now(timezone.utc)

            # Update proposal state to APPLIED in the same transaction
            await proposal_repo.update_status(
                db=db,
                proposal=proposal,
                status=ProposalStatus.APPLIED,
                applied_at=datetime.now(timezone.utc),
                commit=False,
            )

            # Stage PROPOSAL_APPLIED audit event atomically
            from app.services.audit_ledger_service import AuditLedgerService
            from app.models.db.audit_ledger import AuditEventType

            audit_service = AuditLedgerService(db)
            await audit_service.record_event(
                project_id=circuit.project_id,
                actor_id=current_user.id,
                actor_role=getattr(current_user, "role", "ENGINEER"),
                event_type=AuditEventType.PROPOSAL_APPLIED,
                entity_type="ENGINEERING_PROPOSAL",
                entity_id=proposal.id,
                entity_revision=circuit.version,
                payload={
                    "proposal_id": proposal.id,
                    "circuit_id": circuit.id,
                    "base_revision": proposal.base_revision,
                    "resulting_circuit_revision": circuit.version,
                    "operations_applied": [op.get("type") if isinstance(op, dict) else getattr(op, "type", str(op)) for op in proposal.operations] if proposal.operations else [],
                },
                tenant_id=current_user.tenant_id,
                commit=False,
            )

            await db.commit()
            await db.refresh(proposal)
        except HTTPException:
            await db.rollback()
            raise
        except Exception as e:
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Atomic application failed and was rolled back: {str(e)}",
            )

        updated = proposal

        # Post-apply automatic deterministic re-analysis
        try:
            from app.services.analysis_service import analysis_service
            await analysis_service.run_analysis(db=db, circuit_id=circuit.id, current_user=current_user)
        except Exception:
            pass

        return ProposalResponse.model_validate(updated)


proposal_service = ProposalService()
