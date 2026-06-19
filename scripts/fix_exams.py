#!/usr/bin/env python3
"""
Improve exam JSON files across all cert groups:
1. Add \n\n paragraph breaks between each option's explanation
2. Bold option labels (**A**, **B**, etc.)
3. Append official documentation URL to each explanation
4. Update reference field to a specific doc URL

Usage:
    python3 scripts/fix_exams.py [--group databricks|ml|cloud|all]
"""

import json
import re
import os
import sys
import glob
import argparse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXAMS = os.path.join(ROOT, "exams")


# ---------------------------------------------------------------------------
# URL pickers — per cert family
# ---------------------------------------------------------------------------

DATABRICKS_CHECKS = [
    # Delta Lake
    ("liquid clustering", "https://docs.databricks.com/delta/clustering.html"),
    ("z-order", "https://docs.databricks.com/delta/optimizations/file-mgmt.html"),
    ("zorder", "https://docs.databricks.com/delta/optimizations/file-mgmt.html"),
    ("optimize", "https://docs.databricks.com/delta/optimizations/file-mgmt.html"),
    ("vacuum", "https://docs.databricks.com/sql/language-manual/delta-vacuum.html"),
    ("transaction log", "https://docs.databricks.com/delta/delta-intro.html"),
    ("cdf", "https://docs.databricks.com/delta/delta-change-data-feed.html"),
    ("change data feed", "https://docs.databricks.com/delta/delta-change-data-feed.html"),
    ("delete vector", "https://docs.databricks.com/delta/deletion-vectors.html"),
    ("deletion vector", "https://docs.databricks.com/delta/deletion-vectors.html"),
    ("merge into", "https://docs.databricks.com/sql/language-manual/delta-merge-into.html"),
    ("time travel", "https://docs.databricks.com/delta/history.html"),
    ("restore", "https://docs.databricks.com/sql/language-manual/delta-restore.html"),
    ("clone", "https://docs.databricks.com/sql/language-manual/delta-clone.html"),
    ("shallow clone", "https://docs.databricks.com/sql/language-manual/delta-clone.html"),
    ("deep clone", "https://docs.databricks.com/sql/language-manual/delta-clone.html"),
    # Auto Loader / streaming ingestion
    ("auto loader", "https://docs.databricks.com/ingestion/auto-loader/index.html"),
    ("cloudfiles", "https://docs.databricks.com/ingestion/auto-loader/index.html"),
    ("cloud_files", "https://docs.databricks.com/ingestion/auto-loader/index.html"),
    # DLT
    ("dlt", "https://docs.databricks.com/delta-live-tables/index.html"),
    ("delta live table", "https://docs.databricks.com/delta-live-tables/index.html"),
    ("live table", "https://docs.databricks.com/delta-live-tables/index.html"),
    ("@dlt.table", "https://docs.databricks.com/delta-live-tables/python-ref.html"),
    ("@dlt.view", "https://docs.databricks.com/delta-live-tables/python-ref.html"),
    ("dlt.read_stream", "https://docs.databricks.com/delta-live-tables/python-ref.html"),
    ("expectations", "https://docs.databricks.com/delta-live-tables/expectations.html"),
    # Structured Streaming
    ("availablenow", "https://docs.databricks.com/structured-streaming/triggers.html"),
    ("trigger(", "https://docs.databricks.com/structured-streaming/triggers.html"),
    ("watermark", "https://docs.databricks.com/structured-streaming/watermarks.html"),
    ("checkpoint", "https://docs.databricks.com/structured-streaming/query-recovery.html"),
    ("foreachbatch", "https://docs.databricks.com/structured-streaming/foreach.html"),
    ("readstream", "https://docs.databricks.com/structured-streaming/index.html"),
    ("writestream", "https://docs.databricks.com/structured-streaming/index.html"),
    # Unity Catalog
    ("unity catalog", "https://docs.databricks.com/data-governance/unity-catalog/index.html"),
    ("unity_catalog", "https://docs.databricks.com/data-governance/unity-catalog/index.html"),
    ("three-level namespace", "https://docs.databricks.com/data-governance/unity-catalog/index.html"),
    ("metastore", "https://docs.databricks.com/data-governance/unity-catalog/create-metastore.html"),
    ("external location", "https://docs.databricks.com/data-governance/unity-catalog/manage-external-locations-and-credentials.html"),
    ("storage credential", "https://docs.databricks.com/data-governance/unity-catalog/manage-external-locations-and-credentials.html"),
    ("data lineage", "https://docs.databricks.com/data-governance/unity-catalog/data-lineage.html"),
    # Jobs / Workflows
    ("job cluster", "https://docs.databricks.com/workflows/jobs/create-run-jobs.html"),
    ("dbutils.notebook.run", "https://docs.databricks.com/notebooks/notebook-workflows.html"),
    ("%run", "https://docs.databricks.com/notebooks/notebook-workflows.html"),
    ("workflow", "https://docs.databricks.com/workflows/index.html"),
    ("task dependency", "https://docs.databricks.com/workflows/jobs/create-run-jobs.html"),
    # Spark
    ("shuffle partition", "https://spark.apache.org/docs/latest/sql-performance-tuning.html"),
    ("spark.sql.shuffle.partitions", "https://spark.apache.org/docs/latest/sql-performance-tuning.html"),
    ("broadcast", "https://spark.apache.org/docs/latest/sql-performance-tuning.html"),
    ("catalyst optimizer", "https://spark.apache.org/docs/latest/sql-programming-guide.html"),
    ("adaptive query execution", "https://spark.apache.org/docs/latest/sql-performance-tuning.html"),
    ("aqe", "https://spark.apache.org/docs/latest/sql-performance-tuning.html"),
    ("repartition", "https://spark.apache.org/docs/latest/rdd-programming-guide.html"),
    ("coalesce", "https://spark.apache.org/docs/latest/rdd-programming-guide.html"),
    ("accumulator", "https://spark.apache.org/docs/latest/rdd-programming-guide.html#accumulators"),
    ("broadcast variable", "https://spark.apache.org/docs/latest/rdd-programming-guide.html#broadcast-variables"),
    ("udf", "https://spark.apache.org/docs/latest/sql-ref-functions-udf-scalar.html"),
    ("pandas udf", "https://docs.databricks.com/udf/pandas.html"),
    ("applyinpandas", "https://docs.databricks.com/udf/pandas.html"),
    ("mapinpandas", "https://docs.databricks.com/udf/pandas.html"),
    # Photon / Runtime
    ("photon", "https://docs.databricks.com/runtime/photon.html"),
    ("dbr", "https://docs.databricks.com/runtime/dbr.html"),
    ("cluster policy", "https://docs.databricks.com/administration-guide/clusters/policies.html"),
    ("instance pool", "https://docs.databricks.com/clusters/instance-pools/index.html"),
    # SQL
    ("databricks sql", "https://docs.databricks.com/sql/index.html"),
    ("sql warehouse", "https://docs.databricks.com/sql/admin/create-sql-warehouse.html"),
    ("serverless", "https://docs.databricks.com/sql/admin/create-sql-warehouse.html"),
    ("query history", "https://docs.databricks.com/sql/user/queries/query-history.html"),
    # Security
    ("secret scope", "https://docs.databricks.com/security/secrets/secret-scopes.html"),
    ("dbutils.secrets", "https://docs.databricks.com/security/secrets/index.html"),
    ("table acl", "https://docs.databricks.com/security/access-control/table-acls/index.html"),
    # Analyst
    ("describe detail", "https://docs.databricks.com/sql/language-manual/sql-ref-syntax-aux-describe-detail.html"),
    ("describe history", "https://docs.databricks.com/sql/language-manual/delta-describe-history.html"),
    ("describe extended", "https://docs.databricks.com/sql/language-manual/sql-ref-syntax-aux-describe-table.html"),
    ("dashboard", "https://docs.databricks.com/sql/user/dashboards/index.html"),
    ("alert", "https://docs.databricks.com/sql/user/alerts/index.html"),
    ("managed table", "https://docs.databricks.com/data-governance/unity-catalog/create-tables.html"),
    ("external table", "https://docs.databricks.com/data-governance/unity-catalog/create-tables.html"),
]

DATABRICKS_DOMAIN_DEFAULTS = {
    "incremental-processing": "https://docs.databricks.com/delta/delta-streaming.html",
    "structured-streaming": "https://docs.databricks.com/structured-streaming/index.html",
    "production-pipelines": "https://docs.databricks.com/delta-live-tables/index.html",
    "elt-processing": "https://docs.databricks.com/delta/index.html",
    "lakehouse-platform": "https://docs.databricks.com/lakehouse/index.html",
    "data-governance": "https://docs.databricks.com/data-governance/unity-catalog/index.html",
    "data-pipeline-design": "https://docs.databricks.com/workflows/index.html",
    "dynamic-tables": "https://docs.databricks.com/delta-live-tables/index.html",
    "performance-tuning": "https://spark.apache.org/docs/latest/sql-performance-tuning.html",
    "spark-architecture": "https://spark.apache.org/docs/latest/cluster-overview.html",
    "spark-dataframe": "https://spark.apache.org/docs/latest/sql-programming-guide.html",
    "spark-sql": "https://spark.apache.org/docs/latest/sql-programming-guide.html",
    "databricks-sql": "https://docs.databricks.com/sql/index.html",
    "sql-lakehouse": "https://docs.databricks.com/sql/index.html",
    "data-exploration": "https://docs.databricks.com/notebooks/index.html",
    "dataframe-api": "https://spark.apache.org/docs/latest/sql-programming-guide.html",
    "storage": "https://docs.databricks.com/delta/index.html",
    "data-modeling": "https://docs.databricks.com/delta/index.html",
    "storing-data": "https://docs.databricks.com/delta/index.html",
    "debugging-deploying": "https://docs.databricks.com/workflows/index.html",
    "monitoring": "https://docs.databricks.com/administration-guide/system-tables/index.html",
    "visualization-dashboards": "https://docs.databricks.com/sql/user/dashboards/index.html",
    "visualization": "https://docs.databricks.com/sql/user/visualizations/index.html",
    "querying": "https://docs.databricks.com/sql/index.html",
    "advanced-sql": "https://docs.databricks.com/sql/index.html",
}

ML_CHECKS = [
    # MLflow
    ("mlflow.autolog", "https://mlflow.org/docs/latest/tracking.html#automatic-logging"),
    ("autolog", "https://mlflow.org/docs/latest/tracking.html#automatic-logging"),
    ("log_artifact", "https://mlflow.org/docs/latest/tracking.html"),
    ("log_metric", "https://mlflow.org/docs/latest/tracking.html"),
    ("log_param", "https://mlflow.org/docs/latest/tracking.html"),
    ("mlflow.start_run", "https://mlflow.org/docs/latest/tracking.html"),
    ("mlflow.end_run", "https://mlflow.org/docs/latest/tracking.html"),
    ("mlflow.set_experiment", "https://mlflow.org/docs/latest/tracking.html"),
    ("model registry", "https://mlflow.org/docs/latest/model-registry.html"),
    ("transition_model", "https://mlflow.org/docs/latest/model-registry.html"),
    ("mlflow.pyfunc", "https://mlflow.org/docs/latest/python_api/mlflow.pyfunc.html"),
    ("pyfunc", "https://mlflow.org/docs/latest/python_api/mlflow.pyfunc.html"),
    ("mlflow.sklearn", "https://mlflow.org/docs/latest/python_api/mlflow.sklearn.html"),
    ("mlflow.spark", "https://mlflow.org/docs/latest/python_api/mlflow.spark.html"),
    ("model signature", "https://mlflow.org/docs/latest/models.html#model-signature"),
    ("infer_signature", "https://mlflow.org/docs/latest/models.html#model-signature"),
    ("mlflow models serve", "https://mlflow.org/docs/latest/deployment/index.html"),
    # Feature Store
    ("feature store", "https://docs.databricks.com/machine-learning/feature-store/index.html"),
    ("featurestorecreateclient", "https://docs.databricks.com/machine-learning/feature-store/index.html"),
    ("feature_spec", "https://docs.databricks.com/machine-learning/feature-store/index.html"),
    # AutoML / HyperOpt
    ("automl", "https://docs.databricks.com/machine-learning/automl/index.html"),
    ("hyperopt", "https://docs.databricks.com/machine-learning/automl-hyperparam-tuning/hyperopt-best-practices.html"),
    ("sparktrials", "https://docs.databricks.com/machine-learning/automl-hyperparam-tuning/hyperopt-best-practices.html"),
    ("fmin", "https://docs.databricks.com/machine-learning/automl-hyperparam-tuning/hyperopt-best-practices.html"),
    # Model serving
    ("model serving", "https://docs.databricks.com/machine-learning/model-serving/index.html"),
    ("serving endpoint", "https://docs.databricks.com/machine-learning/model-serving/index.html"),
    ("real-time inference", "https://docs.databricks.com/machine-learning/model-serving/index.html"),
    # Spark ML
    ("pipeline", "https://spark.apache.org/docs/latest/ml-pipeline.html"),
    ("crossvalidator", "https://spark.apache.org/docs/latest/ml-tuning.html"),
    ("paramgridbuilder", "https://spark.apache.org/docs/latest/ml-tuning.html"),
    ("vector assembler", "https://spark.apache.org/docs/latest/ml-features.html"),
    ("randomforest", "https://spark.apache.org/docs/latest/ml-classification-regression.html"),
    ("logisticregression", "https://spark.apache.org/docs/latest/ml-classification-regression.html"),
    ("kmeans", "https://spark.apache.org/docs/latest/ml-clustering.html"),
    # GenAI / RAG
    ("rag", "https://docs.databricks.com/generative-ai/retrieval-augmented-generation.html"),
    ("retrieval augmented", "https://docs.databricks.com/generative-ai/retrieval-augmented-generation.html"),
    ("vector search", "https://docs.databricks.com/generative-ai/vector-search.html"),
    ("embedding", "https://docs.databricks.com/generative-ai/vector-search.html"),
    ("llm", "https://docs.databricks.com/large-language-models/index.html"),
    ("foundation model", "https://docs.databricks.com/machine-learning/foundation-models/index.html"),
    ("dbrx", "https://docs.databricks.com/machine-learning/foundation-models/index.html"),
    ("ai playground", "https://docs.databricks.com/large-language-models/ai-playground.html"),
    ("ai gateway", "https://docs.databricks.com/generative-ai/ai-gateway/index.html"),
    ("mosaic ai", "https://docs.databricks.com/generative-ai/index.html"),
    ("fine.tun", "https://docs.databricks.com/large-language-models/foundation-model-training.html"),
    ("system prompt", "https://docs.databricks.com/generative-ai/index.html"),
    ("context window", "https://docs.databricks.com/generative-ai/index.html"),
    ("mcp", "https://docs.databricks.com/generative-ai/index.html"),
    ("chunking", "https://docs.databricks.com/generative-ai/retrieval-augmented-generation.html"),
    ("agent", "https://docs.databricks.com/generative-ai/agent-framework/index.html"),
    ("tool call", "https://docs.databricks.com/generative-ai/agent-framework/index.html"),
    ("guardrail", "https://docs.databricks.com/generative-ai/agent-evaluation/index.html"),
]

ML_DOMAIN_DEFAULTS = {
    "databricks-ml": "https://docs.databricks.com/machine-learning/index.html",
    "feature-store": "https://docs.databricks.com/machine-learning/feature-store/index.html",
    "model-registry": "https://mlflow.org/docs/latest/model-registry.html",
    "model-deployment": "https://docs.databricks.com/machine-learning/model-serving/index.html",
    "model-lifecycle": "https://mlflow.org/docs/latest/model-registry.html",
    "experimentation": "https://mlflow.org/docs/latest/tracking.html",
    "ml-workflows": "https://docs.databricks.com/machine-learning/index.html",
    "scaling-ml": "https://spark.apache.org/docs/latest/ml-guide.html",
    "spark-ml": "https://spark.apache.org/docs/latest/ml-guide.html",
    "application-development": "https://docs.databricks.com/generative-ai/agent-framework/index.html",
    "retrieval-search": "https://docs.databricks.com/generative-ai/vector-search.html",
    "context-window": "https://docs.databricks.com/generative-ai/index.html",
    "responsible-ai": "https://docs.databricks.com/generative-ai/agent-evaluation/index.html",
    "governance-evaluation": "https://docs.databricks.com/generative-ai/agent-evaluation/index.html",
    "system-prompts": "https://docs.databricks.com/generative-ai/index.html",
    "tools-mcp": "https://docs.databricks.com/generative-ai/agent-framework/index.html",
    "memory": "https://docs.databricks.com/generative-ai/index.html",
    "design-applications": "https://docs.databricks.com/generative-ai/agent-framework/index.html",
    "maintaining-applications": "https://docs.databricks.com/generative-ai/agent-evaluation/index.html",
    "data-preparation": "https://docs.databricks.com/generative-ai/retrieval-augmented-generation.html",
    "cortex-ai": "https://docs.databricks.com/generative-ai/index.html",
    "cortex-ml": "https://docs.databricks.com/machine-learning/index.html",
}

CLOUD_CHECKS = {
    "aws": [
        ("glue crawler", "https://docs.aws.amazon.com/glue/latest/dg/add-crawler.html"),
        ("glue job", "https://docs.aws.amazon.com/glue/latest/dg/author-job.html"),
        ("glue data catalog", "https://docs.aws.amazon.com/glue/latest/dg/components-overview.html"),
        ("glue databrew", "https://docs.aws.amazon.com/databrew/latest/dg/what-is.html"),
        ("lake formation", "https://docs.aws.amazon.com/lake-formation/latest/dg/what-is-lake-formation.html"),
        ("kinesis data streams", "https://docs.aws.amazon.com/streams/latest/dev/introduction.html"),
        ("kinesis firehose", "https://docs.aws.amazon.com/firehose/latest/dev/what-is-this-service.html"),
        ("kinesis data analytics", "https://docs.aws.amazon.com/kinesisanalytics/latest/dev/what-is.html"),
        ("redshift spectrum", "https://docs.aws.amazon.com/redshift/latest/dg/c-using-spectrum.html"),
        ("redshift", "https://docs.aws.amazon.com/redshift/latest/dg/welcome.html"),
        ("athena", "https://docs.aws.amazon.com/athena/latest/ug/what-is.html"),
        ("emr", "https://docs.aws.amazon.com/emr/latest/ManagementGuide/emr-what-is-emr.html"),
        ("step function", "https://docs.aws.amazon.com/step-functions/latest/dg/welcome.html"),
        ("dms", "https://docs.aws.amazon.com/dms/latest/userguide/Welcome.html"),
        ("s3", "https://docs.aws.amazon.com/AmazonS3/latest/userguide/Welcome.html"),
        ("s3 glacier", "https://docs.aws.amazon.com/amazonglacier/latest/dev/introduction.html"),
        ("eventbridge", "https://docs.aws.amazon.com/eventbridge/latest/userguide/eb-what-is.html"),
        ("lambda", "https://docs.aws.amazon.com/lambda/latest/dg/welcome.html"),
        ("dynamodb", "https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/Introduction.html"),
        ("opensearch", "https://docs.aws.amazon.com/opensearch-service/latest/developerguide/what-is.html"),
        ("quicksight", "https://docs.aws.amazon.com/quicksight/latest/user/welcome.html"),
        ("sagemaker", "https://docs.aws.amazon.com/sagemaker/latest/dg/whatis.html"),
        ("msk", "https://docs.aws.amazon.com/msk/latest/developerguide/what-is-msk.html"),
    ],
    "gcp": [
        ("bigquery", "https://cloud.google.com/bigquery/docs/introduction"),
        ("dataflow", "https://cloud.google.com/dataflow/docs/overview"),
        ("pub/sub", "https://cloud.google.com/pubsub/docs/overview"),
        ("pubsub", "https://cloud.google.com/pubsub/docs/overview"),
        ("dataproc", "https://cloud.google.com/dataproc/docs/concepts/overview"),
        ("cloud storage", "https://cloud.google.com/storage/docs/introduction"),
        ("gcs", "https://cloud.google.com/storage/docs/introduction"),
        ("vertex ai", "https://cloud.google.com/vertex-ai/docs/start/introduction-unified-platform"),
        ("data catalog", "https://cloud.google.com/data-catalog/docs/concepts/overview"),
        ("spanner", "https://cloud.google.com/spanner/docs/whatis"),
        ("bigtable", "https://cloud.google.com/bigtable/docs/overview"),
        ("cloud composer", "https://cloud.google.com/composer/docs/concepts/overview"),
        ("looker", "https://cloud.google.com/looker/docs"),
        ("dataplex", "https://cloud.google.com/dataplex/docs/introduction"),
        ("cloud sql", "https://cloud.google.com/sql/docs/introduction"),
    ],
    "powerbi": [
        ("dax", "https://learn.microsoft.com/dax/dax-overview"),
        ("power query", "https://learn.microsoft.com/power-query/power-query-what-is-power-query"),
        ("directquery", "https://learn.microsoft.com/power-bi/connect-data/desktop-directquery-about"),
        ("import mode", "https://learn.microsoft.com/power-bi/connect-data/service-dataset-modes-understand"),
        ("composite model", "https://learn.microsoft.com/power-bi/transform-model/desktop-composite-models"),
        ("row-level security", "https://learn.microsoft.com/power-bi/enterprise/service-admin-rls"),
        ("rls", "https://learn.microsoft.com/power-bi/enterprise/service-admin-rls"),
        ("deployment pipeline", "https://learn.microsoft.com/power-bi/create-reports/deployment-pipelines-overview"),
        ("dataflow", "https://learn.microsoft.com/power-bi/transform-model/dataflows/dataflows-introduction-self-service"),
        ("measure", "https://learn.microsoft.com/dax/dax-overview"),
        ("calculated column", "https://learn.microsoft.com/power-bi/transform-model/desktop-calculated-columns"),
        ("gateway", "https://learn.microsoft.com/data-integration/gateway/service-gateway-onprem"),
        ("sensitivity label", "https://learn.microsoft.com/power-bi/enterprise/service-security-sensitivity-label-overview"),
        ("paginated report", "https://learn.microsoft.com/power-bi/paginated-reports/paginated-reports-report-builder-power-bi"),
    ],
    "fabric": [
        ("onelake", "https://learn.microsoft.com/fabric/onelake/onelake-overview"),
        ("lakehouse", "https://learn.microsoft.com/fabric/data-engineering/lakehouse-overview"),
        ("eventhouse", "https://learn.microsoft.com/fabric/real-time-intelligence/eventhouse"),
        ("kql", "https://learn.microsoft.com/fabric/real-time-intelligence/kusto-query-language"),
        ("dataflow gen2", "https://learn.microsoft.com/fabric/data-factory/dataflows-gen2-overview"),
        ("data pipeline", "https://learn.microsoft.com/fabric/data-factory/pipeline-overview"),
        ("copy activity", "https://learn.microsoft.com/fabric/data-factory/copy-data-activity"),
        ("warehouse", "https://learn.microsoft.com/fabric/data-warehouse/data-warehousing"),
        ("semantic model", "https://learn.microsoft.com/fabric/data-warehouse/semantic-models"),
        ("notebook", "https://learn.microsoft.com/fabric/data-engineering/how-to-use-notebook"),
        ("data activator", "https://learn.microsoft.com/fabric/real-time-intelligence/data-activator/data-activator-introduction"),
        ("real-time hub", "https://learn.microsoft.com/fabric/real-time-intelligence/real-time-hub/real-time-hub-overview"),
        ("eventstream", "https://learn.microsoft.com/fabric/real-time-intelligence/event-streams/overview"),
        ("shortcuts", "https://learn.microsoft.com/fabric/onelake/onelake-shortcuts"),
        ("git integration", "https://learn.microsoft.com/fabric/cicd/git-integration/intro-to-git-integration"),
        ("deployment pipeline", "https://learn.microsoft.com/fabric/cicd/deployment-pipelines/intro-to-deployment-pipelines"),
        ("power query m", "https://learn.microsoft.com/power-query/power-query-what-is-power-query"),
        ("spark", "https://learn.microsoft.com/fabric/data-engineering/spark-overview"),
        ("delta table", "https://learn.microsoft.com/fabric/data-engineering/lakehouse-and-delta-tables"),
        ("medallion", "https://learn.microsoft.com/fabric/onelake/onelake-medallion-lakehouse-architecture"),
    ],
    "sigma": [
        ("workbook", "https://help.sigmacomputing.com/docs/workbooks"),
        ("data model", "https://help.sigmacomputing.com/docs/intro-to-data-models"),
        ("warehouse view", "https://help.sigmacomputing.com/docs/create-and-manage-warehouse-views"),
        ("connection", "https://help.sigmacomputing.com/docs/manage-connections"),
        ("embed", "https://help.sigmacomputing.com/docs/get-started-with-embedding"),
        ("tag", "https://help.sigmacomputing.com/docs/tags"),
        ("permission", "https://help.sigmacomputing.com/docs/manage-member-account-types"),
        ("materialization", "https://help.sigmacomputing.com/docs/materialization"),
        ("input table", "https://help.sigmacomputing.com/docs/intro-to-input-tables"),
    ],
}

CLOUD_DOMAIN_DEFAULTS = {
    "aws": {
        "ingestion-acquisition": "https://docs.aws.amazon.com/glue/latest/dg/add-crawler.html",
        "data-processing": "https://docs.aws.amazon.com/glue/latest/dg/author-job.html",
        "storing-data": "https://docs.aws.amazon.com/AmazonS3/latest/userguide/Welcome.html",
        "querying": "https://docs.aws.amazon.com/athena/latest/ug/what-is.html",
        "data-governance": "https://docs.aws.amazon.com/lake-formation/latest/dg/what-is-lake-formation.html",
        "security": "https://docs.aws.amazon.com/lake-formation/latest/dg/security-data-lake-overview.html",
        "monitoring": "https://docs.aws.amazon.com/glue/latest/dg/monitor-glue.html",
        "data-pipeline-design": "https://docs.aws.amazon.com/step-functions/latest/dg/welcome.html",
        "incremental-processing": "https://docs.aws.amazon.com/streams/latest/dev/introduction.html",
        "structured-streaming": "https://docs.aws.amazon.com/kinesisanalytics/latest/dev/what-is.html",
    },
    "gcp": {
        "data-pipeline-design": "https://cloud.google.com/dataflow/docs/overview",
        "data-processing": "https://cloud.google.com/dataflow/docs/overview",
        "storing-data": "https://cloud.google.com/storage/docs/introduction",
        "querying": "https://cloud.google.com/bigquery/docs/introduction",
        "data-modeling": "https://cloud.google.com/bigquery/docs/introduction",
        "data-governance": "https://cloud.google.com/data-catalog/docs/concepts/overview",
        "security": "https://cloud.google.com/bigquery/docs/column-level-security-intro",
        "monitoring-alerting": "https://cloud.google.com/monitoring/docs",
        "incremental-processing": "https://cloud.google.com/pubsub/docs/overview",
        "structured-streaming": "https://cloud.google.com/dataflow/docs/overview",
    },
    "powerbi": {
        "model-data": "https://learn.microsoft.com/power-bi/transform-model/",
        "prepare-data": "https://learn.microsoft.com/power-query/power-query-what-is-power-query",
        "deploy-maintain": "https://learn.microsoft.com/power-bi/enterprise/",
        "visualize-analyze": "https://learn.microsoft.com/power-bi/create-reports/",
        "visualization": "https://learn.microsoft.com/power-bi/visuals/",
        "security": "https://learn.microsoft.com/power-bi/enterprise/service-admin-rls",
        "data-governance": "https://learn.microsoft.com/power-bi/enterprise/",
        "advanced-sql": "https://learn.microsoft.com/dax/dax-overview",
    },
    "fabric": {
        "lakehouse-platform": "https://learn.microsoft.com/fabric/data-engineering/lakehouse-overview",
        "data-pipeline-design": "https://learn.microsoft.com/fabric/data-factory/pipeline-overview",
        "elt-processing": "https://learn.microsoft.com/fabric/data-factory/dataflows-gen2-overview",
        "storing-data": "https://learn.microsoft.com/fabric/onelake/onelake-overview",
        "incremental-processing": "https://learn.microsoft.com/fabric/real-time-intelligence/eventhouse",
        "data-governance": "https://learn.microsoft.com/fabric/governance/",
        "security": "https://learn.microsoft.com/fabric/security/",
        "visualization": "https://learn.microsoft.com/power-bi/create-reports/",
        "structured-streaming": "https://learn.microsoft.com/fabric/real-time-intelligence/eventhouse",
    },
    "sigma": {
        "visualization": "https://help.sigmacomputing.com/docs/workbooks",
        "querying": "https://help.sigmacomputing.com/docs/workbooks",
        "data-exploration": "https://help.sigmacomputing.com/docs/workbooks",
        "visualization-dashboards": "https://help.sigmacomputing.com/docs/workbooks",
    },
}


def detect_cert_family(filepath):
    parts = filepath.replace("\\", "/").split("/")
    for i, p in enumerate(parts):
        if p == "exams" and i + 1 < len(parts):
            cert = parts[i + 1]
            if cert.startswith("snowpro") or cert.startswith("snowflake"):
                return "snowflake"
            if cert in ("machine-learning-associate", "machine-learning-professional",
                        "generative-ai-engineer-associate", "context-engineer-associate"):
                return "ml"
            if cert.startswith("data-") or cert.startswith("spark-"):
                return "databricks"
            if cert.startswith("aws-"):
                return "aws"
            if cert.startswith("gcp-"):
                return "gcp"
            if cert.startswith("powerbi-"):
                return "powerbi"
            if cert.startswith("fabric-"):
                return "fabric"
            if cert.startswith("sigma-"):
                return "sigma"
    return "databricks"


def pick_url(question, family):
    domain = question.get("domain", "").lower()
    stem = question.get("stem", "").lower()
    explanation = question.get("explanation", "").lower()
    reference = question.get("reference", "").lower()
    options_text = " ".join(o.get("text", "").lower() for o in question.get("options", []))
    all_text = f"{reference} {stem} {explanation} {options_text} {domain}"

    if family == "databricks":
        for kw, url in DATABRICKS_CHECKS:
            if kw in all_text:
                return url
        for d, url in DATABRICKS_DOMAIN_DEFAULTS.items():
            if d in domain:
                return url
        return "https://docs.databricks.com/index.html"

    if family == "ml":
        for kw, url in ML_CHECKS:
            if kw in all_text:
                return url
        for d, url in ML_DOMAIN_DEFAULTS.items():
            if d in domain:
                return url
        return "https://docs.databricks.com/machine-learning/index.html"

    if family in ("aws", "gcp", "powerbi", "fabric", "sigma"):
        checks = CLOUD_CHECKS.get(family, [])
        for kw, url in checks:
            if kw in all_text:
                return url
        domain_map = CLOUD_DOMAIN_DEFAULTS.get(family, {})
        for d, url in domain_map.items():
            if d in domain:
                return url
        # Family-level default
        defaults = {
            "aws": "https://docs.aws.amazon.com/glue/latest/dg/what-is-glue.html",
            "gcp": "https://cloud.google.com/bigquery/docs/introduction",
            "powerbi": "https://learn.microsoft.com/power-bi/fundamentals/power-bi-overview",
            "fabric": "https://learn.microsoft.com/fabric/get-started/microsoft-fabric-overview",
            "sigma": "https://help.sigmacomputing.com/docs/get-started-with-sigma",
        }
        return defaults.get(family, "https://docs.databricks.com/index.html")

    return "https://docs.databricks.com/index.html"


# ---------------------------------------------------------------------------
# Explanation reformatter (same logic as Snowflake script)
# ---------------------------------------------------------------------------

SPLIT_RE = re.compile(
    r'(?<=[.!?])\s+'
    r'(?='
    r'(?:Both\s+[A-F]\s+and\s+[A-F]\s+are\b'
    r'|[A-F]\s+and\s+[A-F]\s+and\s+[A-F]\s+are\b'
    r'|[A-F]\s+and\s+[A-F]\s+are\b'
    r'|[A-F]\s+(?:is|are)\b'
    r'|Option\s+[A-F]\s+(?:is|are)\b'
    r')'
    r')'
)

FALLBACK_RE = re.compile(
    r'\.\s+(?=(?:Both\s+[A-F]\s+and\s+[A-F]\s+are\b'
    r'|[A-F]\s+and\s+[A-F]\s+and\s+[A-F]\s+are\b'
    r'|[A-F]\s+and\s+[A-F]\s+are\b'
    r'|[A-F]\s+(?:is|are)\b'
    r'|Option\s+[A-F]\s+(?:is|are)\b'
    r'))'
)


def bold_labels(text):
    text = re.sub(r'\bBoth\s+([A-F])\s+and\s+([A-F])\s+are\b', r'Both **\1** and **\2** are', text)
    text = re.sub(r'\b([A-F])\s+and\s+([A-F])\s+and\s+([A-F])\s+are\b', r'**\1**, **\2**, and **\3** are', text)
    text = re.sub(r'\b([A-F])\s+and\s+([A-F])\s+are\b', r'**\1** and **\2** are', text)
    text = re.sub(r'(?<![*\w])([A-F])\s+(is|are|was)\b', r'**\1** \2', text)
    text = re.sub(r'\(option ([A-F])\)', r'(**\1**)', text, flags=re.IGNORECASE)
    text = re.sub(r'\boption\s+([A-F])\b', r'option **\1**', text, flags=re.IGNORECASE)
    return text


def split_paragraphs(explanation):
    parts = SPLIT_RE.split(explanation.strip())
    if len(parts) > 1:
        return [p.strip() for p in parts if p.strip()]
    parts = FALLBACK_RE.split(explanation.strip())
    if len(parts) > 1:
        result = []
        for p in parts:
            p = p.strip()
            if p and not p.endswith('.'):
                p += '.'
            if p:
                result.append(p)
        return result
    return [explanation.strip()]


def reformat(explanation, doc_url):
    if not explanation:
        return doc_url

    if "\n\n" in explanation:
        # Already paragraph-formatted; bold any unbolded labels, ensure doc link
        paras = [bold_labels(p) for p in explanation.split("\n\n")]
        last = paras[-1].strip()
        if not (last.startswith("http") or "https://" in last):
            if "https://" not in explanation:
                paras.append(doc_url)
        return "\n\n".join(paras)

    paras = split_paragraphs(explanation)
    paras = [bold_labels(p) for p in paras]
    if "https://" not in explanation:
        paras.append(doc_url)
    return "\n\n".join(paras)


def process_file(filepath, family):
    with open(filepath, encoding="utf-8") as f:
        data = json.load(f)

    changed = 0
    for q in data.get("questions", []):
        doc_url = pick_url(q, family)
        old_exp = q.get("explanation", "")
        new_exp = reformat(old_exp, doc_url)
        if new_exp != old_exp:
            q["explanation"] = new_exp
            changed += 1
        # Always update reference to specific URL
        q["reference"] = doc_url

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")

    return len(data.get("questions", [])), changed


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

GROUPS = {
    "databricks": [
        "data-engineer-associate",
        "data-engineer-professional",
        "data-analyst-associate",
        "spark-developer-associate",
    ],
    "ml": [
        "machine-learning-associate",
        "machine-learning-professional",
        "generative-ai-engineer-associate",
        "context-engineer-associate",
    ],
    "cloud": [
        "aws-data-engineer-associate",
        "gcp-professional-data-engineer",
        "powerbi-data-analyst",
        "fabric-analytics-engineer",
        "fabric-data-engineer-associate",
        "sigma-certified-developer",
    ],
}

FAMILY_MAP = {
    "data-engineer-associate": "databricks",
    "data-engineer-professional": "databricks",
    "data-analyst-associate": "databricks",
    "spark-developer-associate": "databricks",
    "machine-learning-associate": "ml",
    "machine-learning-professional": "ml",
    "generative-ai-engineer-associate": "ml",
    "context-engineer-associate": "ml",
    "aws-data-engineer-associate": "aws",
    "gcp-professional-data-engineer": "gcp",
    "powerbi-data-analyst": "powerbi",
    "fabric-analytics-engineer": "fabric",
    "fabric-data-engineer-associate": "fabric",
    "sigma-certified-developer": "sigma",
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--group", choices=["databricks", "ml", "cloud", "all"], default="all")
    args = parser.parse_args()

    if args.group == "all":
        certs = [c for g in GROUPS.values() for c in g]
    else:
        certs = GROUPS.get(args.group, [])

    total_q = total_changed = total_files = 0
    for cert in certs:
        cert_dir = os.path.join(EXAMS, cert)
        if not os.path.isdir(cert_dir):
            print(f"SKIP (no dir): {cert}", file=sys.stderr)
            continue
        family = FAMILY_MAP.get(cert, "databricks")
        for fp in sorted(glob.glob(os.path.join(cert_dir, "exam-*.json"))):
            q_count, changed = process_file(fp, family)
            rel = os.path.relpath(fp, ROOT)
            print(f"  {rel}: {q_count} questions, {changed} explanations updated")
            total_q += q_count
            total_changed += changed
            total_files += 1

    print(f"\nDone: {total_files} files, {total_q} questions, {total_changed} explanations reformatted")


if __name__ == "__main__":
    main()
