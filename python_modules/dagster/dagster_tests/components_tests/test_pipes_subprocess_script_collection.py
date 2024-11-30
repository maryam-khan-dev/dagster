from pathlib import Path

from dagster._components import (
    Component,
    ComponentInitContext,
    ComponentLoadContext,
    ComponentRegistry,
    build_defs_from_component_folder,
)
from dagster._components.impls.pipes_subprocess_script_collection import (
    PipesSubprocessScriptCollection,
)
from dagster._core.pipes.subprocess import PipesSubprocessClient

LOCATION_PATH = Path(__file__).parent / "code_locations" / "python_script_location"
init_context = ComponentInitContext(
    path=LOCATION_PATH / "scripts", registry=ComponentRegistry.empty()
)
init_context.registry.register(
    "pipes_subprocess_script_collection", PipesSubprocessScriptCollection
)


def _assert_assets(component: Component, expected_assets: int) -> None:
    defs = component.build_defs(ComponentLoadContext.for_test())
    assert len(defs.get_asset_graph().get_all_asset_keys()) == expected_assets
    result = defs.get_implicit_global_asset_job_def().execute_in_process()
    assert result.success


def test_python_native() -> None:
    component = PipesSubprocessScriptCollection(LOCATION_PATH / "scripts")
    _assert_assets(component, 3)


def test_python_params() -> None:
    component = PipesSubprocessScriptCollection.from_component_params(
        init_context=init_context,
        component_params={
            "script_one": {
                "assets": [
                    {"key": "a"},
                    {"key": "b", "deps": ["up1", "up2"]},
                ]
            },
            "script_three": {"assets": [{"key": "key_override"}]},
        },
    )
    _assert_assets(component, 6)


def test_load_from_path() -> None:
    components = init_context.load()
    assert len(components) == 1

    _assert_assets(components[0], 6)


def test_build_from_path() -> None:
    defs = build_defs_from_component_folder(
        path=LOCATION_PATH,
        resources={"pipes_client": PipesSubprocessClient()},
        registry=init_context.registry,
    )

    assert len(defs.get_asset_graph().get_all_asset_keys()) == 6
