from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.dependencies import AuthenticatedUser
from app.models.db.circuit import Circuit, CircuitValidationStatus
from app.models.schemas.circuit import (
    AssumptionResponse,
    CircuitCreate,
    CircuitDetailResponse,
    CircuitResponse,
    CircuitUpdate,
    ComponentCreate,
    ComponentResponse,
    ComponentUpdate,
    ConnectionCreate,
    ConnectionResponse,
    NetCreate,
    NetResponse,
    NetUpdate,
    SchematicObjectBatchUpdate,
    SchematicObjectResponse,
    SchematicObjectUpdate,
)
from app.repositories.circuit_repo import circuit_repo
from app.repositories.project_repo import project_repo
from app.services.ai.validators.base import StageResult, ValidationStatus
from app.services.ai.validators.circuit_validator import circuit_schema_validator


class CircuitService:
    """Business logic service managing circuit graphs, structural validation, and electrical integrity."""

    async def create_circuit(
        self,
        db: AsyncSession,
        project_id: str,
        circuit_in: CircuitCreate,
        current_user: AuthenticatedUser,
        request_id: str | None = None,
    ) -> CircuitDetailResponse:
        # 1. Verify project ownership/tenant access
        project = await project_repo.get_by_id(
            db=db,
            project_id=project_id,
            owner_id=current_user.id if not current_user.tenant_id else None,
            tenant_id=current_user.tenant_id,
        )
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Parent project not found or access denied",
            )

        # 2. Persist circuit with components, nets, connections, assumptions, and schematic models
        circuit = await circuit_repo.create(
            db=db,
            circuit_in=circuit_in,
            project_id=project_id,
            owner_id=current_user.id,
            tenant_id=current_user.tenant_id,
            source_request_id=request_id,
            created_source="USER",
            commit=False,
        )

        from app.services.audit_ledger_service import AuditLedgerService
        from app.models.db.audit_ledger import AuditEventType

        audit_service = AuditLedgerService(db)
        await audit_service.record_event(
            project_id=project_id,
            actor_id=current_user.id,
            actor_role=getattr(current_user, "role", "ENGINEER"),
            event_type=AuditEventType.CIRCUIT_CREATED,
            entity_type="CIRCUIT",
            entity_id=circuit.id,
            entity_revision=circuit.version,
            payload={
                "circuit_id": circuit.id,
                "project_id": project_id,
                "name": circuit.name,
                "version": circuit.version,
                "components_count": len(circuit_in.components),
                "nets_count": len(circuit_in.nets),
                "connections_count": len(circuit_in.connections),
                "source_request_id": request_id,
            },
            tenant_id=current_user.tenant_id,
            commit=False,
        )

        await db.commit()
        refreshed_circuit = await circuit_repo.get_by_id(db, circuit.id, tenant_id=current_user.tenant_id, owner_id=current_user.id)
        return self._build_detail_response(refreshed_circuit or circuit)

    async def get_circuit(
        self,
        db: AsyncSession,
        circuit_id: str,
        current_user: AuthenticatedUser,
    ) -> CircuitDetailResponse:
        circuit = await circuit_repo.get_by_id(
            db=db,
            circuit_id=circuit_id,
            tenant_id=current_user.tenant_id,
            owner_id=current_user.id,
        )
        if not circuit:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Circuit not found or unauthorized",
            )
        return self._build_detail_response(circuit)

    async def list_circuits_for_project(
        self,
        db: AsyncSession,
        project_id: str,
        current_user: AuthenticatedUser,
    ) -> list[CircuitResponse]:
        # Verify project access
        project = await project_repo.get_by_id(
            db=db,
            project_id=project_id,
            owner_id=current_user.id if not current_user.tenant_id else None,
            tenant_id=current_user.tenant_id,
        )
        if not project:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

        circuits = await circuit_repo.list_for_project(
            db=db,
            project_id=project_id,
            tenant_id=current_user.tenant_id,
            owner_id=current_user.id,
        )
        return [CircuitResponse.model_validate(c) for c in circuits]

    async def update_circuit(
        self,
        db: AsyncSession,
        circuit_id: str,
        update_in: CircuitUpdate,
        current_user: AuthenticatedUser,
    ) -> CircuitResponse:
        circuit = await circuit_repo.get_by_id(
            db=db,
            circuit_id=circuit_id,
            tenant_id=current_user.tenant_id,
            owner_id=current_user.id,
        )
        if not circuit:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Circuit not found")

        updated = await circuit_repo.update(db=db, circuit=circuit, update_in=update_in)
        return CircuitResponse.model_validate(updated)

    async def validate_circuit(
        self,
        db: AsyncSession,
        circuit_id: str,
        current_user: AuthenticatedUser,
    ) -> StageResult:
        circuit = await circuit_repo.get_by_id(
            db=db,
            circuit_id=circuit_id,
            tenant_id=current_user.tenant_id,
            owner_id=current_user.id,
        )
        if not circuit:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Circuit not found")

        # Prepare payload for deterministic schema validator
        payload = {
            "components": [
                {"id": c.id, "ref_des": c.ref_des, "component_type": c.component_type, "value": c.value}
                for c in circuit.components
            ],
            "nets": [{"id": n.id, "name": n.name} for n in circuit.nets],
            "connections": [
                {"component_id": conn.component_id, "pin_number": conn.pin_number, "net_id": conn.net_id}
                for conn in circuit.connections
            ],
        }

        stage_result = await circuit_schema_validator.validate(payload)

        # Update validation status on circuit entity
        new_status = CircuitValidationStatus.VALID if stage_result.status == ValidationStatus.PASSED else CircuitValidationStatus.INVALID
        await circuit_repo.update(
            db=db,
            circuit=circuit,
            update_in=CircuitUpdate(validation_status=new_status),
        )

        return stage_result

    async def add_component(
        self,
        db: AsyncSession,
        circuit_id: str,
        comp_in: ComponentCreate,
        current_user: AuthenticatedUser,
        pos_x: float = 100.0,
        pos_y: float = 100.0,
    ) -> ComponentResponse:
        circuit = await circuit_repo.get_by_id(db=db, circuit_id=circuit_id, tenant_id=current_user.tenant_id, owner_id=current_user.id)
        if not circuit:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Circuit not found")

        # RefDes uniqueness check
        for c in circuit.components:
            if c.ref_des.strip().upper() == comp_in.ref_des.strip().upper():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Duplicate reference designator '{comp_in.ref_des}' already exists in circuit.",
                )

        comp, schem = await circuit_repo.add_component(
            db=db, circuit_id=circuit_id, comp_in=comp_in, pos_x=pos_x, pos_y=pos_y, commit=False
        )

        from app.services.audit_ledger_service import AuditLedgerService
        from app.models.db.audit_ledger import AuditEventType

        audit_service = AuditLedgerService(db)
        await audit_service.record_event(
            project_id=circuit.project_id,
            actor_id=current_user.id,
            actor_role=getattr(current_user, "role", "ENGINEER"),
            event_type=AuditEventType.COMPONENT_ADDED,
            entity_type="COMPONENT",
            entity_id=comp.id,
            entity_revision=circuit.version,
            payload={
                "component_id": comp.id,
                "circuit_id": circuit.id,
                "ref_des": comp.ref_des,
                "component_type": comp.component_type,
                "value": comp.value,
                "package": comp.package,
            },
            tenant_id=current_user.tenant_id,
            commit=False,
        )

        await db.commit()
        await db.refresh(comp)
        await db.refresh(schem)
        return ComponentResponse.model_validate(comp)

    async def update_component(
        self,
        db: AsyncSession,
        component_id: str,
        update_in: ComponentUpdate,
        current_user: AuthenticatedUser,
    ) -> ComponentResponse:
        comp = await circuit_repo.get_component(db=db, component_id=component_id)
        if not comp:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Component not found")

        # Check circuit ownership
        circuit = await circuit_repo.get_by_id(db=db, circuit_id=comp.circuit_id, tenant_id=current_user.tenant_id, owner_id=current_user.id)
        if not circuit:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Circuit not found or unauthorized")

        # If renaming ref_des, check uniqueness
        if update_in.ref_des and update_in.ref_des.strip().upper() != comp.ref_des.strip().upper():
            for c in circuit.components:
                if c.id != comp.id and c.ref_des.strip().upper() == update_in.ref_des.strip().upper():
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Duplicate reference designator '{update_in.ref_des}' already in use.",
                    )

        updated = await circuit_repo.update_component(db=db, component=comp, update_in=update_in, commit=False)

        from app.services.audit_ledger_service import AuditLedgerService
        from app.models.db.audit_ledger import AuditEventType

        audit_service = AuditLedgerService(db)
        await audit_service.record_event(
            project_id=circuit.project_id,
            actor_id=current_user.id,
            actor_role=getattr(current_user, "role", "ENGINEER"),
            event_type=AuditEventType.COMPONENT_UPDATED,
            entity_type="COMPONENT",
            entity_id=updated.id,
            entity_revision=circuit.version,
            payload={
                "component_id": updated.id,
                "circuit_id": circuit.id,
                "ref_des": updated.ref_des,
                "component_type": updated.component_type,
                "value": updated.value,
                "package": updated.package,
            },
            tenant_id=current_user.tenant_id,
            commit=False,
        )

        await db.commit()
        await db.refresh(updated)
        return ComponentResponse.model_validate(updated)

    async def delete_component(
        self,
        db: AsyncSession,
        component_id: str,
        current_user: AuthenticatedUser,
    ) -> None:
        comp = await circuit_repo.get_component(db=db, component_id=component_id)
        if not comp:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Component not found")

        circuit = await circuit_repo.get_by_id(db=db, circuit_id=comp.circuit_id, tenant_id=current_user.tenant_id, owner_id=current_user.id)
        if not circuit:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Circuit not found or unauthorized")

        from app.services.audit_ledger_service import AuditLedgerService
        from app.models.db.audit_ledger import AuditEventType

        audit_service = AuditLedgerService(db)
        await audit_service.record_event(
            project_id=circuit.project_id,
            actor_id=current_user.id,
            actor_role=getattr(current_user, "role", "ENGINEER"),
            event_type=AuditEventType.COMPONENT_DELETED,
            entity_type="COMPONENT",
            entity_id=comp.id,
            entity_revision=circuit.version,
            payload={
                "component_id": comp.id,
                "circuit_id": circuit.id,
                "ref_des": comp.ref_des,
            },
            tenant_id=current_user.tenant_id,
            commit=False,
        )

        await circuit_repo.delete_component(db=db, component=comp, commit=False)
        await db.commit()

    async def add_net(
        self,
        db: AsyncSession,
        circuit_id: str,
        net_in: NetCreate,
        current_user: AuthenticatedUser,
    ) -> NetResponse:
        circuit = await circuit_repo.get_by_id(db=db, circuit_id=circuit_id, tenant_id=current_user.tenant_id, owner_id=current_user.id)
        if not circuit:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Circuit not found")

        # Check if net name already exists
        for n in circuit.nets:
            if n.name.strip().upper() == net_in.name.strip().upper():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Net with name '{net_in.name}' already exists in circuit.",
                )

        net = await circuit_repo.add_net(db=db, circuit_id=circuit_id, net_in=net_in, commit=False)

        from app.services.audit_ledger_service import AuditLedgerService
        from app.models.db.audit_ledger import AuditEventType

        audit_service = AuditLedgerService(db)
        await audit_service.record_event(
            project_id=circuit.project_id,
            actor_id=current_user.id,
            actor_role=getattr(current_user, "role", "ENGINEER"),
            event_type=AuditEventType.NET_MUTATED,
            entity_type="NET",
            entity_id=net.id,
            entity_revision=circuit.version,
            payload={
                "action": "ADD_NET",
                "net_id": net.id,
                "circuit_id": circuit.id,
                "name": net.name,
                "net_type": net.net_type,
            },
            tenant_id=current_user.tenant_id,
            commit=False,
        )

        await db.commit()
        await db.refresh(net)
        return NetResponse.model_validate(net)

    async def update_net(
        self,
        db: AsyncSession,
        net_id: str,
        update_in: NetUpdate,
        current_user: AuthenticatedUser,
    ) -> NetResponse:
        net = await circuit_repo.get_net(db=db, net_id=net_id)
        if not net:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Net not found")

        circuit = await circuit_repo.get_by_id(db=db, circuit_id=net.circuit_id, tenant_id=current_user.tenant_id, owner_id=current_user.id)
        if not circuit:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Circuit not found or unauthorized")

        if update_in.name and update_in.name.strip().upper() != net.name.strip().upper():
            for n in circuit.nets:
                if n.id != net.id and n.name.strip().upper() == update_in.name.strip().upper():
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Duplicate net name '{update_in.name}' already in use.",
                    )

        updated = await circuit_repo.update_net(db=db, net=net, update_in=update_in, commit=False)

        from app.services.audit_ledger_service import AuditLedgerService
        from app.models.db.audit_ledger import AuditEventType

        audit_service = AuditLedgerService(db)
        await audit_service.record_event(
            project_id=circuit.project_id,
            actor_id=current_user.id,
            actor_role=getattr(current_user, "role", "ENGINEER"),
            event_type=AuditEventType.NET_MUTATED,
            entity_type="NET",
            entity_id=updated.id,
            entity_revision=circuit.version,
            payload={
                "action": "UPDATE_NET",
                "net_id": updated.id,
                "circuit_id": circuit.id,
                "name": updated.name,
                "net_type": updated.net_type,
            },
            tenant_id=current_user.tenant_id,
            commit=False,
        )

        await db.commit()
        await db.refresh(updated)
        return NetResponse.model_validate(updated)

    async def delete_net(
        self,
        db: AsyncSession,
        net_id: str,
        current_user: AuthenticatedUser,
    ) -> None:
        net = await circuit_repo.get_net(db=db, net_id=net_id)
        if not net:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Net not found")

        circuit = await circuit_repo.get_by_id(db=db, circuit_id=net.circuit_id, tenant_id=current_user.tenant_id, owner_id=current_user.id)
        if not circuit:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Circuit not found or unauthorized")

        from app.services.audit_ledger_service import AuditLedgerService
        from app.models.db.audit_ledger import AuditEventType

        audit_service = AuditLedgerService(db)
        await audit_service.record_event(
            project_id=circuit.project_id,
            actor_id=current_user.id,
            actor_role=getattr(current_user, "role", "ENGINEER"),
            event_type=AuditEventType.NET_MUTATED,
            entity_type="NET",
            entity_id=net.id,
            entity_revision=circuit.version,
            payload={
                "action": "DELETE_NET",
                "net_id": net.id,
                "circuit_id": circuit.id,
                "name": net.name,
            },
            tenant_id=current_user.tenant_id,
            commit=False,
        )

        await circuit_repo.delete_net(db=db, net=net, commit=False)
        await db.commit()

    async def add_connection(
        self,
        db: AsyncSession,
        circuit_id: str,
        conn_in: ConnectionCreate,
        current_user: AuthenticatedUser,
    ) -> ConnectionResponse:
        circuit = await circuit_repo.get_by_id(db=db, circuit_id=circuit_id, tenant_id=current_user.tenant_id, owner_id=current_user.id)
        if not circuit:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Circuit not found")

        # 1. Verify component belongs to this circuit
        component = next((c for c in circuit.components if c.id == conn_in.component_id), None)
        if not component:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid component reference: component '{conn_in.component_id}' not found in circuit.",
            )

        # 2. Verify pin exists on component if component.pins is defined
        if component.pins:
            valid_pin_numbers = [str(p.get("pin_number")) for p in component.pins if isinstance(p, dict)]
            if valid_pin_numbers and str(conn_in.pin_number) not in valid_pin_numbers:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid pin reference: pin '{conn_in.pin_number}' does not exist on component '{component.ref_des}' (valid: {valid_pin_numbers}).",
                )

        # 3. Verify net belongs to this circuit
        net = next((n for n in circuit.nets if n.id == conn_in.net_id), None)
        if not net:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid net reference: net '{conn_in.net_id}' not found in circuit.",
            )

        # 4. Check for duplicate connection or conflicting pin mapping
        existing = await circuit_repo.get_existing_connection(
            db=db,
            circuit_id=circuit_id,
            component_id=conn_in.component_id,
            pin_number=conn_in.pin_number,
        )
        if existing:
            if existing.net_id == conn_in.net_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Duplicate connection: pin '{conn_in.pin_number}' on '{component.ref_des}' is already connected to net '{net.name}'.",
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Duplicate pin mapping: pin '{conn_in.pin_number}' on '{component.ref_des}' is already connected to another net.",
                )

        conn = await circuit_repo.add_connection(db=db, circuit_id=circuit_id, conn_in=conn_in, commit=False)

        from app.services.audit_ledger_service import AuditLedgerService
        from app.models.db.audit_ledger import AuditEventType

        audit_service = AuditLedgerService(db)
        await audit_service.record_event(
            project_id=circuit.project_id,
            actor_id=current_user.id,
            actor_role=getattr(current_user, "role", "ENGINEER"),
            event_type=AuditEventType.CONNECTION_MUTATED,
            entity_type="CONNECTION",
            entity_id=conn.id,
            entity_revision=circuit.version,
            payload={
                "action": "ADD_CONNECTION",
                "connection_id": conn.id,
                "circuit_id": circuit.id,
                "component_id": conn.component_id,
                "pin_number": conn.pin_number,
                "net_id": conn.net_id,
            },
            tenant_id=current_user.tenant_id,
            commit=False,
        )

        await db.commit()
        await db.refresh(conn)
        return ConnectionResponse.model_validate(conn)

    async def delete_connection(
        self,
        db: AsyncSession,
        connection_id: str,
        current_user: AuthenticatedUser,
    ) -> None:
        conn = await circuit_repo.get_connection(db=db, connection_id=connection_id)
        if not conn:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connection not found")

        circuit = await circuit_repo.get_by_id(db=db, circuit_id=conn.circuit_id, tenant_id=current_user.tenant_id, owner_id=current_user.id)
        if not circuit:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Circuit not found or unauthorized")

        from app.services.audit_ledger_service import AuditLedgerService
        from app.models.db.audit_ledger import AuditEventType

        audit_service = AuditLedgerService(db)
        await audit_service.record_event(
            project_id=circuit.project_id,
            actor_id=current_user.id,
            actor_role=getattr(current_user, "role", "ENGINEER"),
            event_type=AuditEventType.CONNECTION_MUTATED,
            entity_type="CONNECTION",
            entity_id=conn.id,
            entity_revision=circuit.version,
            payload={
                "action": "DELETE_CONNECTION",
                "connection_id": conn.id,
                "circuit_id": circuit.id,
                "component_id": conn.component_id,
                "pin_number": conn.pin_number,
                "net_id": conn.net_id,
            },
            tenant_id=current_user.tenant_id,
            commit=False,
        )

        await circuit_repo.delete_connection(db=db, connection=conn, commit=False)
        await db.commit()

    async def update_schematic_object(
        self,
        db: AsyncSession,
        obj_id: str,
        update_in: SchematicObjectUpdate,
        current_user: AuthenticatedUser,
    ) -> SchematicObjectResponse:
        obj = await circuit_repo.get_schematic_object(db=db, obj_id=obj_id)
        if not obj:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Schematic object not found")

        circuit = await circuit_repo.get_by_id(db=db, circuit_id=obj.circuit_id, tenant_id=current_user.tenant_id, owner_id=current_user.id)
        if not circuit:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Circuit not found or unauthorized")

        updated = await circuit_repo.update_schematic_object(db=db, obj=obj, update_in=update_in)
        return SchematicObjectResponse.model_validate(updated)

    async def batch_update_schematic_objects(
        self,
        db: AsyncSession,
        circuit_id: str,
        batch_in: SchematicObjectBatchUpdate,
        current_user: AuthenticatedUser,
    ) -> list[SchematicObjectResponse]:
        circuit = await circuit_repo.get_by_id(db=db, circuit_id=circuit_id, tenant_id=current_user.tenant_id, owner_id=current_user.id)
        if not circuit:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Circuit not found or unauthorized")

        updated = await circuit_repo.batch_update_schematic_objects(db=db, circuit_id=circuit_id, items=batch_in.items)
        return [SchematicObjectResponse.model_validate(o) for o in updated]

    async def export_circuit_json(
        self,
        db: AsyncSession,
        circuit_id: str,
        current_user: AuthenticatedUser,
    ) -> dict:
        circuit = await self.get_circuit(db=db, circuit_id=circuit_id, current_user=current_user)
        return {
            "format": "quebet_circuit_v1",
            "circuit": circuit.model_dump(),
        }

    def _build_detail_response(self, circuit: Circuit) -> CircuitDetailResponse:
        return CircuitDetailResponse(
            id=circuit.id,
            project_id=circuit.project_id,
            tenant_id=circuit.tenant_id,
            name=circuit.name,
            description=circuit.description,
            version=circuit.version,
            validation_status=circuit.validation_status,
            created_by=circuit.created_by,
            created_source=circuit.created_source,
            source_request_id=circuit.source_request_id,
            metadata=circuit.metadata_ or {},
            components=[ComponentResponse.model_validate(c) for c in circuit.components],
            nets=[NetResponse.model_validate(n) for n in circuit.nets],
            connections=[ConnectionResponse.model_validate(conn) for conn in circuit.connections],
            schematic_objects=[SchematicObjectResponse.model_validate(so) for so in circuit.schematic_objects],
            assumptions=[AssumptionResponse.model_validate(a) for a in circuit.assumptions],
            created_at=circuit.created_at,
            updated_at=circuit.updated_at,
        )


circuit_service = CircuitService()
