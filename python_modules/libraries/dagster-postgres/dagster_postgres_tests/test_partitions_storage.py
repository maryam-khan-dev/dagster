import pytest
from dagster import AssetKey, asset, materialize
from dagster._core.definitions.mutable_partitions_definition import MutablePartitionsDefinition
from dagster._core.errors import DagsterUnknownPartitionError, DagsterInvalidInvocationError
from dagster._core.test_utils import instance_for_test
from dagster_postgres.partitions_storage.partitions_storage import PostgresPartitionsStorage


class TestPartitionsStorage:
    __test__ = False

    @pytest.fixture(name="storage", params=[])
    def partitions_storage(self, request):
        with request.param() as s:
            yield s

    def test_add_partitions(self, storage):
        assert storage

        storage.add_partitions(partitions_def_name="foo", partition_keys=["foo", "bar", "baz"])
        assert set(storage.get_partitions("foo")) == {"foo", "bar", "baz"}

        # Test for idempotency
        storage.add_partitions(partitions_def_name="foo", partition_keys=["foo"])
        assert set(storage.get_partitions("foo")) == {"foo", "bar", "baz"}

        assert set(storage.get_partitions("baz")) == set()

    def test_delete_partitions(self, storage):
        assert storage

        storage.add_partitions(partitions_def_name="foo", partition_keys=["foo", "bar", "baz"])
        assert set(storage.get_partitions("foo")) == {"foo", "bar", "baz"}

        storage.delete_partition(partitions_def_name="foo", partition_key="foo")
        assert set(storage.get_partitions("foo")) == {"bar", "baz"}

        # Test for idempotency
        storage.delete_partition(partitions_def_name="foo", partition_key="foo")
        assert set(storage.get_partitions("foo")) == {"bar", "baz"}

        storage.delete_partition(partitions_def_name="bar", partition_key="foo")
        assert set(storage.get_partitions("baz")) == set()

    def test_has_partition(self, storage):
        assert storage

        storage.add_partitions(partitions_def_name="foo", partition_keys=["foo", "bar", "baz"])
        assert storage.has_partition(partitions_def_name="foo", partition_key="foo")
        assert not storage.has_partition(partitions_def_name="foo", partition_key="qux")
        assert not storage.has_partition(partitions_def_name="bar", partition_key="foo")

    def test_partitioned_run(self, storage):
        with instance_for_test() as instance:
            instance._partitions_storage = storage

            @asset(partitions_def=MutablePartitionsDefinition.with_instance("foo", instance))
            def my_asset():
                return 1

            with pytest.raises(DagsterUnknownPartitionError):
                materialize([my_asset], instance=instance, partition_key="a")

            instance.add_mutable_partitions("foo", ["a"])
            assert instance.get_mutable_partitions("foo") == ["a"]
            assert materialize([my_asset], instance=instance, partition_key="a").success
            materialization = instance.get_latest_materialization_event(AssetKey("my_asset"))
            assert materialization
            assert materialization.dagster_event.partition == "a"

            with pytest.raises(DagsterInvalidInvocationError):
                instance.add_mutable_partitions("foo", "a")


class TestPostgresPartitionsStorage(TestPartitionsStorage):
    __test__ = True

    @pytest.fixture(scope="function", name="storage")
    def partitions_storage(self, conn_string):  # pylint: disable=arguments-renamed
        storage = PostgresPartitionsStorage.create_clean_storage(conn_string)
        assert storage
        return storage
