from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.models.db.assumption import Assumption
from app.models.db.circuit import Circuit
from app.models.db.component import Component
from app.models.db.connection import Connection
from app.models.db.net import Net
from app.models.db.schematic_object import SchematicObject
from app.models.schemas.circuit import (
    CircuitCreate,
    CircuitUpdate,
    ComponentCreate,
    ComponentUpdate,
    ConnectionCreate,
    NetCreate,
    NetUpdate,
    SchematicObjectBatchItem,
    SchematicObjectUpdate,
)


class CircuitRepository:
    """Data access repository for Circuit graphs with eager relationship loading and soft delete."""

    async def get_by_id(
        self,
        db: AsyncSession,
        circuit_id: str,
        tenant_id: str | None = None,
        owner_id: str | None = None,
        allow_unscoped: bool = False,
    ) -> Circuit | None:
        stmt = (
            select(Circuit)
            .where(Circuit.id == circuit_id, Circuit.deleted_at.is_(None))
            .options(
                selectinload(Circuit.components),
                selectinload(Circuit.nets),
                selectinload(Circuit.connections),
                selectinload(Circuit.schematic_objects),
                selectinload(Circuit.assumptions),
            )
        )
        if tenant_id:
            stmt = stmt.where(Circuit.tenant_id == tenant_id)
        elif owner_id:
            # Untenanted personal circuit: strictly must have NULL tenant_id and match owner_id
            stmt = stmt.where(Circuit.tenant_id.is_(None), Circuit.created_by == owner_id)
        elif allow_unscoped:
            pass
        else:
            # UNKNOWN OWNERSHIP = DENIED (Fail Closed)
            return None

        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_for_project(
        self,
        db: AsyncSession,
        project_id: str,
        tenant_id: str | None = None,
        owner_id: str | None = None,
        allow_unscoped: bool = False,
    ) -> list[Circuit]:
        stmt = (
            select(Circuit)
            .where(
                Circuit.project_id == project_id,
                Circuit.deleted_at.is_(None),
            )
            .order_by(Circuit.created_at.desc())
        )
        if tenant_id:
            stmt = stmt.where(Circuit.tenant_id == tenant_id)
        elif owner_id:
            stmt = stmt.where(Circuit.tenant_id.is_(None), Circuit.created_by == owner_id)
        elif allow_unscoped:
            pass
        else:
            return []

        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def create(
        self,
        db: AsyncSession,
        circuit_in: CircuitCreate,
        project_id: str,
        owner_id: str,
        tenant_id: str | None = None,
        source_request_id: str | None = None,
        created_source: str = "USER",
        commit: bool = True,
    ) -> Circuit:
        circuit = Circuit(
            project_id=project_id,
            tenant_id=tenant_id,
            name=circuit_in.name,
            description=circuit_in.description,
            created_by=owner_id,
            created_source=created_source,
            source_request_id=source_request_id,
            metadata_=circuit_in.metadata,
        )
        db.add(circuit)
        await db.flush()

        # Add Components
        comp_map: dict[str, Component] = {}
        for c in circuit_in.components:
            comp = Component(
                circuit_id=circuit.id,
                ref_des=c.ref_des,
                component_type=c.component_type,
                manufacturer=c.manufacturer,
                part_number=c.part_number,
                value=c.value,
                unit=c.unit,
                tolerance=c.tolerance,
                rating=c.rating,
                package=c.package,
                pins=c.pins,
                metadata_=c.metadata,
                created_source=c.created_source,
            )
            db.add(comp)
            comp_map[c.ref_des] = comp

        # Add Nets
        net_map: dict[str, Net] = {}
        for n in circuit_in.nets:
            net = Net(
                circuit_id=circuit.id,
                name=n.name,
                net_type=n.net_type,
                metadata_=n.metadata,
            )
            db.add(net)
            net_map[n.name] = net

        await db.flush()

        # Add Connections
        for conn in circuit_in.connections:
            connection = Connection(
                circuit_id=circuit.id,
                component_id=conn.component_id,
                pin_number=conn.pin_number,
                pin_name=conn.pin_name,
                net_id=conn.net_id,
            )
            db.add(connection)

        # Add Schematic Objects
        for so in circuit_in.schematic_objects:
            schem = SchematicObject(
                circuit_id=circuit.id,
                object_type=so.object_type,
                component_id=so.component_id,
                net_id=so.net_id,
                pos_x=so.pos_x,
                pos_y=so.pos_y,
                rotation=so.rotation,
                graphics=so.graphics,
            )
            db.add(schem)

        # Add Assumptions
        for a in circuit_in.assumptions:
            assumption = Assumption(
                circuit_id=circuit.id,
                field=a.field,
                value=a.value,
                unit=a.unit,
                source=a.source.value,
                confidence=a.confidence,
                user_confirmed=a.user_confirmed,
                rationale=a.rationale,
            )
            db.add(assumption)

        if commit:
            await db.commit()
            return await self.get_by_id(db, circuit.id, tenant_id=tenant_id, owner_id=owner_id) or circuit
        else:
            await db.flush()
            return circuit

    async def update(
        self,
        db: AsyncSession,
        circuit: Circuit,
        update_in: CircuitUpdate,
    ) -> Circuit:
        if update_in.name is not None:
            circuit.name = update_in.name
        if update_in.description is not None:
            circuit.description = update_in.description
        if update_in.version is not None:
            circuit.version = update_in.version
        if update_in.validation_status is not None:
            circuit.validation_status = update_in.validation_status.value
        if update_in.metadata is not None:
            circuit.metadata_ = update_in.metadata

        circuit.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(circuit)
        return circuit

    async def soft_delete(self, db: AsyncSession, circuit: Circuit) -> None:
        circuit.deleted_at = datetime.now(timezone.utc)
        await db.commit()

    # --- Component Operations ---

    async def add_component(
        self,
        db: AsyncSession,
        circuit_id: str,
        comp_in: ComponentCreate,
        pos_x: float = 100.0,
        pos_y: float = 100.0,
        commit: bool = True,
    ) -> tuple[Component, SchematicObject]:
        comp = Component(
            circuit_id=circuit_id,
            ref_des=comp_in.ref_des,
            component_type=comp_in.component_type,
            manufacturer=comp_in.manufacturer,
            part_number=comp_in.part_number,
            value=comp_in.value,
            unit=comp_in.unit,
            tolerance=comp_in.tolerance,
            rating=comp_in.rating,
            package=comp_in.package,
            pins=comp_in.pins,
            metadata_=comp_in.metadata,
            created_source=comp_in.created_source,
        )
        db.add(comp)
        await db.flush()

        # Create corresponding visual schematic object
        schem = SchematicObject(
            circuit_id=circuit_id,
            object_type="symbol",
            component_id=comp.id,
            pos_x=pos_x,
            pos_y=pos_y,
            rotation=0.0,
            graphics={"symbol": comp_in.component_type, "ref_des": comp_in.ref_des, "value": comp_in.value},
        )
        db.add(schem)
        if commit:
            await db.commit()
            await db.refresh(comp)
            await db.refresh(schem)
        else:
            await db.flush()
        return comp, schem

    async def get_component(self, db: AsyncSession, component_id: str) -> Component | None:
        stmt = select(Component).where(Component.id == component_id, Component.deleted_at.is_(None))
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def update_component(
        self,
        db: AsyncSession,
        component: Component,
        update_in: ComponentUpdate,
        commit: bool = True,
    ) -> Component:
        if update_in.ref_des is not None:
            component.ref_des = update_in.ref_des
        if update_in.component_type is not None:
            component.component_type = update_in.component_type
        if update_in.value is not None:
            component.value = update_in.value
        if update_in.unit is not None:
            component.unit = update_in.unit
        if update_in.tolerance is not None:
            component.tolerance = update_in.tolerance
        if update_in.rating is not None:
            component.rating = update_in.rating
        if update_in.package is not None:
            component.package = update_in.package
        if update_in.manufacturer is not None:
            component.manufacturer = update_in.manufacturer
        if update_in.part_number is not None:
            component.part_number = update_in.part_number
        if update_in.pins is not None:
            component.pins = update_in.pins
        if update_in.metadata is not None:
            component.metadata_ = update_in.metadata

        component.updated_at = datetime.now(timezone.utc)
        if commit:
            await db.commit()
            await db.refresh(component)
        else:
            await db.flush()
        return component

    async def delete_component(self, db: AsyncSession, component: Component, commit: bool = True) -> None:
        component.deleted_at = datetime.now(timezone.utc)
        # Also remove associated connections and schematic object
        await db.delete(component)
        if commit:
            await db.commit()
        else:
            await db.flush()

    # --- Net Operations ---

    async def add_net(self, db: AsyncSession, circuit_id: str, net_in: NetCreate, commit: bool = True) -> Net:
        net = Net(
            circuit_id=circuit_id,
            name=net_in.name,
            net_type=net_in.net_type,
            metadata_=net_in.metadata,
        )
        db.add(net)
        if commit:
            await db.commit()
            await db.refresh(net)
        else:
            await db.flush()
        return net

    async def get_net(self, db: AsyncSession, net_id: str) -> Net | None:
        stmt = select(Net).where(Net.id == net_id, Net.deleted_at.is_(None))
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def update_net(self, db: AsyncSession, net: Net, update_in: NetUpdate, commit: bool = True) -> Net:
        if update_in.name is not None:
            net.name = update_in.name
        if update_in.net_type is not None:
            net.net_type = update_in.net_type
        if update_in.metadata is not None:
            net.metadata_ = update_in.metadata

        net.updated_at = datetime.now(timezone.utc)
        if commit:
            await db.commit()
            await db.refresh(net)
        else:
            await db.flush()
        return net

    async def delete_net(self, db: AsyncSession, net: Net, commit: bool = True) -> None:
        await db.delete(net)
        if commit:
            await db.commit()
        else:
            await db.flush()

    # --- Connection Operations ---

    async def add_connection(
        self,
        db: AsyncSession,
        circuit_id: str,
        conn_in: ConnectionCreate,
        commit: bool = True,
    ) -> Connection:
        conn = Connection(
            circuit_id=circuit_id,
            component_id=conn_in.component_id,
            pin_number=conn_in.pin_number,
            pin_name=conn_in.pin_name,
            net_id=conn_in.net_id,
        )
        db.add(conn)
        if commit:
            await db.commit()
            await db.refresh(conn)
        else:
            await db.flush()
        return conn

    async def get_connection(self, db: AsyncSession, connection_id: str) -> Connection | None:
        stmt = select(Connection).where(Connection.id == connection_id, Connection.deleted_at.is_(None))
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_existing_connection(
        self,
        db: AsyncSession,
        circuit_id: str,
        component_id: str,
        pin_number: str,
    ) -> Connection | None:
        stmt = select(Connection).where(
            Connection.circuit_id == circuit_id,
            Connection.component_id == component_id,
            Connection.pin_number == pin_number,
            Connection.deleted_at.is_(None),
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def delete_connection(self, db: AsyncSession, connection: Connection, commit: bool = True) -> None:
        await db.delete(connection)
        if commit:
            await db.commit()
        else:
            await db.flush()

    # --- Schematic Object Operations ---

    async def get_schematic_object(self, db: AsyncSession, obj_id: str) -> SchematicObject | None:
        stmt = select(SchematicObject).where(SchematicObject.id == obj_id, SchematicObject.deleted_at.is_(None))
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def update_schematic_object(
        self,
        db: AsyncSession,
        obj: SchematicObject,
        update_in: SchematicObjectUpdate,
    ) -> SchematicObject:
        if update_in.pos_x is not None:
            obj.pos_x = update_in.pos_x
        if update_in.pos_y is not None:
            obj.pos_y = update_in.pos_y
        if update_in.rotation is not None:
            obj.rotation = update_in.rotation
        if update_in.graphics is not None:
            obj.graphics = update_in.graphics

        obj.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(obj)
        return obj

    async def batch_update_schematic_objects(
        self,
        db: AsyncSession,
        circuit_id: str,
        items: list[SchematicObjectBatchItem],
    ) -> list[SchematicObject]:
        updated_objects: list[SchematicObject] = []
        for item in items:
            stmt = select(SchematicObject).where(
                SchematicObject.id == item.id,
                SchematicObject.circuit_id == circuit_id,
                SchematicObject.deleted_at.is_(None),
            )
            result = await db.execute(stmt)
            obj = result.scalar_one_or_none()
            if obj:
                if item.pos_x is not None:
                    obj.pos_x = item.pos_x
                if item.pos_y is not None:
                    obj.pos_y = item.pos_y
                if item.rotation is not None:
                    obj.rotation = item.rotation
                if item.graphics is not None:
                    obj.graphics = item.graphics
                obj.updated_at = datetime.now(timezone.utc)
                updated_objects.append(obj)

        await db.commit()
        for obj in updated_objects:
            await db.refresh(obj)
        return updated_objects


circuit_repo = CircuitRepository()

