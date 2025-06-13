#!/usr/bin/env python3
"""
PDF Extractor Module for Datasheet AI Comparison System

This module provides functionality to extract structured data from PDF datasheets.
It uses PyMuPDF (fitz) for PDF parsing and implements pattern recognition
to identify technical parameters from various datasheet formats.
"""

import os
import re
import logging
import json
from typing import Dict, List, Optional, Any, Union, Tuple
from dataclasses import dataclass
import fitz  # PyMuPDF
import pdfplumber
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('pdf_extractor')

@dataclass
class Parameter:
    """Represents a technical parameter extracted from a datasheet"""
    name: str
    value: Any
    unit: str = ""
    category: str = "general"
    confidence: float = 1.0  # Confidence score for extraction accuracy

@dataclass
class PartVariant:
    """Represents a product variant with its parameters"""
    part_number: str
    parameters: List[Parameter]
    description: str = ""

@dataclass
class DatasheetExtraction:
    """Represents the complete extraction result from a datasheet"""
    supplier: str
    product_family: str
    variants: List[PartVariant]
    extraction_date: datetime = datetime.now()
    metadata: Dict[str, Any] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format for database storage"""
        return {
            "supplier": self.supplier,
            "product_family": self.product_family,
            "variants": [
                {
                    "part_number": variant.part_number,
                    "description": variant.description,
                    "parameters": [
                        {
                            "name": param.name,
                            "value": param.value,
                            "unit": param.unit,
                            "category": param.category,
                            "confidence": param.confidence
                        }
                        for param in variant.parameters
                    ]
                }
                for variant in self.variants
            ],
            "extraction_date": self.extraction_date.isoformat(),
            "metadata": self.metadata or {}
        }

class PDFExtractor:
    """
    PDF Extractor class for processing datasheet PDFs and extracting structured data.
    
    This class provides methods to:
    1. Extract text from PDF files
    2. Identify technical parameters using pattern recognition
    3. Structure the extracted data for database storage
    """
    
    # Common parameter patterns in datasheets
    PARAMETER_PATTERNS = {
        "temperature_range": [
            r"(?:operating|temperature)[\s\-_]*range.*?([+-]?\d+)\s*(?:to|[-–])\s*([+-]?\d+)\s*(?:°|deg)?C",
            r"(?:T(?:emp)?|Temperature)(?:op|operating)?\s*:\s*([+-]?\d+)\s*(?:to|[-–])\s*([+-]?\d+)\s*(?:°|deg)?C"
        ],
        "data_rate": [
            r"(?:data|bit)\s*rate.*?(\d+(?:\.\d+)?)\s*(Gbps|Mbps|kbps|bps)",
            r"(?:speed|bandwidth).*?(\d+(?:\.\d+)?)\s*(Gbps|Mbps|kbps|bps)"
        ],
        "wavelength": [
            r"wavelength.*?(\d+(?:\.\d+)?)\s*(nm)",
            r"(?:λ|lambda).*?(\d+(?:\.\d+)?)\s*(nm)"
        ],
        "power_consumption": [
            r"(?:power|consumption).*?(\d+(?:\.\d+)?)\s*(mW|W)",
            r"(?:power|consumption).*?(\d+(?:\.\d+)?)\s*(mW|W)"
        ],
        "reach": [
            r"(?:reach|distance|range).*?(\d+(?:\.\d+)?)\s*(m|km)",
            r"(?:transmission).*?(?:up to|max).*?(\d+(?:\.\d+)?)\s*(m|km)"
        ],
        "voltage": [
            r"(?:voltage|Vcc|supply).*?(\d+(?:\.\d+)?)\s*(V)",
            r"(?:V(?:cc|dd)).*?(\d+(?:\.\d+)?)\s*(V)"
        ],
        "dimensions": [
            r"(?:dimensions|size).*?(\d+(?:\.\d+)?)\s*x\s*(\d+(?:\.\d+)?)\s*x\s*(\d+(?:\.\d+)?)\s*(mm|cm|in)",
        ]
    }
    
    # Parameter categories
    PARAMETER_CATEGORIES = {
        "temperature_range": "environmental",
        "data_rate": "performance",
        "wavelength": "optical",
        "power_consumption": "electrical",
        "reach": "performance",
        "voltage": "electrical",
        "dimensions": "physical",
    }
    
    # Common units and their standardized form
    UNIT_STANDARDIZATION = {
        "C": "°C",
        "deg C": "°C",
        "degC": "°C",
        "degree C": "°C",
        "degrees C": "°C",
        "Gbit/s": "Gbps",
        "Gb/s": "Gbps",
        "Mbit/s": "Mbps",
        "Mb/s": "Mbps",
        "kbit/s": "kbps",
        "kb/s": "kbps",
        "nanometer": "nm",
        "nanometers": "nm",
        "milliwatt": "mW",
        "milliwatts": "mW",
        "watt": "W",
        "watts": "W",
        "meter": "m",
        "meters": "m",
        "kilometer": "km",
        "kilometers": "km",
        "volt": "V",
        "volts": "V",
        "millimeter": "mm",
        "millimeters": "mm",
        "centimeter": "cm",
        "centimeters": "cm",
        "inch": "in",
        "inches": "in",
    }
    
    def __init__(self, debug: bool = False):
        """
        Initialize the PDF extractor
        
        Args:
            debug: Enable debug mode with additional logging
        """
        self.debug = debug
        if debug:
            logger.setLevel(logging.DEBUG)
    
    def extract_from_file(self, file_path: str) -> DatasheetExtraction:
        """
        Extract structured data from a PDF file
        
        Args:
            file_path: Path to the PDF file
            
        Returns:
            DatasheetExtraction object containing structured data
        """
        logger.info(f"Processing PDF file: {file_path}")
        
        try:
            # Extract text from PDF
            text = self._extract_text(file_path)
            
            # Extract metadata
            metadata = self._extract_metadata(file_path)
            
            # Identify supplier and product family
            supplier = self._identify_supplier(text, os.path.basename(file_path), metadata)
            product_family = self._identify_product_family(text, metadata)
            
            # Extract part numbers
            part_numbers = self._extract_part_numbers(text)
            
            # If no part numbers found, use a default one based on the filename
            if not part_numbers:
                base_name = os.path.splitext(os.path.basename(file_path))[0]
                part_numbers = [base_name.replace(" ", "_")]
                logger.warning(f"No part numbers found, using filename: {part_numbers[0]}")
            
            # Process each part number
            variants = []
            for part_number in part_numbers:
                # Extract parameters for this part
                parameters = self._extract_parameters(text, part_number)
                
                # Create variant
                variant = PartVariant(
                    part_number=part_number,
                    parameters=parameters
                )
                variants.append(variant)
            
            # Create and return extraction result
            result = DatasheetExtraction(
                supplier=supplier,
                product_family=product_family,
                variants=variants,
                metadata=metadata
            )
            
            logger.info(f"Extraction completed for {file_path}: "
                       f"{len(variants)} variants, "
                       f"{sum(len(v.parameters) for v in variants)} parameters")
            
            return result
            
        except Exception as e:
            logger.error(f"Error extracting data from {file_path}: {str(e)}")
            raise
    
    def extract_from_bytes(self, file_content: bytes, filename: str) -> DatasheetExtraction:
        """
        Extract structured data from PDF bytes
        
        Args:
            file_content: PDF file content as bytes
            filename: Original filename for reference
            
        Returns:
            DatasheetExtraction object containing structured data
        """
        logger.info(f"Processing PDF from bytes: {filename}")
        
        try:
            # Save to temporary file
            import tempfile
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
                tmp_file.write(file_content)
                tmp_path = tmp_file.name
            
            # Process the temporary file
            result = self.extract_from_file(tmp_path)
            
            # Clean up
            os.unlink(tmp_path)
            
            return result
            
        except Exception as e:
            logger.error(f"Error extracting data from bytes ({filename}): {str(e)}")
            raise
    
    def _extract_text(self, file_path: str) -> str:
        """
        Extract text content from PDF file
        
        Args:
            file_path: Path to the PDF file
            
        Returns:
            Extracted text content
        """
        logger.debug(f"Extracting text from {file_path}")
        
        # Try PyMuPDF first (faster)
        try:
            doc = fitz.open(file_path)
            text = ""
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                text += page.get_text()
            doc.close()
            return text
        except Exception as e:
            logger.warning(f"PyMuPDF extraction failed: {str(e)}. Trying pdfplumber...")
        
        # Fall back to pdfplumber if PyMuPDF fails
        try:
            text = ""
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    text += page.extract_text() or ""
            return text
        except Exception as e:
            logger.error(f"Text extraction failed: {str(e)}")
            raise
    
    def _extract_metadata(self, file_path: str) -> Dict[str, Any]:
        """
        Extract metadata from PDF file
        
        Args:
            file_path: Path to the PDF file
            
        Returns:
            Dictionary of metadata
        """
        try:
            doc = fitz.open(file_path)
            metadata = doc.metadata
            doc.close()
            return metadata or {}
        except Exception as e:
            logger.warning(f"Metadata extraction failed: {str(e)}")
            return {}
    
    def _identify_supplier(self, text: str, filename: str, metadata: Dict[str, Any]) -> str:
        """
        Identify the supplier from text content
        
        Args:
            text: Extracted text content
            filename: Original filename
            metadata: PDF metadata
            
        Returns:
            Identified supplier name
        """
        # Common suppliers to check for
        common_suppliers = [
            "Finisar", "Cisco", "Juniper", "Huawei", "Broadcom", "Intel",
            "Mellanox", "Arista", "Nokia", "Ericsson", "Fujitsu", "NEC",
            "Alcatel-Lucent", "ZTE", "Ciena", "ADVA", "Infinera", "Lumentum"
        ]
        
        # Try to find supplier in metadata
        if metadata.get("author"):
            for supplier in common_suppliers:
                if supplier.lower() in metadata.get("author", "").lower():
                    return supplier
        
        # Try to find supplier in the first page of text
        first_page_text = text[:5000]  # Look at first ~5000 chars
        
        for supplier in common_suppliers:
            if supplier.lower() in first_page_text.lower():
                return supplier
        
        # Try to extract from filename
        for supplier in common_suppliers:
            if supplier.lower() in filename.lower():
                return supplier
        
        # Default to "Unknown" if no supplier found
        return "Unknown"
    
    def _identify_product_family(self, text: str, metadata: Dict[str, Any]) -> str:
        """
        Identify the product family from text content
        
        Args:
            text: Extracted text content
            metadata: PDF metadata
            
        Returns:
            Identified product family
        """
        # Common product family keywords
        product_families = {
            "Optical Transceivers": ["transceiver", "SFP", "QSFP", "XFP", "CFP", "optical", "optic"],
            "Network Switches": ["switch", "switching", "ethernet switch"],
            "Routers": ["router", "routing", "edge router", "core router"],
            "Servers": ["server", "rack server", "blade server"],
            "Storage": ["storage", "SSD", "HDD", "NAS", "SAN"],
            "Wireless": ["wireless", "WiFi", "access point", "AP", "antenna"],
        }
        
        # Check title in metadata
        if metadata.get("title"):
            title = metadata.get("title", "").lower()
            for family, keywords in product_families.items():
                if any(keyword.lower() in title for keyword in keywords):
                    return family
        
        # Check in text
        text_lower = text.lower()
        for family, keywords in product_families.items():
            if any(keyword.lower() in text_lower for keyword in keywords):
                return family
        
        # Default
        return "General Electronics"
    
    def _extract_part_numbers(self, text: str) -> List[str]:
        """
        Extract part numbers from text content
        
        Args:
            text: Extracted text content
            
        Returns:
            List of identified part numbers
        """
        # Common part number patterns
        part_patterns = [
            # Model/Part Number explicitly labeled
            r"(?:Model|Part|Product)[\s\-_]*(?:Number|No|#|ID)[\s\-_]*[:=][\s\-_]*([A-Z0-9][\w\-]{2,20})",
            # P/N format
            r"P/N[\s\-_]*[:=][\s\-_]*([A-Z0-9][\w\-]{2,20})",
            # Ordering information section
            r"(?:Ordering|Order)[\s\-_]*(?:Information|Info|Code)[\s\-_]*[:=][\s\-_]*([A-Z0-9][\w\-]{2,20})"
        ]
        
        part_numbers = []
        for pattern in part_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                part_number = match.group(1).strip()
                if part_number and part_number not in part_numbers:
                    part_numbers.append(part_number)
        
        return part_numbers
    
    def _extract_parameters(self, text: str, part_number: str) -> List[Parameter]:
        """
        Extract technical parameters from text content
        
        Args:
            text: Extracted text content
            part_number: Part number for context
            
        Returns:
            List of extracted parameters
        """
        parameters = []
        
        # Process each parameter type
        for param_name, patterns in self.PARAMETER_PATTERNS.items():
            category = self.PARAMETER_CATEGORIES.get(param_name, "general")
            
            for pattern in patterns:
                matches = re.finditer(pattern, text, re.IGNORECASE)
                for match in matches:
                    try:
                        if param_name == "temperature_range":
                            # Temperature range has two values
                            low = match.group(1)
                            high = match.group(2)
                            value = f"{low} to {high}"
                            unit = "°C"
                        elif param_name == "dimensions":
                            # Dimensions have three values plus unit
                            length = match.group(1)
                            width = match.group(2)
                            height = match.group(3)
                            value = f"{length}x{width}x{height}"
                            unit = match.group(4)
                        else:
                            # Most parameters have value and unit
                            value = match.group(1)
                            unit = match.group(2)
                        
                        # Standardize unit
                        unit = self.UNIT_STANDARDIZATION.get(unit, unit)
                        
                        # Create parameter
                        parameter = Parameter(
                            name=param_name,
                            value=value,
                            unit=unit,
                            category=category,
                            confidence=0.8  # Default confidence
                        )
                        
                        # Add to list if not duplicate
                        if not any(p.name == param_name for p in parameters):
                            parameters.append(parameter)
                            logger.debug(f"Extracted parameter: {param_name} = {value} {unit}")
                        
                    except Exception as e:
                        logger.warning(f"Error processing parameter match {param_name}: {str(e)}")
        
        return parameters
    
    def extract_tables(self, file_path: str) -> List[Dict[str, Any]]:
        """
        Extract tables from PDF file
        
        Args:
            file_path: Path to the PDF file
            
        Returns:
            List of extracted tables as dictionaries
        """
        tables = []
        
        try:
            with pdfplumber.open(file_path) as pdf:
                for page_num, page in enumerate(pdf.pages):
                    page_tables = page.extract_tables()
                    
                    for table_num, table_data in enumerate(page_tables):
                        if not table_data:
                            continue
                        
                        # Process table - convert to dict with header row as keys
                        headers = [str(h).strip() if h else f"Column{i}" for i, h in enumerate(table_data[0])]
                        
                        for row in table_data[1:]:
                            if not any(cell for cell in row):  # Skip empty rows
                                continue
                                
                            row_dict = {}
                            for i, cell in enumerate(row):
                                if i < len(headers):
                                    row_dict[headers[i]] = cell
                            
                            if row_dict:
                                tables.append({
                                    "page": page_num + 1,
                                    "table": table_num + 1,
                                    "data": row_dict
                                })
            
            logger.info(f"Extracted {len(tables)} table rows from {file_path}")
            return tables
            
        except Exception as e:
            logger.error(f"Error extracting tables from {file_path}: {str(e)}")
            return []


# Example usage
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python pdf_extractor.py <pdf_file>")
        sys.exit(1)
    
    pdf_path = sys.argv[1]
    extractor = PDFExtractor(debug=True)
    
    try:
        result = extractor.extract_from_file(pdf_path)
        print(json.dumps(result.to_dict(), indent=2))
    except Exception as e:
        print(f"Error: {str(e)}")
        sys.exit(1)
