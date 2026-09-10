"""The tool surface is a contract with a language model, so it gets tested like one."""

import pytest
from acex_mcp.app import create_app

EXPECTED_TOOLS = {
    "find_nodes",
    "get_node",
    "find_assets",
    "list_sites",
    "list_regions",
    "get_desired_config",
    "get_observed_config",
    "get_running_config",
    "list_observed_configs",
    "diff_observed_configs",
    "get_config_drift",
    "get_neighbors",
}


@pytest.fixture(scope="module")
def app():
    return create_app()


async def _tools(app):
    return await app.get_tools()


async def test_expected_tools_present(app):
    assert set((await _tools(app)).keys()) == EXPECTED_TOOLS


async def test_every_tool_is_documented(app):
    """A tool without a description is invisible to a model — it has nothing to
    choose from but the name."""
    for name, tool in (await _tools(app)).items():
        assert tool.description, f"{name} has no description"
        assert len(tool.description) > 80, f"{name}'s description is too thin to pick it by"


async def test_arguments_defaulting_to_none_are_nullable(app):
    """`x: str = None` generates a schema saying a string is required, which
    tells the model the opposite of the truth. Only `x: str | None = None`
    produces a nullable schema."""
    for name, tool in (await _tools(app)).items():
        for arg, spec in tool.parameters.get("properties", {}).items():
            if "default" not in spec or spec["default"] is not None:
                continue
            allows_null = "null" in str(spec.get("type", "")) or any(
                sub.get("type") == "null" for sub in spec.get("anyOf", [])
            )
            assert allows_null, f"{name}.{arg} defaults to None but its schema is not nullable"


async def test_node_id_is_the_only_identifier(app):
    """Every per-node tool addresses nodes the same way, so the model never has
    to work out which of several ids a tool wants."""
    per_node = {
        "get_node",
        "get_desired_config",
        "get_observed_config",
        "get_running_config",
        "list_observed_configs",
        "diff_observed_configs",
        "get_config_drift",
        "get_neighbors",
    }
    tools = await _tools(app)
    for name in per_node:
        assert "node_id" in tools[name].parameters["properties"], f"{name} does not take node_id"


async def test_all_tools_declare_read_only(app):
    """v1 is read-only; a client should be able to see that without calling anything."""
    for name, tool in (await _tools(app)).items():
        assert tool.annotations is not None, f"{name} has no annotations"
        assert tool.annotations.readOnlyHint is True, f"{name} is not marked read-only"


async def test_resources_and_prompts_registered(app):
    resources = await app.get_resources()
    assert {"acex://glossary", "acex://entities", "acex://capabilities", "acex://now"} <= set(resources)
    prompts = await app.get_prompts()
    assert {"explain_config_change", "assess_config_risk", "assess_config_alignment"} <= set(prompts)
