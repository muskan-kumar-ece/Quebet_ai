from fastapi import APIRouter
from app.api.v1.routes import (
    admin,
    analysis,
    auth,
    circuits,
    components,
    connections,
    design,
    health,
    models_list,
    nets,
    projects,
    proposals,
    schematic_objects,
    verification,
    provenance,
    systems,
    system_design,
    requirements,
    decisions,
    design_reviews,
    cognitive,
    knowledge,
    simulation,
    pcb,
    bom,
    dfm,
    cross_domain,
    workspace,
    audit,
    release,
)

api_router = APIRouter()

api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(models_list.router)
api_router.include_router(projects.router)
api_router.include_router(circuits.router)
api_router.include_router(requirements.router)
api_router.include_router(decisions.router)
api_router.include_router(design_reviews.router)
api_router.include_router(systems.router)
api_router.include_router(system_design.router)
api_router.include_router(analysis.router)
api_router.include_router(design.router)
api_router.include_router(components.router)
api_router.include_router(nets.router)
api_router.include_router(connections.router)
api_router.include_router(schematic_objects.router)
api_router.include_router(proposals.router)
api_router.include_router(verification.router)
api_router.include_router(knowledge.router)
api_router.include_router(provenance.router)
api_router.include_router(cognitive.router)
api_router.include_router(simulation.router)
api_router.include_router(pcb.router)
api_router.include_router(bom.router)
api_router.include_router(dfm.router)
api_router.include_router(cross_domain.router)
api_router.include_router(workspace.router)
api_router.include_router(audit.router)
api_router.include_router(release.router)
api_router.include_router(admin.router)

