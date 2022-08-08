import pytest

from dagster import Field, op
from dagster._check import CheckError
from dagster._config import ConfigAnyInstance
from dagster._legacy import composite_solid


def test_solid_field_backcompat():
    @op
    def op_without_schema(_):
        pass

    field = op_without_schema.config_schema.as_field()
    assert field.config_type == ConfigAnyInstance
    assert not field.is_required

    @op(config_schema=Field(str))
    def op_with_schema(_):
        pass

    assert op_with_schema.config_schema.is_required is True
    assert op_with_schema.config_schema.default_provided is False
    assert op_with_schema.config_schema.description is None

    with pytest.raises(CheckError):
        op_with_schema.config_schema.default_value  # pylint: disable=pointless-statement

    with pytest.raises(CheckError):
        op_with_schema.config_schema.default_value_as_json_str  # pylint: disable=pointless-statement

    @op(config_schema=Field(int, default_value=4, description="foo"))
    def op_with_all_properties(_):
        pass

    assert op_with_all_properties.config_schema.is_required is False
    assert op_with_all_properties.config_schema.default_provided is True
    assert op_with_all_properties.config_schema.default_value == 4
    assert op_with_all_properties.config_schema.default_value_as_json_str == "4"
    assert op_with_all_properties.config_schema.description == "foo"


def test_composite_field_backwards_compat():
    @op
    def noop(_):
        pass

    @composite_solid
    def bare_composite():
        noop()

    assert bare_composite.config_schema is None

    @composite_solid(config_schema=int, config_fn=lambda _: 4)
    def composite_with_int():
        noop()

    assert composite_with_int.config_schema
    assert composite_with_int.config_schema.is_required is True
    assert composite_with_int.config_schema.default_provided is False

    with pytest.raises(CheckError):
        composite_with_int.config_schema.default_value  # pylint: disable=pointless-statement

    with pytest.raises(CheckError):
        composite_with_int.config_schema.default_value_as_json_str  # pylint: disable=pointless-statement

    @composite_solid(
        config_schema=Field(int, default_value=2, description="bar"),
        config_fn=lambda _: 4,
    )
    def composite_kitchen_sink():
        noop()

    assert composite_kitchen_sink.config_schema
    assert composite_kitchen_sink.config_schema.is_required is False
    assert composite_kitchen_sink.config_schema.default_provided is True
    assert composite_kitchen_sink.config_schema.default_value == 2
    assert composite_kitchen_sink.config_schema.default_value_as_json_str == "2"
    assert composite_kitchen_sink.config_schema.description == "bar"
