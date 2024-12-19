from contextlib import contextmanager
from types import ModuleType
from typing import Any, Mapping, Sequence, Type

import dagster as dg
import pytest
from dagster._core.definitions.module_loaders.object_list import ModuleScopedDagsterObjects
from dagster._record import record


def build_module_fake(name: str, objects: Mapping[str, Any]) -> ModuleType:
    module = ModuleType(name)
    for key, value in objects.items():
        setattr(module, key, value)
    return module


def asset_with_key(key: str) -> dg.AssetsDefinition:
    @dg.asset(key=key)
    def my_asset(): ...

    return my_asset


def schedule_with_name(name: str) -> dg.ScheduleDefinition:
    return dg.ScheduleDefinition(name=name, cron_schedule="* * * * *", target="*")


def sensor_with_name(name: str) -> dg.SensorDefinition:
    @dg.sensor(job_name="blah")
    def my_sensor():
        pass

    return my_sensor


def check_with_key(key: str, name: str) -> dg.AssetChecksDefinition:
    @dg.asset_check(asset=key, name=name)
    def my_check() -> dg.AssetCheckResult:
        raise Exception("ooops")

    return my_check


@contextmanager
def optional_pytest_raise(error_expected: bool, exception_cls: Type[Exception]):
    if error_expected:
        with pytest.raises(exception_cls):
            yield
    else:
        yield


@record
class ModuleScopeTestSpec:
    objects: Mapping[str, Any]
    error_expected: bool
    id_: str

    @staticmethod
    def as_parametrize_kwargs(seq: Sequence["ModuleScopeTestSpec"]) -> Mapping[str, Any]:
        return {
            "argnames": "objects,error_expected",
            "argvalues": [(spec.objects, spec.error_expected) for spec in seq],
            "ids": [spec.id_ for spec in seq],
        }


some_schedule = schedule_with_name("foo")
some_sensor = sensor_with_name("foo")
some_asset = asset_with_key("foo")
some_job = dg.define_asset_job(name="foo")
some_check = check_with_key("foo_key", "some_name")


MODULE_TEST_SPECS = [
    ModuleScopeTestSpec(
        objects={"foo": some_schedule}, error_expected=False, id_="single schedule"
    ),
    ModuleScopeTestSpec(
        objects={"foo": some_schedule, "bar": schedule_with_name("foo")},
        error_expected=True,
        id_="conflicting schedules",
    ),
    ModuleScopeTestSpec(
        objects={"foo": some_schedule, "bar": some_schedule},
        error_expected=False,
        id_="schedules multiple variables",
    ),
    ModuleScopeTestSpec(objects={"foo": some_sensor}, error_expected=False, id_="single sensor"),
    ModuleScopeTestSpec(
        objects={"foo": some_sensor, "bar": sensor_with_name("foo")},
        error_expected=True,
        id_="conflicting sensors",
    ),
    ModuleScopeTestSpec(
        objects={"foo": some_sensor, "bar": some_sensor},
        error_expected=False,
        id_="sensors multiple variables",
    ),
    ModuleScopeTestSpec(
        objects={"foo": some_asset},
        error_expected=False,
        id_="asset single variable",
    ),
    ModuleScopeTestSpec(
        objects={"foo": some_asset, "bar": asset_with_key("foo")},
        error_expected=True,
        id_="conflicting assets",
    ),
    ModuleScopeTestSpec(
        objects={"foo": some_asset, "bar": some_asset},
        error_expected=False,
        id_="assets multiple variables",
    ),
    ModuleScopeTestSpec(
        objects={"foo": some_job},
        error_expected=False,
        id_="single job",
    ),
    ModuleScopeTestSpec(
        objects={"foo": some_job, "bar": dg.define_asset_job("other_job")},
        error_expected=False,
        id_="conflicting jobs",
    ),
    ModuleScopeTestSpec(
        objects={"foo": some_job, "bar": some_job},
        error_expected=False,
        id_="job multiple variables",
    ),
    ModuleScopeTestSpec(
        objects={"foo": some_check},
        error_expected=False,
        id_="single job",
    ),
    # Currently, we do not perform any collision detection on asset checks. This is the behavior currently public in load_asset_checks_from_module.
    ModuleScopeTestSpec(
        objects={"foo": some_check, "bar": check_with_key("foo_key", "some_name")},
        error_expected=False,
        id_="conflicting checks",
    ),
    ModuleScopeTestSpec(
        objects={"foo": some_check, "bar": some_check},
        error_expected=False,
        id_="check multiple variables",
    ),
]


@pytest.mark.parametrize(**ModuleScopeTestSpec.as_parametrize_kwargs(MODULE_TEST_SPECS))
def test_collision_detection(objects: Mapping[str, Any], error_expected: bool) -> None:
    module_fake = build_module_fake("fake", objects)
    with optional_pytest_raise(
        error_expected=error_expected, exception_cls=dg.DagsterInvalidDefinitionError
    ):
        obj_list = ModuleScopedDagsterObjects.from_modules([module_fake]).get_object_list()
        obj_ids = {id(obj) for obj in objects.values()}
        assert len(obj_list.loaded_objects) == len(obj_ids)
