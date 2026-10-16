from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.dependencies import AuthenticatedUser
from app.models.db.project import Project
from app.models.schemas.project import ProjectCreate, ProjectListResponse, ProjectResponse, ProjectUpdate
from app.repositories.project_repo import project_repo


class ProjectService:
    """Business logic service managing engineering workspace projects and tenant boundaries."""

    async def create_project(
        self,
        db: AsyncSession,
        project_in: ProjectCreate,
        current_user: AuthenticatedUser,
    ) -> ProjectResponse:
        project = await project_repo.create(
            db=db,
            project_in=project_in,
            owner_id=current_user.id,
            tenant_id=current_user.tenant_id,
        )
        return ProjectResponse.model_validate(project)

    async def get_project(
        self,
        db: AsyncSession,
        project_id: str,
        current_user: AuthenticatedUser,
    ) -> ProjectResponse:
        project = await project_repo.get_by_id(
            db=db,
            project_id=project_id,
            owner_id=current_user.id if not current_user.tenant_id else None,
            tenant_id=current_user.tenant_id,
        )
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found or access denied across tenant boundaries",
            )
        return ProjectResponse.model_validate(project)

    async def list_projects(
        self,
        db: AsyncSession,
        current_user: AuthenticatedUser,
        page: int = 1,
        page_size: int = 50,
    ) -> ProjectListResponse:
        projects, total = await project_repo.list_projects(
            db=db,
            owner_id=current_user.id,
            tenant_id=current_user.tenant_id,
            page=page,
            page_size=page_size,
        )
        return ProjectListResponse(
            projects=[ProjectResponse.model_validate(p) for p in projects],
            total=total,
            page=page,
            page_size=page_size,
        )

    async def update_project(
        self,
        db: AsyncSession,
        project_id: str,
        update_in: ProjectUpdate,
        current_user: AuthenticatedUser,
    ) -> ProjectResponse:
        project = await project_repo.get_by_id(
            db=db,
            project_id=project_id,
            owner_id=current_user.id if not current_user.tenant_id else None,
            tenant_id=current_user.tenant_id,
        )
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found or unauthorized",
            )
        updated = await project_repo.update(db=db, project=project, update_in=update_in)
        return ProjectResponse.model_validate(updated)

    async def delete_project(
        self,
        db: AsyncSession,
        project_id: str,
        current_user: AuthenticatedUser,
    ) -> None:
        project = await project_repo.get_by_id(
            db=db,
            project_id=project_id,
            owner_id=current_user.id if not current_user.tenant_id else None,
            tenant_id=current_user.tenant_id,
        )
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found or unauthorized",
            )
        await project_repo.soft_delete(db=db, project=project)


project_service = ProjectService()
