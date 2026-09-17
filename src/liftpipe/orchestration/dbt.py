"""dbt models as Dagster assets via dagster-dbt.

Each dbt model, seed and snapshot becomes an asset and each dbt test an asset check.
The dbt sources ``raw.*`` map to the asset keys of the Python ingestion assets, so the
lineage graph runs from export file to dashboard Parquet without gaps.
"""

from dagster import AssetExecutionContext
from dagster_dbt import DbtCliResource, DbtProject, dbt_assets

from liftpipe.config import DBT_PROJECT_DIR

dbt_project = DbtProject(project_dir=DBT_PROJECT_DIR, profiles_dir=DBT_PROJECT_DIR)
# Under `dagster dev` this runs `dbt parse` so the manifest is always current; on a fresh
# checkout (CI, first run) parse once so the asset graph can be built.
dbt_project.prepare_if_dev()
if not dbt_project.manifest_path.exists():
    dbt_project.preparer.prepare(dbt_project)


@dbt_assets(manifest=dbt_project.manifest_path)
def liftpipe_dbt_assets(context: AssetExecutionContext, dbt: DbtCliResource):
    yield from dbt.cli(["build"], context=context).stream()
