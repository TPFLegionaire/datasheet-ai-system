#!/usr/bin/env python3
"""
Pytest Configurations and Shared Fixtures for Datasheet AI Comparison System Tests.
"""

import pytest
import os
import sys
import tempfile
import json
import shutil
import asyncio
import hashlib
import secrets
from datetime import datetime, timedelta
from unittest.mock import MagicMock, AsyncMock, patch

# Add the project root to the Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

# Import project modules
from pdf_extractor import PDFExtractor, Parameter, PartVariant, DatasheetExtraction
from database import DatabaseManager, DatabaseError
from mistral_processor import (
    MistralProcessor,
    MistralProcessorError,
    ExtractionResult as MistralExtractionResult, # Renamed to avoid clash if any
    QueryResult as MistralQueryResult,
    DEFAULT_MODEL as MISTRAL_DEFAULT_MODEL, # Renamed
    EXTRACTION_MODEL as MISTRAL_EXTRACTION_MODEL,
    QUERY_MODEL as MISTRAL_QUERY_MODEL
)
from ai_integration import (
    IntegratedExtractor,
    ExtractionStats,
    AIIntegrationError,
    MIN_PATTERN_CONFIDENCE,
    MIN_PARAMETERS_THRESHOLD,
    CONFIDENCE_BOOST
)
from batch_processor import (
    BatchProcessor,
    BatchResult,
    FileTask,
    ProcessingStatus
)
from auth import (
    AuthManager,
    User,
    Session,
    UserRole,
    AuthProvider,
    AuthError,
    RegistrationError,
    LoginError,
    SessionError,
    PermissionError,
    PASSWORD_MIN_LENGTH,
    PASSWORD_COMPLEXITY_REGEX,
    DEFAULT_ADMIN_EMAIL,
    DEFAULT_ADMIN_PASSWORD,
    TOKEN_EXPIRY_DAYS
)

# Import external libraries used in fixtures
import fitz  # PyMuPDF
from mistralai.models.chat_completion import ChatMessage, ChatCompletion, Choice


# --- Basic Data Fixtures ---

@pytest.fixture(scope="session")
def sample_pdf_text_content():
    """Provides sample text content similar to what's extracted from a PDF."""
    return """
    Product Datasheet: SuperTransceiver Model X1000
    Supplier: OptiCore Networks
    Part Number: OC-X1000-LR
    P/N: OC-X1000-SR

    Specifications:
    Operating Temperature Range: -5 to 70°C (Commercial)
    Data Rate: 10.3 Gbps
    Wavelength: 1310 nm
    Power Consumption: 1.5 W typical
    Reach: 10 km
    Supply Voltage: 3.3V
    Dimensions: 56.5mm x 13.7mm x 8.5mm

    Ordering Information:
    OC-X1000-LR: Long Reach Model
    OC-X1000-SR: Short Reach Model, Data Rate 10Gbps, Wavelength 850nm, Reach 300m
    """

@pytest.fixture(scope="session")
def sample_mistral_extraction_response_success():
    """A successful JSON response from Mistral for extraction."""
    return {
        "supplier": "TestCorp",
        "product_family": "Gadgets",
        "part_numbers": ["TC-GDT-001"],
        "parameters": {
            "performance": {
                "data_rate": {"value": "10", "unit": "Gbps", "description": "Data transmission speed"}
            },
            "environmental": {
                "temperature_range": {"value": "-10 to 70", "unit": "C", "description": "Operating temperature"}
            }
        },
        "confidence": 0.95
    }

@pytest.fixture(scope="session")
def sample_mistral_parameter_extraction_response_success():
    """A successful JSON response for parameter extraction."""
    return {
        "data_rate": {"value": "10", "unit": "Gbps", "confidence": 0.9},
        "temperature_range": {"value": "-10 to 70", "unit": "C", "confidence": 0.85}
    }

@pytest.fixture(scope="session")
def sample_mistral_query_response_success():
    """A successful response from Mistral for a query."""
    return "The highest data rate is 10 Gbps for part TC-GDT-001."

@pytest.fixture(scope="session")
def sample_extraction_data_v1():
    """Provides sample extraction data for a datasheet (version 1)."""
    return {
        "supplier": "SupplierA",
        "product_family": "FamilyX",
        "variants": [
            {
                "part_number": "PN001",
                "description": "Part 1 description",
                "parameters": [
                    {"name": "temp_range", "value": "-40 to 85", "unit": "C", "category": "environmental", "confidence": 0.9, "extraction_method": "pattern"},
                    {"name": "data_rate", "value": "10", "unit": "Gbps", "category": "performance", "confidence": 0.95, "extraction_method": "pattern"},
                ]
            }
        ],
        "extraction_date": datetime.now().isoformat(),
        "metadata": {"source": "test_v1"}
    }

@pytest.fixture(scope="session")
def sample_extraction_data_v2():
    """Provides sample extraction data for another datasheet (version 2)."""
    return {
        "supplier": "SupplierB",
        "product_family": "FamilyY",
        "variants": [
            {
                "part_number": "PN002",
                "description": "Part 2 description",
                "parameters": [
                    {"name": "temp_range", "value": "0 to 70", "unit": "C", "category": "environmental", "confidence": 0.8, "extraction_method": "ai"},
                    {"name": "voltage", "value": "3.3", "unit": "V", "category": "electrical", "confidence": 0.88, "extraction_method": "ai"},
                ]
            },
            {
                "part_number": "PN003",
                "description": "Part 3 description",
                "parameters": [
                    {"name": "data_rate", "value": "25", "unit": "Gbps", "category": "performance", "confidence": 0.92, "extraction_method": "merged"},
                ]
            }
        ],
        "extraction_date": datetime.now().isoformat(),
        "metadata": {"source": "test_v2"}
    }

@pytest.fixture(scope="session")
def sample_user_data():
    return {
        "email": "test@example.com",
        "username": "testuser",
        "password": "Password@123", # Compliant password
        "role": UserRole.VIEWER
    }

# --- PDF Creation Fixtures ---

@pytest.fixture(scope="function") # Function scope to ensure fresh file per test
def create_dummy_pdf():
    """Factory fixture to create dummy PDF files for testing."""
    created_files = []

    def _create_pdf(filename_prefix="test_pdf", content=None, metadata=None, empty=False, no_text=False):
        doc = fitz.open() # New empty PDF
        if not empty and not no_text:
            if content:
                page = doc.new_page()
                page.insert_text((50, 72), content, fontsize=11)
        elif not empty and no_text:
            doc.new_page() # Page with no text

        if metadata:
            doc.set_metadata(metadata)

        temp_file = tempfile.NamedTemporaryFile(prefix=filename_prefix, suffix=".pdf", delete=False)
        doc.save(temp_file.name)
        doc.close()
        created_files.append(temp_file.name)
        return temp_file.name

    yield _create_pdf

    for f_path in created_files:
        try:
            os.unlink(f_path)
        except OSError:
            pass

# --- Complex Data Object Fixtures ---

@pytest.fixture(scope="session")
def sample_pattern_extraction_result_strong():
    params = [
        Parameter(name="temp", value="0-70", unit="C", confidence=0.9, extraction_method="pattern"),
        Parameter(name="rate", value="10", unit="G", confidence=0.85, extraction_method="pattern"),
        Parameter(name="power", value="1", unit="W", confidence=0.92, extraction_method="pattern"),
        Parameter(name="reach", value="10", unit="km", confidence=0.88, extraction_method="pattern"),
    ]
    variant = PartVariant(part_number="PN123", parameters=params)
    return DatasheetExtraction(supplier="SupplierA", product_family="FamilyX", variants=[variant], metadata={"source":"pattern_strong"})

@pytest.fixture(scope="session")
def sample_pattern_extraction_result_weak_params():
    params = [Parameter(name="temp", value="0-70", unit="C", confidence=0.9, extraction_method="pattern")]
    variant = PartVariant(part_number="PN123", parameters=params)
    return DatasheetExtraction(supplier="SupplierA", product_family="FamilyX", variants=[variant], metadata={"source":"pattern_weak_params"})

@pytest.fixture(scope="session")
def sample_pattern_extraction_result_low_confidence():
    params = [
        Parameter(name="temp", value="0-70", unit="C", confidence=0.5, extraction_method="pattern"),
        Parameter(name="rate", value="10", unit="G", confidence=0.4, extraction_method="pattern"),
        Parameter(name="power", value="1", unit="W", confidence=0.3, extraction_method="pattern"),
    ]
    variant = PartVariant(part_number="PN123", parameters=params)
    return DatasheetExtraction(supplier="SupplierA", product_family="FamilyX", variants=[variant], metadata={"source":"pattern_low_conf"})

@pytest.fixture(scope="session")
def sample_pattern_extraction_result_unknown_supplier():
    params = [Parameter(name="temp", value="0-70", unit="C", confidence=0.9)]
    variant = PartVariant(part_number="PN123", parameters=params)
    return DatasheetExtraction(supplier="Unknown", product_family="FamilyX", variants=[variant])

@pytest.fixture(scope="session")
def sample_ai_data_dict_good():
    return {
        "supplier": "SupplierAI",
        "product_family": "FamilyAI",
        "variants": [
            {
                "part_number": "PN123",
                "description": "AI description",
                "parameters": [
                    {"name": "temp", "value": "-5-75", "unit": "C", "category": "env", "confidence": 0.95},
                    {"name": "voltage", "value": "5", "unit": "V", "category": "elec", "confidence": 0.90},
                ]
            },
            {
                "part_number": "PN456",
                "description": "AI new variant",
                "parameters": [
                    {"name": "rate", "value": "25", "unit": "G", "category": "perf", "confidence": 0.88},
                ]
            }
        ],
        "extraction_method": "ai",
        "extraction_time": 1.0,
        "extraction_date": datetime.now().isoformat()
    }

@pytest.fixture(scope="session")
def sample_ai_data_dict_different_params():
    return {
        "supplier": "SupplierAI",
        "product_family": "FamilyAI",
        "variants": [
            {
                "part_number": "PN123",
                "parameters": [
                    {"name": "humidity", "value": "10-90", "unit": "%", "category": "env", "confidence": 0.85},
                    {"name": "size", "value": "10x20", "unit": "mm", "category": "phys", "confidence": 0.90},
                ]
            }
        ],
        "extraction_method": "ai"
    }

# --- Mock Object Fixtures ---

@pytest.fixture
def mock_mistral_client():
    """Provides a MagicMock instance of MistralClient."""
    client = MagicMock()
    client.chat = MagicMock()
    client.chat.complete = MagicMock(
        return_value=ChatCompletion(
            id='cmpl-mock', object='chat.completion', created=123, model='mock-model',
            choices=[Choice(index=0, message=ChatMessage(role='assistant', content='{}'), finish_reason='stop')],
            usage=None
        )
    )
    client.models = MagicMock(return_value=[MagicMock(id="mistral-tiny")])
    return client

@pytest.fixture
def mock_pdf_extractor():
    """Provides a MagicMock instance of PDFExtractor."""
    extractor = MagicMock(spec=PDFExtractor)
    extractor.extract_from_file = MagicMock()
    extractor.extract_from_bytes = MagicMock()
    return extractor

@pytest.fixture
def mock_mistral_processor():
    """Provides an AsyncMock instance of MistralProcessor."""
    processor = AsyncMock(spec=MistralProcessor)
    processor.extract_from_pdf = AsyncMock(
        return_value={ # Default mock return for extract_from_pdf
            "supplier": "MockAISupplier", "product_family": "MockAIFamily",
            "variants": [{"part_number": "AIPN1", "parameters": []}],
            "extraction_method": "ai", "extraction_time": 0.1, "extraction_date": datetime.now().isoformat()
        }
    )
    processor.answer_query = MagicMock(
        return_value=MistralQueryResult(query="q", response="Mock AI Response", context_used="ctx", model_used="mock-model", execution_time=0.1)
    )
    processor.extract_parameters_from_text = AsyncMock(return_value={"mock_param": {"value": "1", "unit": "X"}})
    processor.validate_api_key = MagicMock(return_value=True)
    return processor

@pytest.fixture
def mock_db_manager():
    """Provides a MagicMock instance of DatabaseManager."""
    db_manager = MagicMock(spec=DatabaseManager)
    db_manager.save_datasheet = MagicMock(return_value=1) # Returns a dummy datasheet_id
    db_manager.existing_hashes = {} # For _check_file_exists simulation

    def mock_get_connection_context_manager(*args, **kwargs):
        conn_mock = MagicMock()
        cursor_mock = MagicMock()
        def mock_execute_for_hash_check(query, params):
            if "SELECT id FROM datasheets WHERE file_hash = ?" in query:
                file_hash_to_check = params[0]
                if file_hash_to_check in db_manager.existing_hashes:
                    cursor_mock.fetchone.return_value = (db_manager.existing_hashes[file_hash_to_check],)
                else:
                    cursor_mock.fetchone.return_value = None
            else:
                cursor_mock.fetchone.return_value = None
        cursor_mock.execute = MagicMock(side_effect=mock_execute_for_hash_check)
        conn_mock.cursor.return_value = cursor_mock
        mock_cm = MagicMock()
        mock_cm.__enter__.return_value = conn_mock
        mock_cm.__exit__.return_value = None
        return mock_cm

    db_manager.get_connection = MagicMock(side_effect=mock_get_connection_context_manager)
    return db_manager

# --- Instance Fixtures ---

@pytest.fixture
def pdf_extractor_instance():
    """Returns an instance of PDFExtractor."""
    return PDFExtractor(debug=True)

@pytest.fixture
def mistral_processor_instance(mock_mistral_client):
    """Initializes MistralProcessor with a mock client."""
    processor = MistralProcessor(api_key="test_api_key", debug=True)
    processor.client = mock_mistral_client
    return processor

@pytest.fixture
def in_memory_db_manager():
    """Returns a DatabaseManager instance with an in-memory SQLite database."""
    return DatabaseManager(db_file=":memory:", debug=True)

@pytest.fixture
def temp_db_manager():
    """Returns a DatabaseManager instance with a temporary file-based SQLite database."""
    temp_dir = tempfile.mkdtemp()
    db_path = os.path.join(temp_dir, "test_datasheet_system.db")
    
    original_backup_dir_attr = 'BACKUP_DIR'
    # Use a class variable if defined, otherwise a default string path.
    # This assumes BACKUP_DIR is a static/class variable in DatabaseManager.
    # If it's an instance variable, this approach needs adjustment or the DatabaseManager needs to be patchable.
    original_backup_dir_val = getattr(DatabaseManager, original_backup_dir_attr, 'db_backups') 
    
    # Modify class variable carefully for the test
    setattr(DatabaseManager, original_backup_dir_attr, os.path.join(temp_dir, "db_backups_test"))
    os.makedirs(getattr(DatabaseManager, original_backup_dir_attr), exist_ok=True)

    manager = DatabaseManager(db_file=db_path, debug=True)
    yield manager
    
    del manager # Help release file lock
    try:
        shutil.rmtree(temp_dir)
    except Exception as e:
        print(f"Warning: Could not remove temp dir {temp_dir}: {e}")
    setattr(DatabaseManager, original_backup_dir_attr, original_backup_dir_val) # Restore

@pytest.fixture
def integrated_extractor_instance(mock_pdf_extractor, mock_mistral_processor):
    """Initializes IntegratedExtractor with mock dependencies."""
    return IntegratedExtractor(
        pattern_extractor=mock_pdf_extractor,
        ai_extractor=mock_mistral_processor,
        debug=True
    )

@pytest.fixture
def integrated_extractor_no_ai(mock_pdf_extractor):
    """Initializes IntegratedExtractor without an AI processor."""
    return IntegratedExtractor(
        pattern_extractor=mock_pdf_extractor,
        ai_extractor=None,
        debug=True
    )

@pytest.fixture
def batch_processor_instance(mock_db_manager, integrated_extractor_instance, mock_pattern_extractor):
    """Initializes BatchProcessor with mock dependencies.
       Note: integrated_extractor_instance already has mock_pattern_extractor internally if created that way.
       If IntegratedExtractor takes pattern_extractor explicitly, pass mock_pattern_extractor.
    """
    return BatchProcessor(
        db_manager=mock_db_manager,
        integrated_extractor=integrated_extractor_instance, # This already has a pattern_extractor
        pattern_extractor=mock_pattern_extractor, # Or pass integrated_extractor_instance.pattern_extractor
        debug=True
    )


@pytest.fixture
def batch_processor_pattern_only(mock_db_manager, mock_pattern_extractor):
    """Initializes BatchProcessor for pattern extraction only."""
    return BatchProcessor(
        db_manager=mock_db_manager,
        integrated_extractor=None,
        pattern_extractor=mock_pattern_extractor,
        debug=True
    )

@pytest.fixture
def in_memory_auth_manager():
    """Returns an AuthManager instance with an in-memory SQLite database."""
    with patch.dict(os.environ, {}, clear=True): # Ensure no env var for secret key
        manager = AuthManager(db_file=":memory:", secret_key="test_secret_key_fixed_for_tests", debug=True)
    return manager

@pytest.fixture
def temp_db_auth_manager():
    """Returns an AuthManager instance with a temporary file-based SQLite database."""
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    with patch.dict(os.environ, {}, clear=True):
        manager = AuthManager(db_file=db_path, secret_key="test_secret_key_temp_db", debug=True)
    yield manager
    try:
        os.unlink(db_path)
    except OSError:
        pass

@pytest.fixture
def registered_user(in_memory_auth_manager: AuthManager, sample_user_data):
    """Registers a sample user and returns the User object."""
    return in_memory_auth_manager.register_user(**sample_user_data)

# --- File/Directory Creation Fixtures ---

@pytest.fixture(scope="function")
def temp_files_factory():
    """Factory to create temporary files for testing."""
    created_files = []
    def _create_files(num_files, prefix="test_file_", content_prefix="Content for file"):
        paths = []
        for i in range(num_files):
            fd, path = tempfile.mkstemp(suffix=".pdf", prefix=f"{prefix}{i}_")
            with os.fdopen(fd, 'w') as tmp:
                tmp.write(f"{content_prefix} {i}")
            paths.append(path)
            created_files.append(path)
        return paths
    yield _create_files
    for f_path in created_files:
        try:
            os.remove(f_path)
        except OSError:
            pass
