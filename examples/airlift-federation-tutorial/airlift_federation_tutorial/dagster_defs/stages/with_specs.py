from dagster import Definitions
from dagster._core.definitions.asset_spec import replace_attributes
from dagster_airlift.core import (
    AirflowBasicAuthBackend,
    AirflowInstance,
    build_airflow_polling_sensor,
    load_airflow_dag_asset_specs,
)

upstream_airflow_instance = AirflowInstance(
    auth_backend=AirflowBasicAuthBackend(
        webserver_url="http://localhost:8081",
        username="admin",
        password="admin",
    ),
    name="upstream",
)

downstream_airflow_instance = AirflowInstance(
    auth_backend=AirflowBasicAuthBackend(
        webserver_url="http://localhost:8082",
        username="admin",
        password="admin",
    ),
    name="downstream",
)

load_customers_dag_asset = next(
    iter(
        load_airflow_dag_asset_specs(
            airflow_instance=upstream_airflow_instance,
            dag_selector_fn=lambda dag: dag.dag_id == "load_customers",
        )
    )
)
customer_metrics_dag_asset = replace_attributes(
    next(
        iter(
            load_airflow_dag_asset_specs(
                airflow_instance=downstream_airflow_instance,
                dag_selector_fn=lambda dag: dag.dag_id == "customer_metrics",
            )
        )
        # Add a dependency on the load_customers_dag_asset
    ),
    deps=[load_customers_dag_asset],
)

upstream_sensor = build_airflow_polling_sensor(
    mapped_assets=[load_customers_dag_asset],
    airflow_instance=upstream_airflow_instance,
)
downstream_sensor = build_airflow_polling_sensor(
    mapped_assets=[customer_metrics_dag_asset],
    airflow_instance=downstream_airflow_instance,
)

defs = Definitions(
    assets=[load_customers_dag_asset, customer_metrics_dag_asset],
    sensors=[upstream_sensor, downstream_sensor],
)
