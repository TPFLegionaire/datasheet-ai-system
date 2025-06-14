#!/usr/bin/env python3
"""
Mistral AI Integration Module for Datasheet AI Comparison System

This module provides integration with Mistral AI for:
1. Enhanced PDF text extraction and processing
2. Fallback extraction when pattern-based extraction fails
3. Natural language query processing with context
4. Structured parameter extraction with AI assistance
5. Error handling and rate limiting
"""

import os
import json
import time
import logging
import asyncio
from typing import Dict, List, Optional, Any, Union, Tuple
from dataclasses import dataclass, asdict, field
import base64
from datetime import datetime
import tempfile
import backoff
from io import BytesIO

# Mistral AI SDK
from mistralai import Mistral
from mistralai.client import MistralClient
from mistralai.exceptions import MistralAPIError, MistralRateLimitError, MistralConnectionError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('mistral_processor')

# Constants
DEFAULT_MODEL = "mistral-large-latest"
EXTRACTION_MODEL = "mistral-large-latest"
QUERY_MODEL = "mistral-large-latest"
MAX_RETRIES = 3
RETRY_DELAY = 2  # seconds
MAX_TOKENS = 4096
TEMPERATURE = 0.1  # Low temperature for more deterministic outputs

@dataclass
class ExtractionResult:
    """Result of an AI-assisted extraction"""
    supplier: str
    product_family: str
    part_numbers: List[str]
    parameters: Dict[str, Any]
    raw_response: str
    confidence: float = 0.0
    extraction_time: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format"""
        return {
            "supplier": self.supplier,
            "product_family": self.product_family,
            "part_numbers": self.part_numbers,
            "parameters": self.parameters,
            "confidence": self.confidence,
            "extraction_time": self.extraction_time
        }

@dataclass
class QueryResult:
    """Result of a natural language query"""
    query: str
    response: str
    context_used: str
    execution_time: float = 0.0
    model_used: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format"""
        return {
            "query": self.query,
            "response": self.response,
            "context_used": self.context_used,
            "execution_time": self.execution_time,
            "model_used": self.model_used
        }

class MistralProcessorError(Exception):
    """Base exception for Mistral processor errors"""
    pass

class MistralProcessor:
    """
    Mistral AI Integration for Datasheet AI Comparison System
    
    This class provides methods to interact with Mistral AI for:
    - Enhanced PDF text extraction
    - Parameter identification from text
    - Natural language query processing
    """
    
    def __init__(self, api_key: str, model: str = DEFAULT_MODEL, debug: bool = False):
        """
        Initialize the Mistral processor
        
        Args:
            api_key: Mistral API key
            model: Model to use for queries
            debug: Enable debug mode with additional logging
        """
        self.api_key = api_key
        self.model = model
        self.debug = debug
        self.client = MistralClient(api_key=api_key)
        
        if debug:
            logger.setLevel(logging.DEBUG)
            
        logger.info(f"Initialized MistralProcessor with model: {model}")
    
    @backoff.on_exception(
        backoff.expo,
        (MistralRateLimitError, MistralConnectionError),
        max_tries=MAX_RETRIES,
        factor=RETRY_DELAY
    )
    async def extract_from_pdf(self, file_content: bytes, filename: str) -> Dict:
        """
        Extract structured data from PDF content using Mistral AI
        
        Args:
            file_content: PDF file content as bytes
            filename: Original filename for reference
            
        Returns:
            Dictionary containing structured data
            
        Raises:
            MistralProcessorError: If extraction fails
        """
        logger.info(f"Processing PDF: {filename}")
        start_time = time.time()
        
        try:
            # Save to temporary file for processing
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
                tmp_file.write(file_content)
                tmp_path = tmp_file.name
            
            # Extract text from PDF (implementation depends on available libraries)
            # For this example, we'll use a simple approach
            # In production, you might want to use PyMuPDF or another PDF library
            text_content = self._extract_text_from_pdf(tmp_path)
            
            # Clean up temporary file
            os.unlink(tmp_path)
            
            # If text content is too large, truncate it
            if len(text_content) > 15000:
                logger.warning(f"PDF content too large ({len(text_content)} chars), truncating to 15000 chars")
                text_content = text_content[:15000]
            
            # Process with Mistral AI
            extraction_result = await self._process_text_with_mistral(text_content, filename)
            
            # Calculate processing time
            extraction_result.extraction_time = time.time() - start_time
            
            # Convert to standard format for database storage
            result = self._convert_to_standard_format(extraction_result)
            
            logger.info(f"Successfully processed {filename} in {extraction_result.extraction_time:.2f}s")
            return result
            
        except Exception as e:
            logger.error(f"Error extracting data from {filename}: {str(e)}")
            raise MistralProcessorError(f"Failed to extract data: {str(e)}")
    
    def _extract_text_from_pdf(self, pdf_path: str) -> str:
        """
        Extract text content from PDF file
        
        Args:
            pdf_path: Path to the PDF file
            
        Returns:
            Extracted text content
        """
        try:
            # Try to use PyMuPDF if available
            import fitz
            doc = fitz.open(pdf_path)
            text = ""
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                text += page.get_text()
            doc.close()
            return text
        except ImportError:
            logger.warning("PyMuPDF not available, falling back to alternative method")
            
            # Try pdfplumber if available
            try:
                import pdfplumber
                with pdfplumber.open(pdf_path) as pdf:
                    text = ""
                    for page in pdf.pages:
                        text += page.extract_text() or ""
                    return text
            except ImportError:
                logger.error("No PDF extraction libraries available")
                raise MistralProcessorError("No PDF extraction libraries available")
    
    async def _process_text_with_mistral(self, text_content: str, filename: str) -> ExtractionResult:
        """
        Process text content with Mistral AI to extract structured data
        
        Args:
            text_content: Text content from PDF
            filename: Original filename for reference
            
        Returns:
            ExtractionResult object with structured data
        """
        logger.debug(f"Processing text content with Mistral AI (length: {len(text_content)})")
        
        # Create prompt for Mistral
        prompt = self._create_extraction_prompt(text_content, filename)
        
        try:
            # Call Mistral API
            response = self.client.chat.complete(
                model=EXTRACTION_MODEL,
                messages=[
                    {"role": "system", "content": "You are a technical datasheet analyzer that extracts structured information from text. Output should be valid JSON only."},
                    {"role": "user", "content": prompt}
                ],
                temperature=TEMPERATURE,
                max_tokens=MAX_TOKENS
            )
            
            # Parse response
            response_text = response.choices[0].message.content
            
            # Try to extract JSON from response
            json_data = self._extract_json_from_response(response_text)
            
            # Create extraction result
            result = ExtractionResult(
                supplier=json_data.get("supplier", "Unknown"),
                product_family=json_data.get("product_family", "Unknown"),
                part_numbers=json_data.get("part_numbers", []),
                parameters=json_data.get("parameters", {}),
                raw_response=response_text,
                confidence=json_data.get("confidence", 0.7)
            )
            
            return result
            
        except MistralAPIError as e:
            logger.error(f"Mistral API error: {str(e)}")
            raise MistralProcessorError(f"Mistral API error: {str(e)}")
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {str(e)}")
            logger.debug(f"Raw response: {response_text}")
            raise MistralProcessorError(f"Failed to parse JSON response: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}")
            raise MistralProcessorError(f"Unexpected error: {str(e)}")
    
    def _create_extraction_prompt(self, text_content: str, filename: str) -> str:
        """
        Create a prompt for Mistral AI to extract structured data
        
        Args:
            text_content: Text content from PDF
            filename: Original filename for reference
            
        Returns:
            Prompt string for Mistral AI
        """
        return f"""
I need to extract structured information from this technical datasheet. The filename is {filename}.

DATASHEET CONTENT:
```
{text_content}
```

Extract the following information in JSON format:
1. "supplier": The company that makes this product
2. "product_family": The product category or family
3. "part_numbers": A list of part numbers mentioned in the document
4. "parameters": A dictionary of technical parameters with the following structure:
   - Each key should be a parameter category (environmental, electrical, optical, physical, performance)
   - Each value should be a dictionary of parameters in that category
   - Each parameter should have "value", "unit", and "description" fields

5. "confidence": Your confidence score (0.0-1.0) in the extraction accuracy

Only output valid JSON with the above structure. Do not include any explanations or text outside the JSON.
"""
    
    def _extract_json_from_response(self, response_text: str) -> Dict[str, Any]:
        """
        Extract JSON from Mistral AI response
        
        Args:
            response_text: Response text from Mistral AI
            
        Returns:
            Parsed JSON data
            
        Raises:
            json.JSONDecodeError: If JSON parsing fails
        """
        # Try to find JSON in the response
        try:
            # First try to parse the entire response as JSON
            return json.loads(response_text)
        except json.JSONDecodeError:
            # If that fails, try to extract JSON from markdown code blocks
            import re
            json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', response_text)
            if json_match:
                return json.loads(json_match.group(1))
            
            # If that fails, try to find anything that looks like JSON
            json_match = re.search(r'(\{[\s\S]*\})', response_text)
            if json_match:
                return json.loads(json_match.group(1))
            
            # If all else fails, raise an error
            raise json.JSONDecodeError("Could not extract JSON from response", response_text, 0)
    
    def _convert_to_standard_format(self, extraction_result: ExtractionResult) -> Dict[str, Any]:
        """
        Convert extraction result to standard format for database storage
        
        Args:
            extraction_result: ExtractionResult object
            
        Returns:
            Dictionary in standard format for database storage
        """
        # Create variants from part numbers
        variants = []
        
        # If no part numbers were found, create a default one
        if not extraction_result.part_numbers:
            extraction_result.part_numbers = ["Unknown"]
        
        # Process each part number
        for part_number in extraction_result.part_numbers:
            # Collect parameters for this part
            parameters = []
            
            # Process each parameter category
            for category, params in extraction_result.parameters.items():
                for param_name, param_data in params.items():
                    # Skip if no value
                    if not param_data.get("value"):
                        continue
                    
                    parameters.append({
                        "name": param_name,
                        "value": param_data.get("value", ""),
                        "unit": param_data.get("unit", ""),
                        "category": category,
                        "description": param_data.get("description", ""),
                        "confidence": extraction_result.confidence
                    })
            
            # Create variant
            variant = {
                "part_number": part_number,
                "parameters": parameters
            }
            
            variants.append(variant)
        
        # Create final result
        result = {
            "supplier": extraction_result.supplier,
            "product_family": extraction_result.product_family,
            "variants": variants,
            "extraction_method": "mistral_ai",
            "extraction_time": extraction_result.extraction_time,
            "extraction_date": datetime.now().isoformat()
        }
        
        return result
    
    @backoff.on_exception(
        backoff.expo,
        (MistralRateLimitError, MistralConnectionError),
        max_tries=MAX_RETRIES,
        factor=RETRY_DELAY
    )
    def answer_query(self, query: str, context: str) -> QueryResult:
        """
        Answer a natural language query using Mistral AI
        
        Args:
            query: User query
            context: Context information for the query
            
        Returns:
            QueryResult object with response
            
        Raises:
            MistralProcessorError: If query processing fails
        """
        logger.info(f"Processing query: {query}")
        start_time = time.time()
        
        try:
            # Truncate context if too large
            if len(context) > 15000:
                logger.warning(f"Context too large ({len(context)} chars), truncating to 15000 chars")
                context = context[:15000]
            
            # Create prompt
            prompt = self._create_query_prompt(query, context)
            
            # Call Mistral API
            response = self.client.chat.complete(
                model=QUERY_MODEL,
                messages=[
                    {"role": "system", "content": "You are a technical datasheet expert that provides accurate, concise answers based on the provided context."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2,  # Slightly higher temperature for more natural responses
                max_tokens=1024
            )
            
            # Get response
            response_text = response.choices[0].message.content
            
            # Create query result
            result = QueryResult(
                query=query,
                response=response_text,
                context_used=context[:100] + "..." if len(context) > 100 else context,
                execution_time=time.time() - start_time,
                model_used=QUERY_MODEL
            )
            
            logger.info(f"Query processed in {result.execution_time:.2f}s")
            return result
            
        except MistralAPIError as e:
            logger.error(f"Mistral API error: {str(e)}")
            raise MistralProcessorError(f"Mistral API error: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}")
            raise MistralProcessorError(f"Unexpected error: {str(e)}")
    
    def _create_query_prompt(self, query: str, context: str) -> str:
        """
        Create a prompt for Mistral AI to answer a query
        
        Args:
            query: User query
            context: Context information for the query
            
        Returns:
            Prompt string for Mistral AI
        """
        return f"""
I need you to answer a question about technical datasheets based on the provided context.

CONTEXT:
```
{context}
```

QUESTION:
{query}

Please provide a concise, accurate answer based only on the information in the context. If the context doesn't contain enough information to answer the question, say so clearly.
"""
    
    async def extract_parameters_from_text(self, text: str, parameter_types: List[str] = None) -> Dict[str, Any]:
        """
        Extract specific parameters from text using Mistral AI
        
        Args:
            text: Text to extract parameters from
            parameter_types: List of parameter types to extract (e.g., "temperature_range", "data_rate")
            
        Returns:
            Dictionary of extracted parameters
            
        Raises:
            MistralProcessorError: If extraction fails
        """
        logger.info(f"Extracting parameters from text (length: {len(text)})")
        
        # If text is too large, truncate it
        if len(text) > 10000:
            logger.warning(f"Text too large ({len(text)} chars), truncating to 10000 chars")
            text = text[:10000]
        
        # Default parameter types if none provided
        if not parameter_types:
            parameter_types = [
                "temperature_range", "data_rate", "wavelength", 
                "power_consumption", "reach", "voltage"
            ]
        
        try:
            # Create prompt
            prompt = self._create_parameter_extraction_prompt(text, parameter_types)
            
            # Call Mistral API
            response = self.client.chat.complete(
                model=EXTRACTION_MODEL,
                messages=[
                    {"role": "system", "content": "You are a technical parameter extraction expert that extracts specific values from text. Output should be valid JSON only."},
                    {"role": "user", "content": prompt}
                ],
                temperature=TEMPERATURE,
                max_tokens=1024
            )
            
            # Parse response
            response_text = response.choices[0].message.content
            
            # Try to extract JSON from response
            parameters = self._extract_json_from_response(response_text)
            
            logger.info(f"Extracted {len(parameters)} parameters")
            return parameters
            
        except MistralAPIError as e:
            logger.error(f"Mistral API error: {str(e)}")
            raise MistralProcessorError(f"Mistral API error: {str(e)}")
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {str(e)}")
            raise MistralProcessorError(f"Failed to parse JSON response: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}")
            raise MistralProcessorError(f"Unexpected error: {str(e)}")
    
    def _create_parameter_extraction_prompt(self, text: str, parameter_types: List[str]) -> str:
        """
        Create a prompt for Mistral AI to extract specific parameters
        
        Args:
            text: Text to extract parameters from
            parameter_types: List of parameter types to extract
            
        Returns:
            Prompt string for Mistral AI
        """
        parameters_str = ", ".join(parameter_types)
        
        return f"""
I need to extract specific technical parameters from this text:

```
{text}
```

Please extract the following parameters: {parameters_str}

For each parameter, provide:
1. The value (numeric or range)
2. The unit of measurement
3. Your confidence in the extraction (0.0-1.0)

Format the output as a JSON object where each key is the parameter name and each value is an object with "value", "unit", and "confidence" fields.

Only output valid JSON. Do not include any explanations or text outside the JSON.
"""
    
    def get_models(self) -> List[str]:
        """
        Get available Mistral AI models
        
        Returns:
            List of available model names
            
        Raises:
            MistralProcessorError: If API call fails
        """
        try:
            response = self.client.models()
            return [model.id for model in response]
        except Exception as e:
            logger.error(f"Error getting models: {str(e)}")
            raise MistralProcessorError(f"Failed to get models: {str(e)}")
    
    def validate_api_key(self) -> bool:
        """
        Validate the Mistral API key
        
        Returns:
            True if API key is valid, False otherwise
        """
        try:
            # Try to get models as a simple API test
            self.get_models()
            return True
        except:
            return False


# Example usage
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 3:
        print("Usage: python mistral_processor.py <api_key> <pdf_file>")
        sys.exit(1)
    
    api_key = sys.argv[1]
    pdf_path = sys.argv[2]
    
    processor = MistralProcessor(api_key, debug=True)
    
    # Validate API key
    if not processor.validate_api_key():
        print("Invalid API key")
        sys.exit(1)
    
    # Read PDF file
    with open(pdf_path, "rb") as f:
        file_content = f.read()
    
    # Process PDF
    loop = asyncio.get_event_loop()
    result = loop.run_until_complete(
        processor.extract_from_pdf(file_content, os.path.basename(pdf_path))
    )
    
    # Print result
    print(json.dumps(result, indent=2))
