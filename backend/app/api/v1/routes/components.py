from typing import Any
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.dependencies import AuthenticatedUser, require_authenticated_user
from app.models.schemas.circuit import ComponentResponse, ComponentUpdate
from app.models.schemas.common import ApiResponse
from app.services.circuit_service import circuit_service
from app.services.component_knowledge_service import component_knowledge_service

router = APIRouter(prefix="/components", tags=["Component Knowledge Base & Management"])


@router.get("/search", response_model=ApiResponse[list[dict[str, Any]]])
async def search_components(
    q: str = Query(..., min_length=1, description="Search query e.g. LM7805, ESP32, 10k"),
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
):
    """Search validated electronics components and IC specifications from knowledge base."""
    results = component_knowledge_service.search_components(q)
    return ApiResponse(success=True, data=results)


@router.get("/standards/resistors", response_model=ApiResponse[dict[str, Any]])
async def get_resistor_standards(
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
):
    """Retrieve E12/E24 base series and SMD packaging power ratings."""
    data = component_knowledge_service.get_resistors()
    return ApiResponse(success=True, data=data)


@router.get("/standards/capacitors", response_model=ApiResponse[dict[str, Any]])
async def get_capacitor_guidelines(
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
):
    """Retrieve capacitor dielectric types, voltage derating rules, and decoupling defaults."""
    data = component_knowledge_service.get_capacitors()
    return ApiResponse(success=True, data=data)


@router.patch("/{component_id}", response_model=ApiResponse[ComponentResponse])
async def update_component(
    component_id: str,
    update_in: ComponentUpdate,
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    """Update component values, tolerances, package, or manufacturer details."""
    updated = await circuit_service.update_component(
        db=db,
        component_id=component_id,
        update_in=update_in,
        current_user=current_user,
    )
    return ApiResponse(success=True, data=updated)


@router.delete("/{component_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_component(
    component_id: str,
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a component and cascade deletion to its associated connections."""
    await circuit_service.delete_component(
        db=db,
        component_id=component_id,
        current_user=current_user,
    )
    return None
