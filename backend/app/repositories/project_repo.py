from datetime import datetime, timezone
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.db.project import Project
from app.models.schemas.project import ProjectCreate, ProjectUpdate


class ProjectRepository:
    """Data access repository for Project entities with multi-tenant and soft-delete isolation."""

    async def get_by_id(
        self,
        db: AsyncSession,
        project_id: str,
        owner_id: str | None = None,
        tenant_id: str | None = None,
        allow_unscoped: bool = False,
    ) -> Project | None:
        stmt = select(Project).where(
            Project.id == project_id,
            Project.deleted_at.is_(None),
        )
        if tenant_id:
            stmt = stmt.where(Project.tenant_id == tenant_id)
        elif owner_id:
            stmt = stmt.where(Project.tenant_id.is_(None), Project.owner_id == owner_id)
        elif allow_unscoped:
            pass
        else:
            return None

        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_projects(
        self,
        db: AsyncSession,
        owner_id: str,
        tenant_id: str | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[Project], int]:
        stmt = select(Project).where(Project.deleted_at.is_(None))
        count_stmt = select(func.count(Project.id)).where(Project.deleted_at.is_(None))

        if tenant_id:
            stmt = stmt.where(Project.tenant_id == tenant_id)
            count_stmt = count_stmt.where(Project.tenant_id == tenant_id)
        else:
            stmt = stmt.where(Project.tenant_id.is_(None), Project.owner_id == owner_id)
            count_stmt = count_stmt.where(Project.tenant_id.is_(None), Project.owner_id == owner_id)

        total = await db.scalar(count_stmt) or 0

        offset = max(0, (page - 1) * page_size)
        stmt = stmt.order_by(Project.created_at.desc()).offset(offset).limit(page_size)

        result = await db.execute(stmt)
        projects = list(result.scalars().all())
        return projects, total

    async def create(
        self,
        db: AsyncSession,
        project_in: ProjectCreate,
        owner_id: str,
        tenant_id: str | None = None,
    ) -> Project:
        project = Project(
            owner_id=owner_id,
            tenant_id=tenant_id,
            name=project_in.name,
            description=project_in.description,
            project_type=project_in.project_type.value,
            status=project_in.status.value,
            metadata_=project_in.metadata,
        )
        db.add(project)
        await db.commit()
        await db.refresh(project)
        return project

    async def update(
        self,
        db: AsyncSession,
        project: Project,
        update_in: ProjectUpdate,
    ) -> Project:
        if update_in.name is not None:
            project.name = update_in.name
        if update_in.description is not None:
            project.description = update_in.description
        if update_in.project_type is not None:
            project.project_type = update_in.project_type.value
        if update_in.status is not None:
            project.status = update_in.status.value
        if update_in.metadata is not None:
            project.metadata_ = update_in.metadata

        project.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(project)
        return project

    async def soft_delete(self, db: AsyncSession, project: Project) -> None:
        project.deleted_at = datetime.now(timezone.utc)
        await db.commit()


project_repo = ProjectRepository()
