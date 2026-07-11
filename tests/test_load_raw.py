import pytest
from load_raw import SOURCES, stage_locally


def test_unknown_source_fails_loudly_before_any_connection():
    # The source lookup happens before any DuckDB/S3 connection is opened, so
    # a typo'd CLI argument dies immediately instead of half-staging data.
    with pytest.raises(KeyError):
        stage_locally("not_a_source")


def test_every_source_glob_keeps_hive_partition_columns():
    # DuckDB derives the season/load_date columns from these hive-partitioned
    # paths, and every staging model selects them -- a glob that drops a
    # partition segment silently breaks the entire downstream lineage.
    for source, s3_glob in SOURCES.items():
        assert "season=" in s3_glob, source
        assert "load_date=" in s3_glob, source
