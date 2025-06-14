#!/usr/bin/env python3
"""
Unit Tests for the MistralProcessor Module (mistral_processor.py)
"""

import pytest
import asyncio
import json
from unittest.mock import MagicMock, patch, mock_open, ANY
from datetime import datetime

# Module to test
from mistral_processor import (
    MistralProcessor,
    MistralProcessorError,
    ExtractionResult as MistralExtractionResultInternal, # Internal dataclass from mistral_processor
    QueryResult,
    DEFAULT_MODEL,
    EXTRACTION_MODEL,
    QUERY_MODEL
)
# Assuming DatasheetExtraction is the standardized output format if needed for comparison
# from pdf_extractor import DatasheetExtraction # If needed for comparing converted output

from mistralai.exceptions import MistralAPIError, MistralRateLimitError, MistralConnectionError
from mistralai.models.chat_completion import ChatMessage, ChatCompletion, Choice, ChatCompletionMessage, CompletionUsage

# --- Fixtures are expected from conftest.py ---
# - mock_mistral_client
# - mistral_processor_instance
# - sample_pdf_text_content
# - sample_mistral_extraction_response_success (this is the AI's direct JSON output)
# - sample_mistral_parameter_extraction_response_success
# - sample_mistral_query_response_success

# --- Test Cases ---

def test_initialization(mock_mistral_client):
    """Test MistralProcessor initialization."""
    # Test with explicit model
    processor = MistralProcessor(api_key="test_api_key", model="test_model", debug=True)
    assert processor.api_key == "test_api_key"
    assert processor.model == "test_model" # This is the general model
    assert processor.extraction_model == EXTRACTION_MODEL # Specific model for extraction
    assert processor.query_model == QUERY_MODEL # Specific model for query
    assert processor.debug is True
    assert processor.client is not None

    # Test with default model
    processor_default = MistralProcessor(api_key="test_api_key_default")
    assert processor_default.model == DEFAULT_MODEL


@patch('mistral_processor.MistralClient') # Patch where MistralClient is instantiated
def test_validate_api_key_success(MockMistralClientConstructor, mistral_processor_instance: MistralProcessor):
    """Test API key validation success."""
    # The mistral_processor_instance fixture already has a mock client injected.
    # We need to ensure that client's methods behave as expected.
    mock_client_instance = mistral_processor_instance.client
    mock_client_instance.models.list = MagicMock(return_value=MagicMock(data=[MagicMock(id="mistral-tiny")]))

    assert mistral_processor_instance.validate_api_key() is True
    mock_client_instance.models.list.assert_called_once()

@patch('mistral_processor.MistralClient')
def test_validate_api_key_failure(MockMistralClientConstructor, mistral_processor_instance: MistralProcessor):
    """Test API key validation failure."""
    mock_client_instance = mistral_processor_instance.client
    mock_client_instance.models.list = MagicMock(side_effect=MistralAPIError(message="Auth failed"))

    assert mistral_processor_instance.validate_api_key() is False
    mock_client_instance.models.list.assert_called_once()

@pytest.mark.asyncio
@patch('mistral_processor.MistralProcessor._extract_text_from_pdf_path') # Mock the internal helper
async def test_extract_from_pdf_success(
    mock_internal_extract_text,
    mistral_processor_instance: MistralProcessor,
    sample_pdf_text_content,
    sample_mistral_extraction_response_success # This is the direct AI JSON output
):
    """Test successful PDF data extraction and conversion to standard format."""
    mock_internal_extract_text.return_value = sample_pdf_text_content
    
    # Mock Mistral API response for the main extraction
    mock_chat_message = ChatCompletionMessage(role='assistant', content=json.dumps(sample_mistral_extraction_response_success), tool_calls=None)
    mock_choice = Choice(index=0, message=mock_chat_message, finish_reason='stop', logprobs=None)
    mock_completion = ChatCompletion(id='cmpl-test', object='chat.completion', created=123, model=EXTRACTION_MODEL, choices=[mock_choice], usage=MagicMock(spec=CompletionUsage))
    mistral_processor_instance.client.chat.return_value = mock_completion # Mock the chat method directly

    file_content = b"dummy pdf content"
    filename = "test.pdf"
    
    # The method now returns a dict (standard format)
    standard_result_dict = await mistral_processor_instance.extract_from_pdf(file_content, filename)

    assert standard_result_dict["supplier"] == "TestCorp"
    assert standard_result_dict["product_family"] == "Gadgets"
    assert len(standard_result_dict["variants"]) == 1
    assert standard_result_dict["variants"][0]["part_number"] == "TC-GDT-001"
    
    # Check parameters within the standard format
    params_list = standard_result_dict["variants"][0]["parameters"]
    assert len(params_list) == 2
    data_rate_param = next(p for p in params_list if p["name"] == "data_rate")
    temp_param = next(p for p in params_list if p["name"] == "temperature_range")

    assert data_rate_param["value"] == "10"
    assert data_rate_param["unit"] == "Gbps"
    assert data_rate_param["category"] == "performance" # From the structure of sample_mistral_extraction_response_success
    assert data_rate_param["confidence"] == 0.95 # Confidence from the overall AI extraction

    assert temp_param["value"] == "-10 to 70"
    assert temp_param["unit"] == "C"
    assert temp_param["category"] == "environmental"
    assert temp_param["confidence"] == 0.95

    mock_internal_extract_text.assert_called_once()
    mistral_processor_instance.client.chat.assert_called_once()
    # Check the prompt structure for the call
    args, kwargs = mistral_processor_instance.client.chat.call_args
    messages = kwargs['messages']
    assert messages[1]['role'] == 'user'
    assert "DATASHEET CONTENT:" in messages[1]['content']
    assert sample_pdf_text_content in messages[1]['content']


@pytest.mark.asyncio
@patch('mistral_processor.MistralProcessor._extract_text_from_pdf_path')
async def test_extract_from_pdf_api_error(mock_internal_extract_text, mistral_processor_instance: MistralProcessor, sample_pdf_text_content):
    """Test PDF data extraction with MistralAPIError."""
    mock_internal_extract_text.return_value = sample_pdf_text_content
    mistral_processor_instance.client.chat.side_effect = MistralAPIError(message="API call failed")

    with pytest.raises(MistralProcessorError, match="Mistral API error: API call failed"):
        await mistral_processor_instance.extract_from_pdf(b"dummy", "test.pdf")

@pytest.mark.asyncio
@patch('mistral_processor.MistralProcessor._extract_text_from_pdf_path')
async def test_extract_from_pdf_json_error(mock_internal_extract_text, mistral_processor_instance: MistralProcessor, sample_pdf_text_content):
    """Test PDF data extraction with malformed JSON response."""
    mock_internal_extract_text.return_value = sample_pdf_text_content
    mock_chat_message = ChatCompletionMessage(role='assistant', content="this is not json", tool_calls=None)
    mock_choice = Choice(index=0, message=mock_chat_message, finish_reason='stop', logprobs=None)
    mock_completion = ChatCompletion(id='cmpl-test', object='chat.completion', created=123, model=EXTRACTION_MODEL, choices=[mock_choice], usage=MagicMock(spec=CompletionUsage))
    mistral_processor_instance.client.chat.return_value = mock_completion

    with pytest.raises(MistralProcessorError, match="Failed to parse JSON response from Mistral AI"):
        await mistral_processor_instance.extract_from_pdf(b"dummy", "test.pdf")

@pytest.mark.asyncio
@patch('mistral_processor.MistralProcessor._extract_text_from_pdf_path')
async def test_extract_from_pdf_text_extraction_failure(mock_internal_extract_text, mistral_processor_instance: MistralProcessor):
    """Test PDF data extraction when internal text extraction fails."""
    mock_internal_extract_text.side_effect = Exception("PDF parsing failed")

    with pytest.raises(MistralProcessorError, match="Failed to extract data from PDF: PDF parsing failed"):
        await mistral_processor_instance.extract_from_pdf(b"dummy", "test.pdf")

@pytest.mark.asyncio
async def test_extract_parameters_from_text_success(
    mistral_processor_instance: MistralProcessor,
    sample_pdf_text_content,
    sample_mistral_parameter_extraction_response_success # This is AI's direct JSON output
):
    """Test successful parameter extraction from text."""
    mock_chat_message = ChatCompletionMessage(role='assistant', content=json.dumps(sample_mistral_parameter_extraction_response_success), tool_calls=None)
    mock_choice = Choice(index=0, message=mock_chat_message, finish_reason='stop', logprobs=None)
    mock_completion = ChatCompletion(id='cmpl-test', object='chat.completion', created=123, model=EXTRACTION_MODEL, choices=[mock_choice], usage=MagicMock(spec=CompletionUsage))
    mistral_processor_instance.client.chat.return_value = mock_completion

    parameters_dict = await mistral_processor_instance.extract_parameters_from_text(sample_pdf_text_content, ["data_rate", "temperature_range"])
    
    assert isinstance(parameters_dict, dict)
    assert "data_rate" in parameters_dict
    assert parameters_dict["data_rate"]["value"] == "10"
    assert parameters_dict["data_rate"]["confidence"] == 0.9
    assert "temperature_range" in parameters_dict
    assert parameters_dict["temperature_range"]["unit"] == "C"
    assert parameters_dict["temperature_range"]["confidence"] == 0.85
    mistral_processor_instance.client.chat.assert_called_once()
    # Check prompt
    args, kwargs = mistral_processor_instance.client.chat.call_args
    messages = kwargs['messages']
    assert "extract the following parameters: data_rate, temperature_range" in messages[1]['content']


@pytest.mark.asyncio
async def test_extract_parameters_from_text_api_error(mistral_processor_instance: MistralProcessor, sample_pdf_text_content):
    """Test parameter extraction from text with MistralAPIError."""
    mistral_processor_instance.client.chat.side_effect = MistralAPIError(message="Param API error")
    with pytest.raises(MistralProcessorError, match="Mistral API error: Param API error"):
        await mistral_processor_instance.extract_parameters_from_text(sample_pdf_text_content, ["data_rate"])

@pytest.mark.asyncio
async def test_extract_parameters_from_text_json_error(mistral_processor_instance: MistralProcessor, sample_pdf_text_content):
    """Test parameter extraction from text with malformed JSON."""
    mock_chat_message = ChatCompletionMessage(role='assistant', content="not json at all", tool_calls=None)
    mock_choice = Choice(index=0, message=mock_chat_message, finish_reason='stop', logprobs=None)
    mock_completion = ChatCompletion(id='cmpl-test', object='chat.completion', created=123, model=EXTRACTION_MODEL, choices=[mock_choice], usage=MagicMock(spec=CompletionUsage))
    mistral_processor_instance.client.chat.return_value = mock_completion
    with pytest.raises(MistralProcessorError, match="Failed to parse JSON response from Mistral AI"):
        await mistral_processor_instance.extract_parameters_from_text(sample_pdf_text_content, ["data_rate"])

def test_answer_query_success(mistral_processor_instance: MistralProcessor, sample_mistral_query_response_success):
    """Test successful query answering."""
    mock_chat_message = ChatCompletionMessage(role='assistant', content=sample_mistral_query_response_success, tool_calls=None)
    mock_choice = Choice(index=0, message=mock_chat_message, finish_reason='stop', logprobs=None)
    mock_completion = ChatCompletion(id='cmpl-test', object='chat.completion', created=123, model=QUERY_MODEL, choices=[mock_choice], usage=MagicMock(spec=CompletionUsage))
    mistral_processor_instance.client.chat.return_value = mock_completion

    query = "What is the data rate?"
    context = "Data rate is 10 Gbps."
    result = mistral_processor_instance.answer_query(query, context)

    assert isinstance(result, QueryResult)
    assert result.response == sample_mistral_query_response_success
    assert result.query == query
    assert result.model_used == QUERY_MODEL
    mistral_processor_instance.client.chat.assert_called_once()
    # Check prompt
    args, kwargs = mistral_processor_instance.client.chat.call_args
    messages = kwargs['messages']
    assert "CONTEXT:" in messages[1]['content']
    assert context in messages[1]['content']
    assert "QUESTION:" in messages[1]['content']
    assert query in messages[1]['content']

def test_answer_query_api_error(mistral_processor_instance: MistralProcessor):
    """Test query answering with MistralAPIError."""
    mistral_processor_instance.client.chat.side_effect = MistralAPIError(message="Query API error")
    with pytest.raises(MistralProcessorError, match="Mistral API error: Query API error"):
        mistral_processor_instance.answer_query("test query", "test context")

def test_extract_json_from_response_helper(mistral_processor_instance: MistralProcessor):
    """Test _extract_json_from_response helper with various inputs."""
    assert mistral_processor_instance._extract_json_from_response('{"key": "value"}') == {"key": "value"}
    assert mistral_processor_instance._extract_json_from_response('```json\n{"key": "value"}\n```') == {"key": "value"}
    assert mistral_processor_instance._extract_json_from_response('```\n{"key": "value"}\n```') == {"key": "value"}
    assert mistral_processor_instance._extract_json_from_response('Some text. ```json\n{"key": "value"}\n``` More text.') == {"key": "value"}
    
    with pytest.raises(json.JSONDecodeError):
        mistral_processor_instance._extract_json_from_response('this is not json')
    
    with pytest.raises(json.JSONDecodeError):
        mistral_processor_instance._extract_json_from_response('```json\nnot json inside\n```')

    # Test case where JSON is present but not in markdown
    assert mistral_processor_instance._extract_json_from_response('The result is: {"key": "value"}.') == {"key": "value"}
    # Test case where there are multiple JSON objects, it should pick the first valid one or the one in markdown
    assert mistral_processor_instance._extract_json_from_response('{"a":1} then ```json\n{"b":2}\n```') == {"b": 2} # Prefers markdown
    assert mistral_processor_instance._extract_json_from_response('{"a":1} then {"b":2}') == {"a": 1} # Picks first if no markdown


def test_convert_to_standard_format_helper(mistral_processor_instance: MistralProcessor, sample_mistral_extraction_response_success):
    """Test _convert_to_standard_format helper for converting AI output."""
    # sample_mistral_extraction_response_success is the AI's direct JSON output
    ai_internal_result = MistralExtractionResultInternal(
        supplier=sample_mistral_extraction_response_success["supplier"],
        product_family=sample_mistral_extraction_response_success["product_family"],
        part_numbers=sample_mistral_extraction_response_success["part_numbers"],
        parameters=sample_mistral_extraction_response_success["parameters"],
        raw_response=json.dumps(sample_mistral_extraction_response_success),
        confidence=sample_mistral_extraction_response_success["confidence"],
        extraction_time=0.5,
        filename="test.pdf" # Added filename to internal result
    )
    
    standard_format_dict = mistral_processor_instance._convert_ai_output_to_standard_format(ai_internal_result)

    assert standard_format_dict["supplier"] == "TestCorp"
    assert standard_format_dict["product_family"] == "Gadgets"
    assert len(standard_format_dict["variants"]) == 1
    variant1 = standard_format_dict["variants"][0]
    assert variant1["part_number"] == "TC-GDT-001"
    
    params_list = variant1["parameters"]
    assert len(params_list) == 2
    
    data_rate_param = next(p for p in params_list if p["name"] == "data_rate")
    assert data_rate_param["value"] == "10"
    assert data_rate_param["unit"] == "Gbps"
    assert data_rate_param["category"] == "performance" # Derived from AI output structure
    assert data_rate_param["confidence"] == 0.95 # Propagated from overall AI confidence
    assert data_rate_param["extraction_method"] == "ai" # Should be marked as AI

    temp_param = next(p for p in params_list if p["name"] == "temperature_range")
    assert temp_param["value"] == "-10 to 70"
    assert temp_param["unit"] == "C"
    assert temp_param["category"] == "environmental"
    assert temp_param["confidence"] == 0.95
    assert temp_param["extraction_method"] == "ai"

    assert standard_format_dict["extraction_method"] == "ai" # Top-level method
    assert standard_format_dict["extraction_time"] == 0.5


def test_convert_to_standard_format_no_part_numbers(mistral_processor_instance: MistralProcessor):
    """Test _convert_to_standard_format when AI extracts no part numbers."""
    ai_response_no_pn = {
        "supplier": "TestSupplier", "product_family": "TestFamily", "part_numbers": [],
        "parameters": {"electrical": {"voltage": {"value": "5", "unit": "V"}}}, "confidence": 0.8
    }
    ai_internal_result = MistralExtractionResultInternal(
        supplier=ai_response_no_pn["supplier"], product_family=ai_response_no_pn["product_family"],
        part_numbers=ai_response_no_pn["part_numbers"], parameters=ai_response_no_pn["parameters"],
        raw_response=json.dumps(ai_response_no_pn), confidence=0.8, extraction_time=0.1, filename="test_no_pn.pdf"
    )
    standard_format_dict = mistral_processor_instance._convert_ai_output_to_standard_format(ai_internal_result)
    
    assert len(standard_format_dict["variants"]) == 1 # Should create one default variant
    assert standard_format_dict["variants"][0]["part_number"] == "test_no_pn" # Default from filename
    assert len(standard_format_dict["variants"][0]["parameters"]) == 1
    assert standard_format_dict["variants"][0]["parameters"][0]["name"] == "voltage"


def test_create_extraction_prompt_helper(mistral_processor_instance: MistralProcessor):
    """Test _create_extraction_prompt helper for prompt generation."""
    prompt = mistral_processor_instance._create_extraction_prompt("text content", "file.pdf")
    assert "DATASHEET CONTENT:" in prompt and "text content" in prompt and "file.pdf" in prompt
    assert "Extract the following information in JSON format:" in prompt
    assert '"supplier":' in prompt and '"parameters":' in prompt

def test_create_query_prompt_helper(mistral_processor_instance: MistralProcessor):
    """Test _create_query_prompt helper."""
    prompt = mistral_processor_instance._create_query_prompt("my query", "my context")
    assert "CONTEXT:" in prompt and "my context" in prompt
    assert "QUESTION:" in prompt and "my query" in prompt

def test_create_parameter_extraction_prompt_helper(mistral_processor_instance: MistralProcessor):
    """Test _create_parameter_extraction_prompt helper."""
    prompt = mistral_processor_instance._create_parameter_extraction_prompt("text", ["p1", "p2"])
    assert "extract specific technical parameters from this text:" in prompt and "text" in prompt
    assert "extract the following parameters: p1, p2" in prompt
    assert "Format the output as a JSON object" in prompt


@patch('mistral_processor.MistralClient')
def test_get_models_success(MockMistralClientConstructor, mistral_processor_instance: MistralProcessor):
    """Test successful retrieval of models."""
    mock_client_instance = mistral_processor_instance.client
    mock_model1 = MagicMock(id="mistral-small")
    mock_model2 = MagicMock(id="mistral-large")
    mock_client_instance.models.list = MagicMock(return_value=MagicMock(data=[mock_model1, mock_model2]))

    models = mistral_processor_instance.get_models()
    assert models == ["mistral-small", "mistral-large"]
    mock_client_instance.models.list.assert_called_once()

@patch('mistral_processor.MistralClient')
def test_get_models_failure(MockMistralClientConstructor, mistral_processor_instance: MistralProcessor):
    """Test failure in retrieving models."""
    mock_client_instance = mistral_processor_instance.client
    mock_client_instance.models.list = MagicMock(side_effect=MistralAPIError(message="Failed to fetch models"))

    with pytest.raises(MistralProcessorError, match="Failed to get models: Failed to fetch models"):
        mistral_processor_instance.get_models()

# Test _extract_text_from_pdf_path (internal helper)
@patch('fitz.open') # fitz is PyMuPDF
def test_extract_text_from_pdf_path_with_fitz(mock_fitz_open, mistral_processor_instance: MistralProcessor):
    """Test _extract_text_from_pdf_path using mocked fitz."""
    mock_doc = MagicMock()
    mock_page = MagicMock()
    mock_page.get_text.return_value = "Fitz text "
    mock_doc.load_page.return_value = mock_page # Corrected: load_page returns a page object
    mock_doc.__len__.return_value = 2 # Simulate 2 pages
    mock_fitz_open.return_value.__enter__.return_value = mock_doc # For context manager

    text = mistral_processor_instance._extract_text_from_pdf_path("dummy.pdf")
    assert text == "Fitz text Fitz text "
    mock_fitz_open.assert_called_with("dummy.pdf")
    assert mock_doc.load_page.call_count == 2


@patch('fitz.open', side_effect=ImportError("PyMuPDF not available"))
@patch('pdfplumber.open')
def test_extract_text_from_pdf_path_with_pdfplumber_fallback(mock_pdfplumber_open, mock_fitz_import_error, mistral_processor_instance: MistralProcessor):
    """Test _extract_text_from_pdf_path falling back to pdfplumber."""
    mock_pdfplumber_doc = MagicMock()
    mock_page1 = MagicMock()
    mock_page1.extract_text.return_value = "Pdfplumber page1 "
    mock_page2 = MagicMock()
    mock_page2.extract_text.return_value = "Pdfplumber page2"
    mock_pdfplumber_doc.pages = [mock_page1, mock_page2]
    mock_pdfplumber_open.return_value.__enter__.return_value = mock_pdfplumber_doc

    text = mistral_processor_instance._extract_text_from_pdf_path("dummy.pdf")
    assert text == "Pdfplumber page1 Pdfplumber page2"
    mock_pdfplumber_open.assert_called_with("dummy.pdf")

@patch('fitz.open', side_effect=ImportError)
@patch('pdfplumber.open', side_effect=ImportError)
def test_extract_text_from_pdf_path_no_libraries(mock_pdfplumber_error, mock_fitz_error, mistral_processor_instance: MistralProcessor):
    """Test _extract_text_from_pdf_path when no PDF libraries are available."""
    with pytest.raises(MistralProcessorError, match="No PDF extraction libraries \(PyMuPDF, pdfplumber\) available."):
        mistral_processor_instance._extract_text_from_pdf_path("dummy.pdf")

# Test backoff for rate limit and connection errors
@pytest.mark.asyncio
@patch('mistral_processor.MistralProcessor._extract_text_from_pdf_path')
async def test_extract_from_pdf_rate_limit_error_with_backoff(mock_internal_extract_text, mistral_processor_instance: MistralProcessor, sample_pdf_text_content):
    mock_internal_extract_text.return_value = sample_pdf_text_content
    # Simulate that after retries, the error is still raised
    mistral_processor_instance.client.chat.side_effect = MistralRateLimitError(message="Rate limited")
    
    with pytest.raises(MistralProcessorError, match="Mistral API error: Rate limited"):
        await mistral_processor_instance.extract_from_pdf(b"dummy", "test.pdf")
    assert mistral_processor_instance.client.chat.call_count == MAX_RETRIES + 1 # backoff default is 3 tries, so 1 initial + 3 retries = 4. Oh, it's max_tries, so 3 total.

@pytest.mark.asyncio
@patch('mistral_processor.MistralProcessor._extract_text_from_pdf_path')
async def test_extract_from_pdf_connection_error_with_backoff(mock_internal_extract_text, mistral_processor_instance: MistralProcessor, sample_pdf_text_content):
    mock_internal_extract_text.return_value = sample_pdf_text_content
    mistral_processor_instance.client.chat.side_effect = MistralConnectionError(message="Connection failed")
    
    with pytest.raises(MistralProcessorError, match="Mistral API error: Connection failed"):
        await mistral_processor_instance.extract_from_pdf(b"dummy", "test.pdf")
    assert mistral_processor_instance.client.chat.call_count == MAX_RETRIES + 1


if __name__ == "__main__":
    pytest.main()
