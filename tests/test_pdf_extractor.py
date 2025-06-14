#!/usr/bin/env python3
"""
Unit Tests for the PDF Extractor Module (pdf_extractor.py)
"""

import pytest
import os
import tempfile
from datetime import datetime
import fitz # PyMuPDF
import pdfplumber
import unittest # For mock.ANY if needed

# Module to test
from pdf_extractor import PDFExtractor, Parameter, PartVariant, DatasheetExtraction

# --- Fixtures ---
# These are expected to be in conftest.py or defined here if this file is standalone.
# For this exercise, we assume they are available from a conftest.py.
# If running this file standalone, you'd need to define:
# - pdf_extractor_instance
# - sample_pdf_text_content
# - create_dummy_pdf

# --- Test Cases ---

def test_pdf_extractor_initialization(pdf_extractor_instance):
    """Test if PDFExtractor initializes correctly."""
    assert isinstance(pdf_extractor_instance, PDFExtractor)
    assert pdf_extractor_instance.debug is True
    assert pdf_extractor_instance.ai_processor is None # Default

def test_parameter_dataclass_defaults():
    """Test Parameter dataclass default values."""
    param = Parameter(name="test_param", value="10")
    assert param.name == "test_param"
    assert param.value == "10"
    assert param.unit == ""
    assert param.category == "general"
    assert param.confidence == 1.0
    assert param.extraction_method == "pattern" # Default value

def test_part_variant_dataclass_defaults():
    """Test PartVariant dataclass default values."""
    param = Parameter(name="test_param", value="10")
    variant = PartVariant(part_number="PN123", parameters=[param])
    assert variant.part_number == "PN123"
    assert variant.parameters == [param]
    assert variant.description == ""

def test_datasheet_extraction_dataclass_defaults():
    """Test DatasheetExtraction dataclass default values."""
    extraction = DatasheetExtraction(supplier="TestSupplier", product_family="TestFamily", variants=[])
    assert extraction.supplier == "TestSupplier"
    assert extraction.product_family == "TestFamily"
    assert isinstance(extraction.extraction_date, datetime)
    assert extraction.metadata is None # Default is None, to_dict makes it {}

def test_datasheet_extraction_to_dict(sample_pdf_text_content):
    """Test the to_dict method of DatasheetExtraction."""
    param1 = Parameter(name="data_rate", value="10", unit="Gbps", category="performance", confidence=0.9, extraction_method="pattern")
    variant1 = PartVariant(part_number="PN001", parameters=[param1], description="Variant 1")
    extraction_time = datetime.now()
    extraction = DatasheetExtraction(
        supplier="TestCorp",
        product_family="Transceivers",
        variants=[variant1],
        extraction_date=extraction_time,
        metadata={"author": "Test Author"}
    )
    expected_dict = {
        "supplier": "TestCorp",
        "product_family": "Transceivers",
        "variants": [
            {
                "part_number": "PN001",
                "description": "Variant 1",
                "parameters": [
                    {
                        "name": "data_rate",
                        "value": "10",
                        "unit": "Gbps",
                        "category": "performance",
                        "confidence": 0.9,
                        "extraction_method": "pattern"
                    }
                ]
            }
        ],
        "extraction_date": extraction_time.isoformat(),
        "metadata": {"author": "Test Author"}
    }
    assert extraction.to_dict() == expected_dict

def test_extract_text_from_valid_pdf(pdf_extractor_instance, create_dummy_pdf):
    """Test _extract_text with a PDF containing text."""
    pdf_content = "This is a test PDF with some text."
    pdf_path = create_dummy_pdf(content=pdf_content)
    extracted_text = pdf_extractor_instance._extract_text(pdf_path)
    assert pdf_content in extracted_text

def test_extract_text_from_empty_pdf(pdf_extractor_instance, create_dummy_pdf):
    """Test _extract_text with an empty PDF (no pages)."""
    pdf_path = create_dummy_pdf(empty=True)
    extracted_text = pdf_extractor_instance._extract_text(pdf_path)
    assert extracted_text == ""

def test_extract_text_from_no_text_pdf(pdf_extractor_instance, create_dummy_pdf):
    """Test _extract_text with a PDF that has pages but no extractable text."""
    pdf_path = create_dummy_pdf(no_text=True)
    extracted_text = pdf_extractor_instance._extract_text(pdf_path)
    assert len(extracted_text.strip()) == 0

def test_extract_metadata_from_pdf(pdf_extractor_instance, create_dummy_pdf):
    """Test _extract_metadata with a PDF having metadata."""
    metadata_content = {"author": "Test Author", "title": "Test Title"}
    pdf_path = create_dummy_pdf(content="Some content", metadata=metadata_content)
    metadata = pdf_extractor_instance._extract_metadata(pdf_path)
    assert metadata.get("author") == "Test Author"
    assert metadata.get("title") == "Test Title"

def test_identify_supplier(pdf_extractor_instance, sample_pdf_text_content):
    """Test supplier identification logic."""
    assert pdf_extractor_instance._identify_supplier(sample_pdf_text_content, "some_file.pdf", {}) == "OptiCore Networks"
    assert pdf_extractor_instance._identify_supplier("No supplier here.", "Finisar_datasheet.pdf", {}) == "Finisar"
    assert pdf_extractor_instance._identify_supplier("No supplier here.", "some_file.pdf", {"author": "Cisco Systems"}) == "Cisco"
    assert pdf_extractor_instance._identify_supplier("No supplier here.", "some_file.pdf", {}) == "Unknown"

def test_identify_product_family(pdf_extractor_instance, sample_pdf_text_content):
    """Test product family identification logic."""
    assert pdf_extractor_instance._identify_product_family(sample_pdf_text_content, {}) == "Optical Transceivers"
    assert pdf_extractor_instance._identify_product_family("No family here.", {"title": "Network Switch Manual"}) == "Network Switches"
    assert pdf_extractor_instance._identify_product_family("No family here.", {}) == "General Electronics"

def test_extract_part_numbers(pdf_extractor_instance, sample_pdf_text_content):
    """Test part number extraction."""
    part_numbers = pdf_extractor_instance._extract_part_numbers(sample_pdf_text_content)
    assert "OC-X1000-LR" in part_numbers
    assert "OC-X1000-SR" in part_numbers
    assert len(part_numbers) == 2

def test_extract_parameters_known_patterns(pdf_extractor_instance, sample_pdf_text_content):
    """Test extraction of various parameters using known patterns."""
    parameters = pdf_extractor_instance._extract_parameters(sample_pdf_text_content, "OC-X1000-LR")
    param_dict = {p.name: p for p in parameters}

    assert "temperature_range" in param_dict
    assert param_dict["temperature_range"].value == "-5 to 70"
    assert param_dict["temperature_range"].unit == "°C"
    assert param_dict["temperature_range"].category == "environmental"
    assert param_dict["temperature_range"].extraction_method == "pattern"

    assert "data_rate" in param_dict
    assert param_dict["data_rate"].value == "10.3" 
    assert param_dict["data_rate"].unit == "Gbps"
    assert param_dict["data_rate"].category == "performance"

    assert "wavelength" in param_dict
    assert param_dict["wavelength"].value == "1310"
    assert param_dict["wavelength"].unit == "nm"
    assert param_dict["wavelength"].category == "optical"

    assert "power_consumption" in param_dict
    assert param_dict["power_consumption"].value == "1.5"
    assert param_dict["power_consumption"].unit == "W"
    assert param_dict["power_consumption"].category == "electrical"

    assert "reach" in param_dict
    assert param_dict["reach"].value == "10"
    assert param_dict["reach"].unit == "km"
    assert param_dict["reach"].category == "performance"

    assert "voltage" in param_dict
    assert param_dict["voltage"].value == "3.3"
    assert param_dict["voltage"].unit == "V"
    assert param_dict["voltage"].category == "electrical"

    assert "dimensions" in param_dict
    assert param_dict["dimensions"].value == "56.5x13.7x8.5"
    assert param_dict["dimensions"].unit == "mm"
    assert param_dict["dimensions"].category == "physical"

def test_extract_parameters_no_matches(pdf_extractor_instance):
    """Test parameter extraction when no patterns match."""
    text = "This document contains no relevant technical specifications."
    parameters = pdf_extractor_instance._extract_parameters(text, "ANY_PN")
    assert len(parameters) == 0

def test_unit_standardization(pdf_extractor_instance):
    """Test the unit standardization logic."""
    text_gbits = "Data Rate: 10 Gbit/s"
    params_gbits = pdf_extractor_instance._extract_parameters(text_gbits, "PN_GBITS")
    assert len(params_gbits) > 0
    data_rate_param_gbits = next((p for p in params_gbits if p.name == "data_rate"), None)
    assert data_rate_param_gbits is not None
    assert data_rate_param_gbits.unit == "Gbps"

    text_degc = "Operating Temp: 0 deg C to 70 deg C"
    params_degc = pdf_extractor_instance._extract_parameters(text_degc, "PN_DEGC")
    assert len(params_degc) > 0
    temp_param_degc = next((p for p in params_degc if p.name == "temperature_range"), None)
    assert temp_param_degc is not None
    assert temp_param_degc.unit == "°C"

def test_extract_from_file_valid_pdf(pdf_extractor_instance, create_dummy_pdf, sample_pdf_text_content):
    """Test the main extract_from_file method with a valid PDF."""
    pdf_path = create_dummy_pdf(filename_prefix="valid_datasheet", content=sample_pdf_text_content)
    extraction_result = pdf_extractor_instance.extract_from_file(pdf_path)

    assert isinstance(extraction_result, DatasheetExtraction)
    assert extraction_result.supplier == "OptiCore Networks"
    assert extraction_result.product_family == "Optical Transceivers"
    assert len(extraction_result.variants) > 0 
    found_data_rate = False
    for variant in extraction_result.variants:
        for param in variant.parameters:
            if param.name == "data_rate":
                found_data_rate = True
                assert param.extraction_method == "pattern"
                break
        if found_data_rate:
            break
    assert found_data_rate

def test_extract_from_file_non_existent(pdf_extractor_instance):
    """Test extract_from_file with a non-existent file path."""
    with pytest.raises(Exception): 
        pdf_extractor_instance.extract_from_file("non_existent_file.pdf")

def test_extract_from_file_corrupted_pdf(pdf_extractor_instance, create_dummy_pdf):
    """Test extract_from_file with a (simulated) corrupted PDF."""
    temp_file = tempfile.NamedTemporaryFile(prefix="corrupted", suffix=".pdf", delete=False)
    temp_file.write(b"This is not a PDF content.")
    temp_file.close()
    pdf_path = temp_file.name

    with pytest.raises(Exception): 
        pdf_extractor_instance.extract_from_file(pdf_path)
    os.unlink(pdf_path)


def test_extract_from_bytes_valid_pdf(pdf_extractor_instance, create_dummy_pdf, sample_pdf_text_content):
    """Test the extract_from_bytes method."""
    pdf_path = create_dummy_pdf(filename_prefix="bytes_test", content=sample_pdf_text_content)
    with open(pdf_path, "rb") as f:
        pdf_bytes = f.read()

    extraction_result = pdf_extractor_instance.extract_from_bytes(pdf_bytes, "bytes_test.pdf")
    assert isinstance(extraction_result, DatasheetExtraction)
    assert extraction_result.supplier == "OptiCore Networks"
    assert len(extraction_result.variants) > 0

def test_extract_tables_with_pdfplumber(pdf_extractor_instance, create_dummy_pdf):
    """Test table extraction using pdfplumber."""
    table_like_content = """
    Parameter | Value | Unit
    Data Rate | 10 | Gbps
    Temp Range | -5 to 70 | C
    """
    pdf_path = create_dummy_pdf(content=table_like_content)
    
    try:
        import pdfplumber
    except ImportError:
        pytest.skip("pdfplumber not installed, skipping table extraction test")

    tables = pdf_extractor_instance.extract_tables(pdf_path)
    assert isinstance(tables, list)
    # If pdfplumber finds the table-like structure:
    if tables:
        assert len(tables) > 0
        first_table_first_row = tables[0]['data'] # Assuming extract_tables returns list of dicts with 'data'
        assert 'Parameter' in first_table_first_row 
        assert first_table_first_row['Parameter'] == 'Data Rate'


def test_default_part_number_if_none_extracted(pdf_extractor_instance, create_dummy_pdf):
    """Test if a default part number is generated from filename if none are extracted."""
    pdf_content = "Some random text without any part number patterns like P/N or Model No."
    filename = "MyProduct_RevA_Datasheet.pdf"
    # Create a dummy PDF with a specific name structure for this test
    # The create_dummy_pdf fixture uses a prefix, so we'll handle the name more directly here.
    temp_dir = tempfile.gettempdir()
    pdf_path_for_test = os.path.join(temp_dir, filename)
    
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50,72), pdf_content)
    doc.save(pdf_path_for_test)
    doc.close()

    extraction_result = pdf_extractor_instance.extract_from_file(pdf_path_for_test)
    
    assert len(extraction_result.variants) == 1
    # The logic in PDFExtractor._extract_part_numbers or its caller should handle this.
    # If no explicit P/N found, it defaults to a sanitized filename.
    expected_default_pn = "MyProduct_RevA_Datasheet" # Based on current logic
    assert extraction_result.variants[0].part_number == expected_default_pn

    os.unlink(pdf_path_for_test) # Clean up the manually created file

if __name__ == "__main__":
    pytest.main()
