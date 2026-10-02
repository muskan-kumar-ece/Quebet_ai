import pytest
from app.services.ai.model_router import model_router


@pytest.mark.asyncio
async def test_model_router_plan_defaults():
    """Verify default model resolution per subscription tier."""
    free_model = await model_router.get_model(plan="free", task_type="default")
    assert "deepseek" in free_model.lower()

    plus_model = await model_router.get_model(plan="plus", task_type="default")
    assert "gemini" in plus_model.lower() or "flash" in plus_model.lower()

    pro_model = await model_router.get_model(plan="pro", task_type="default")
    assert "claude" in pro_model.lower() or "sonnet" in pro_model.lower()


@pytest.mark.asyncio
async def test_model_router_user_preference():
    """Verify that user-selected preference is honored for Plus and Pro plans."""
    preferred = "openai/gpt-4o"

    # Free plan cannot override model
    free_res = await model_router.get_model(plan="free", user_preferred=preferred)
    assert free_res != preferred

    # Pro plan can override model
    pro_res = await model_router.get_model(plan="pro", user_preferred=preferred)
    assert pro_res == preferred
