#!/usr/bin/env python3
"""
Unit Tests for the Database Module (database.py)
"""

import pytest
import os
import sqlite3
import tempfile
import json
from datetime import datetime, timedelta
import pandas as pd
import shutil
import unittest # For mock.ANY if needed

# Module to test
from database import DatabaseManager, DatabaseError

# --- Fixtures ---
# These are expected to be in conftest.py or defined here if this file is standalone.
# For this exercise, we assume they are available from a conftest.py.

# --- Test Cases ---

def test_database_initialization(in_memory_db_manager: DatabaseManager):
    """Test if init_database creates all necessary tables and indexes."""
    dbm = in_memory_db_manager
    with dbm.get_connection() as conn:
        cursor = conn.cursor()
        
        tables = ["datasheets", "parameters", "queries", "parts"]
        for table in tables:
            cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table}';")
            assert cursor.fetchone() is not None, f"Table {table} was not created."

        indexes = ["idx_parameters_name", "idx_parameters_part", "idx_datasheets_supplier", "idx_parameters_datasheet_part_name"]
        for index in indexes:
            cursor.execute(f"SELECT name FROM sqlite_master WHERE type='index' AND name='{index}';")
            assert cursor.fetchone() is not None, f"Index {index} was not created."

    # Test idempotency (running init_database again should not fail)
    dbm.init_database() # Should run without error

def test_save_and_get_datasheet(in_memory_db_manager: DatabaseManager, sample_extraction_data_v1):
    """Test saving and retrieving a datasheet."""
    dbm = in_memory_db_manager
    data = sample_extraction_data_v1
    
    datasheet_id = dbm.save_datasheet(
        supplier=data["supplier"],
        product_family=data["product_family"],
        filename="test.pdf",
        data=data,
        file_hash="hash123",
        status="complete"
    )
    assert datasheet_id > 0

    retrieved_ds = dbm.get_datasheet(datasheet_id)
    assert retrieved_ds is not None
    assert retrieved_ds["id"] == datasheet_id
    assert retrieved_ds["supplier"] == data["supplier"]
    assert retrieved_ds["product_family"] == data["product_family"]
    assert retrieved_ds["file_name"] == "test.pdf"
    assert retrieved_ds["file_hash"] == "hash123"
    assert retrieved_ds["processing_status"] == "complete"
    assert retrieved_ds["extracted_data"]["supplier"] == data["supplier"] # Check nested data

    # Test getting a non-existent datasheet
    assert dbm.get_datasheet(999) is None

def test_save_datasheet_duplicate_hash(in_memory_db_manager: DatabaseManager, sample_extraction_data_v1):
    """Test that saving a datasheet with an existing hash returns the existing ID."""
    dbm = in_memory_db_manager
    data = sample_extraction_data_v1
    
    id1 = dbm.save_datasheet(data["supplier"], data["product_family"], "file1.pdf", data, "testhash")
    id2 = dbm.save_datasheet(data["supplier"], data["product_family"], "file2.pdf", data, "testhash") # Same hash
    
    assert id1 == id2 # Should return existing ID
    all_ds = dbm.get_all_datasheets()
    assert len(all_ds) == 1 # Only one entry should exist

def test_save_datasheet_failed_status(in_memory_db_manager: DatabaseManager, sample_extraction_data_v1):
    """Test saving a datasheet with a 'failed' status and error message."""
    dbm = in_memory_db_manager
    data = sample_extraction_data_v1 # Use sample data for supplier/family, but extraction data will be empty
    error_msg = "PDF parsing failed due to corruption."
    
    datasheet_id = dbm.save_datasheet(
        supplier=data["supplier"],
        product_family=data["product_family"],
        filename="failed_extraction.pdf",
        data={}, # Empty data for failed extraction
        status="failed",
        error_message=error_msg
    )
    
    retrieved_ds = dbm.get_datasheet(datasheet_id)
    assert retrieved_ds["processing_status"] == "failed"
    assert retrieved_ds["error_message"] == error_msg
    
    # Check that no parameters were saved for a failed datasheet
    with dbm.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM parameters WHERE datasheet_id = ?", (datasheet_id,))
        param_count = cursor.fetchone()[0]
    assert param_count == 0


def test_get_all_datasheets(in_memory_db_manager: DatabaseManager, sample_extraction_data_v1, sample_extraction_data_v2):
    """Test retrieving all datasheets."""
    dbm = in_memory_db_manager
    dbm.save_datasheet(sample_extraction_data_v1["supplier"], sample_extraction_data_v1["product_family"], "file1.pdf", sample_extraction_data_v1)
    # Introduce a small delay to ensure different upload_date for ordering
    import time
    time.sleep(0.01)
    dbm.save_datasheet(sample_extraction_data_v2["supplier"], sample_extraction_data_v2["product_family"], "file2.pdf", sample_extraction_data_v2)

    all_ds = dbm.get_all_datasheets()
    assert isinstance(all_ds, pd.DataFrame)
    assert len(all_ds) == 2
    # Check if ordered by upload_date DESC (file2.pdf should be first)
    assert all_ds.iloc[0]["file_name"] == "file2.pdf"
    assert all_ds.iloc[1]["file_name"] == "file1.pdf"

def test_update_datasheet_status(in_memory_db_manager: DatabaseManager, sample_extraction_data_v1):
    """Test updating the status of a datasheet."""
    dbm = in_memory_db_manager
    ds_id = dbm.save_datasheet(sample_extraction_data_v1["supplier"], sample_extraction_data_v1["product_family"], "update_me.pdf", sample_extraction_data_v1, status="processing")
    
    dbm.update_datasheet_status(ds_id, "complete")
    updated_ds = dbm.get_datasheet(ds_id)
    assert updated_ds["processing_status"] == "complete"
    assert updated_ds["error_message"] is None

    dbm.update_datasheet_status(ds_id, "failed", "AI processing timeout")
    updated_ds = dbm.get_datasheet(ds_id)
    assert updated_ds["processing_status"] == "failed"
    assert updated_ds["error_message"] == "AI processing timeout"

def test_delete_datasheet(in_memory_db_manager: DatabaseManager, sample_extraction_data_v1):
    """Test deleting a datasheet and its related data handling."""
    dbm = in_memory_db_manager
    ds_id = dbm.save_datasheet(sample_extraction_data_v1["supplier"], sample_extraction_data_v1["product_family"], "to_delete.pdf", sample_extraction_data_v1)
    
    # Verify it exists
    assert dbm.get_datasheet(ds_id) is not None
    
    # Check parameters and parts associated with this datasheet_id before deletion
    part_number_to_check = sample_extraction_data_v1["variants"][0]["part_number"]
    params_before_delete = dbm.get_parameters_for_part(part_number_to_check)
    assert not params_before_delete.empty
    
    part_details_before = dbm.get_part_details(part_number_to_check)
    assert part_details_before is not None
    assert part_details_before['datasheet_id'] == ds_id

    dbm.delete_datasheet(ds_id)
    
    # Verify datasheet is deleted
    assert dbm.get_datasheet(ds_id) is None
    
    # Verify parameters associated with this datasheet_id are deleted
    with dbm.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM parameters WHERE datasheet_id = ?", (ds_id,))
        param_count = cursor.fetchone()[0]
    assert param_count == 0
    
    # Verify parts associated with this datasheet_id have their datasheet_id set to NULL
    part_details_after = dbm.get_part_details(part_number_to_check)
    assert part_details_after is not None # Part itself is not deleted
    assert part_details_after['datasheet_id'] is None


def test_get_parameters_comparison(in_memory_db_manager: DatabaseManager, sample_extraction_data_v1, sample_extraction_data_v2):
    """Test retrieving parameters for comparison."""
    dbm = in_memory_db_manager
    dbm.save_datasheet(sample_extraction_data_v1["supplier"], sample_extraction_data_v1["product_family"], "file1.pdf", sample_extraction_data_v1)
    dbm.save_datasheet(sample_extraction_data_v2["supplier"], sample_extraction_data_v2["product_family"], "file2.pdf", sample_extraction_data_v2)

    # Test for 'temp_range'
    temp_params = dbm.get_parameters_comparison("temp_range")
    assert isinstance(temp_params, pd.DataFrame)
    assert len(temp_params) == 2
    assert "temp_range" in temp_params["parameter_name"].str.lower().tolist()
    
    # Test case-insensitivity
    temp_params_case = dbm.get_parameters_comparison("TEMP_RANGE")
    assert len(temp_params_case) == 2

    # Test for 'data_rate' (numeric values)
    dr_params = dbm.get_parameters_comparison("data_rate")
    assert len(dr_params) == 2
    # Check if 'parameter_value' column is numeric (or can be converted)
    # The database saves as TEXT, so conversion happens in the function or later.
    # We'll check if the values are what we expect and can be converted.
    assert '10' in dr_params['parameter_value'].tolist()
    assert '25' in dr_params['parameter_value'].tolist()
    # Attempt conversion to numeric to ensure it's possible for numeric params
    numeric_dr_values = pd.to_numeric(dr_params['parameter_value'], errors='coerce')
    assert not numeric_dr_values.isnull().any()


    # Test for a parameter that doesn't exist
    non_exist_params = dbm.get_parameters_comparison("non_existent_param")
    assert len(non_exist_params) == 0

def test_get_unique_parameters(in_memory_db_manager: DatabaseManager, sample_extraction_data_v1, sample_extraction_data_v2):
    """Test retrieving unique parameter names."""
    dbm = in_memory_db_manager
    dbm.save_datasheet(sample_extraction_data_v1["supplier"], sample_extraction_data_v1["product_family"], "file1.pdf", sample_extraction_data_v1)
    dbm.save_datasheet(sample_extraction_data_v2["supplier"], sample_extraction_data_v2["product_family"], "file2.pdf", sample_extraction_data_v2)

    unique_params = dbm.get_unique_parameters()
    assert isinstance(unique_params, pd.DataFrame)
    
    expected_params = {"temp_range", "data_rate", "voltage"}
    actual_params = set(unique_params["parameter_name"].tolist())
    assert actual_params == expected_params
    
    # Check counts and categories
    assert "count" in unique_params.columns
    assert "category" in unique_params.columns
    temp_range_row = unique_params[unique_params["parameter_name"] == "temp_range"]
    assert temp_range_row.iloc[0]["count"] == 2
    assert temp_range_row.iloc[0]["category"] == "environmental"

def test_get_metrics(in_memory_db_manager: DatabaseManager, sample_extraction_data_v1, sample_extraction_data_v2):
    """Test retrieving database metrics."""
    dbm = in_memory_db_manager
    dbm.save_datasheet(sample_extraction_data_v1["supplier"], sample_extraction_data_v1["product_family"], "f1.pdf", sample_extraction_data_v1)
    dbm.save_datasheet(sample_extraction_data_v2["supplier"], sample_extraction_data_v2["product_family"], "f2.pdf", sample_extraction_data_v2)
    dbm.save_query("test query", "test response", 0.1)

    metrics = dbm.get_metrics()
    assert metrics["datasheets"] == 2
    assert metrics["parameters"] == 3 # temp_range, data_rate, voltage
    assert metrics["parts"] == 3 # PN001, PN002, PN003
    assert metrics["suppliers"] == 2 # SupplierA, SupplierB
    assert metrics["queries"] == 1

def test_get_extraction_stats(in_memory_db_manager: DatabaseManager, sample_extraction_data_v1, sample_extraction_data_v2):
    """Test retrieving extraction method statistics."""
    dbm = in_memory_db_manager
    dbm.save_datasheet(sample_extraction_data_v1["supplier"], sample_extraction_data_v1["product_family"], "f1.pdf", sample_extraction_data_v1)
    dbm.save_datasheet(sample_extraction_data_v2["supplier"], sample_extraction_data_v2["product_family"], "f2.pdf", sample_extraction_data_v2)

    stats_df = dbm.get_extraction_stats()
    assert isinstance(stats_df, pd.DataFrame)
    # sample_extraction_data_v1 has 2 'pattern' params
    # sample_extraction_data_v2 has 2 'ai' params and 1 'merged' param
    assert len(stats_df) == 3 # pattern, ai, merged
    
    pattern_stats = stats_df[stats_df["extraction_method"] == "pattern"].iloc[0]
    assert pattern_stats["count"] == 2 
    assert pattern_stats["avg_confidence"] == pytest.approx((0.9 + 0.95) / 2)

    ai_stats = stats_df[stats_df["extraction_method"] == "ai"].iloc[0]
    assert ai_stats["count"] == 2 
    assert ai_stats["avg_confidence"] == pytest.approx((0.8 + 0.88) / 2)

    merged_stats = stats_df[stats_df["extraction_method"] == "merged"].iloc[0]
    assert merged_stats["count"] == 1 
    assert merged_stats["avg_confidence"] == pytest.approx(0.92)


def test_compare_extraction_methods(in_memory_db_manager: DatabaseManager, sample_extraction_data_v1, sample_extraction_data_v2):
    """Test comparing parameter values/confidence by different extraction methods."""
    dbm = in_memory_db_manager
    dbm.save_datasheet(sample_extraction_data_v1["supplier"], sample_extraction_data_v1["product_family"], "f1.pdf", sample_extraction_data_v1)
    dbm.save_datasheet(sample_extraction_data_v2["supplier"], sample_extraction_data_v2["product_family"], "f2.pdf", sample_extraction_data_v2)

    # Compare 'temp_range'
    comp_df_temp = dbm.compare_extraction_methods("temp_range")
    assert len(comp_df_temp) == 2 # pattern and ai
    pattern_temp = comp_df_temp[comp_df_temp["extraction_method"] == "pattern"].iloc[0]
    ai_temp = comp_df_temp[comp_df_temp["extraction_method"] == "ai"].iloc[0]
    assert pattern_temp["samples"] == 1
    assert pattern_temp["avg_confidence"] == pytest.approx(0.9)
    assert ai_temp["samples"] == 1
    assert ai_temp["avg_confidence"] == pytest.approx(0.8)
    assert pd.isna(pattern_temp["avg_value"]) # temp_range values are strings like "-40 to 85"

    # Compare 'data_rate'
    comp_df_dr = dbm.compare_extraction_methods("data_rate")
    assert len(comp_df_dr) == 2 # pattern and merged
    pattern_dr = comp_df_dr[comp_df_dr["extraction_method"] == "pattern"].iloc[0]
    merged_dr = comp_df_dr[comp_df_dr["extraction_method"] == "merged"].iloc[0]
    assert pattern_dr["samples"] == 1
    assert pattern_dr["avg_confidence"] == pytest.approx(0.95)
    assert pattern_dr["avg_value"] == pytest.approx(10.0)
    assert merged_dr["samples"] == 1
    assert merged_dr["avg_confidence"] == pytest.approx(0.92)
    assert merged_dr["avg_value"] == pytest.approx(25.0)


def test_get_suppliers_and_product_families(in_memory_db_manager: DatabaseManager, sample_extraction_data_v1, sample_extraction_data_v2):
    """Test retrieving unique suppliers and product families."""
    dbm = in_memory_db_manager
    dbm.save_datasheet(sample_extraction_data_v1["supplier"], sample_extraction_data_v1["product_family"], "f1.pdf", sample_extraction_data_v1)
    dbm.save_datasheet(sample_extraction_data_v2["supplier"], sample_extraction_data_v2["product_family"], "f2.pdf", sample_extraction_data_v2)

    suppliers = dbm.get_suppliers()
    assert sorted(suppliers) == sorted(["SupplierA", "SupplierB"])

    product_families = dbm.get_product_families()
    assert sorted(product_families) == sorted(["FamilyX", "FamilyY"])

def test_save_and_get_queries(in_memory_db_manager: DatabaseManager):
    """Test saving and retrieving user queries."""
    dbm = in_memory_db_manager
    
    query_id1 = dbm.save_query("Query 1", "Response 1", 0.1)
    import time
    time.sleep(0.01) # ensure different timestamps
    query_id2 = dbm.save_query("Query 2", "Response 2", 0.2)
    
    assert query_id1 > 0
    assert query_id2 > 0

    recent_queries = dbm.get_recent_queries(limit=5)
    assert isinstance(recent_queries, pd.DataFrame)
    assert len(recent_queries) == 2
    assert recent_queries.iloc[0]["query_text"] == "Query 2" # Most recent first
    assert recent_queries.iloc[1]["query_text"] == "Query 1"
    assert recent_queries.iloc[0]["execution_time"] == pytest.approx(0.2)

def test_search_parts(in_memory_db_manager: DatabaseManager, sample_extraction_data_v1, sample_extraction_data_v2):
    """Test searching for parts."""
    dbm = in_memory_db_manager
    dbm.save_datasheet(sample_extraction_data_v1["supplier"], sample_extraction_data_v1["product_family"], "f1.pdf", sample_extraction_data_v1)
    dbm.save_datasheet(sample_extraction_data_v2["supplier"], sample_extraction_data_v2["product_family"], "f2.pdf", sample_extraction_data_v2)

    # Search by part number prefix
    results_pn = dbm.search_parts("PN00")
    assert len(results_pn) == 3
    assert "PN001" in results_pn["part_number"].tolist()
    assert "PN002" in results_pn["part_number"].tolist()
    assert "PN003" in results_pn["part_number"].tolist()

    # Search by supplier
    results_supplier = dbm.search_parts("SupplierA")
    assert len(results_supplier) == 1
    assert results_supplier.iloc[0]["part_number"] == "PN001"

    # Search by non-existent term
    results_none = dbm.search_parts("NonExistent")
    assert len(results_none) == 0

def test_get_part_details(in_memory_db_manager: DatabaseManager, sample_extraction_data_v1):
    """Test retrieving detailed information for a specific part."""
    dbm = in_memory_db_manager
    ds_id = dbm.save_datasheet(sample_extraction_data_v1["supplier"], sample_extraction_data_v1["product_family"], "f1.pdf", sample_extraction_data_v1)
    
    part_number = "PN001"
    details = dbm.get_part_details(part_number)
    
    assert details is not None
    assert details["part_number"] == part_number
    assert details["supplier"] == sample_extraction_data_v1["supplier"]
    assert details["product_family"] == sample_extraction_data_v1["product_family"]
    assert details["file_name"] == "f1.pdf" # This depends on how get_part_details joins
    assert details["datasheet_id"] == ds_id
    
    assert "parameters" in details
    assert len(details["parameters"]) == 2 # temp_range, data_rate
    param_names = [p["parameter_name"] for p in details["parameters"]]
    assert "temp_range" in param_names
    assert "data_rate" in param_names

    # Test non-existent part
    assert dbm.get_part_details("NonExistentPN") is None

def test_get_parameters_for_part(in_memory_db_manager: DatabaseManager, sample_extraction_data_v1):
    """Test retrieving parameters for a specific part."""
    dbm = in_memory_db_manager
    dbm.save_datasheet(sample_extraction_data_v1["supplier"], sample_extraction_data_v1["product_family"], "f1.pdf", sample_extraction_data_v1)
    
    part_number = "PN001"
    params_df = dbm.get_parameters_for_part(part_number)
    
    assert isinstance(params_df, pd.DataFrame)
    assert len(params_df) == 2
    assert "temp_range" in params_df["parameter_name"].tolist()
    assert "data_rate" in params_df["parameter_name"].tolist()
    
    # Test non-existent part
    assert dbm.get_parameters_for_part("NonExistentPN").empty

def test_backup_and_restore_database(temp_db_manager: DatabaseManager, sample_extraction_data_v1):
    """Test creating a backup and restoring the database."""
    dbm = temp_db_manager # Use file-based DB for this test
    
    # Save initial data
    dbm.save_datasheet(sample_extraction_data_v1["supplier"], sample_extraction_data_v1["product_family"], "f1.pdf", sample_extraction_data_v1)
    initial_metrics = dbm.get_metrics()
    assert initial_metrics["datasheets"] == 1

    # Create backup
    backup_file_path = dbm.create_backup()
    assert os.path.exists(backup_file_path)

    # Modify the database (e.g., delete the datasheet)
    dbm.delete_datasheet(1) # Assuming first ID is 1
    modified_metrics = dbm.get_metrics()
    assert modified_metrics["datasheets"] == 0

    # Restore from backup
    dbm.restore_backup(backup_file_path)
    restored_metrics = dbm.get_metrics()
    assert restored_metrics["datasheets"] == 1
    # Compare all relevant metrics, not just the object
    assert restored_metrics["parameters"] == initial_metrics["parameters"]
    assert restored_metrics["parts"] == initial_metrics["parts"]


    # Test restoring non-existent backup
    with pytest.raises(DatabaseError, match="Backup file not found"):
        dbm.restore_backup("non_existent_backup.db")

def test_vacuum_database(temp_db_manager: DatabaseManager):
    """Test vacuuming the database."""
    dbm = temp_db_manager # Use file-based DB for this test
    # Just ensure it runs without error
    try:
        dbm.vacuum_database()
    except Exception as e:
        pytest.fail(f"Vacuum database failed: {e}")

def test_database_error_handling(monkeypatch):
    """Test error handling for database operations."""
    # Use a temporary non-existent path for the DB to force connection error
    # This requires the directory to not exist.
    non_existent_path = os.path.join(tempfile.gettempdir(), "non_existent_dir_for_db_test", "test.db")
    if os.path.exists(os.path.dirname(non_existent_path)): # pragma: no cover
        shutil.rmtree(os.path.dirname(non_existent_path))

    manager = DatabaseManager(db_file=non_existent_path)

    with pytest.raises(DatabaseError, match="Failed to connect to database"):
        # init_database is called in constructor, but let's call it again to be sure
        # or try another operation that requires connection.
        with manager.get_connection() as conn:
            pass


    # Mock sqlite3.connect to raise an error during an operation
    # This is more complex as get_connection is a context manager.
    # A simpler test for now: try an operation that would fail if DB is bad.
    # (The above test already covers connection failure during init)
    
    # Create a valid in-memory DB for this part
    dbm_valid = DatabaseManager(db_file=":memory:")
    
    def mock_execute_raises_error(*args, **kwargs):
        raise sqlite3.Error("Simulated query error")
    
    # If get_connection itself fails (e.g., DB file permissions)
    class MockConnection: # pragma: no cover
        def __init__(self, *args, **kwargs):
            raise sqlite3.Error("Simulated connection error in get_connection")
        def cursor(self): pass
        def execute(self, *args, **kwargs): pass
        def commit(self): pass
        def close(self): pass
        def __enter__(self): return self
        def __exit__(self, exc_type, exc_val, exc_tb): pass

    original_connect = sqlite3.connect
    
    def mock_sqlite_connect_fail(*args, **kwargs): # pragma: no cover
        if args[0] == "force_fail.db": # specific db name to trigger failure
            raise sqlite3.Error("Simulated connect error")
        return original_connect(*args, **kwargs)

    monkeypatch.setattr(sqlite3, "connect", mock_sqlite_connect_fail)
    
    dbm_force_fail = DatabaseManager(db_file="force_fail.db")
    with pytest.raises(DatabaseError, match="Failed to connect to database"):
        with dbm_force_fail.get_connection() as conn: # This will trigger the error
            pass # pragma: no cover
    
    # Restore original connect
    monkeypatch.setattr(sqlite3, "connect", original_connect)


if __name__ == "__main__": # pragma: no cover
    pytest.main()
