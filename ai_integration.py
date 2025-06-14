#!/usr/bin/env python3
"""
AI Integration Module for Datasheet AI Comparison System

This module integrates pattern-based extraction with Mistral AI for enhanced accuracy:
1. Provides a combined extraction pipeline using patterns first, then AI as fallback
2. Compares and merges results from both extraction methods
3. Handles confidence scoring and extraction method selection
4. Provides utilities for extraction validation and quality assessment
"""

import os
import logging
import json
import time
import asyncio
from typing import Dict, List, Optional, Any, Union, Tuple, Set
from dataclasses import dataclass, field
import hashlib
from datetime import datetime

# Import extraction modules
from pdf_extractor import PDFExtractor, Parameter, PartVariant, DatasheetExtraction
from mistral_processor import MistralProcessor, MistralProcessorError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('ai_integration')

# Constants
MIN_PATTERN_CONFIDENCE = 0.6  # Minimum confidence for pattern extraction to be considered valid
MIN_PARAMETERS_THRESHOLD = 3  # Minimum number of parameters to extract before considering AI fallback
CONFIDENCE_BOOST = 0.1  # Confidence boost when parameters are found by both methods

@dataclass
class ExtractionStats:
    """Statistics about an extraction process"""
    total_parameters: int = 0
    pattern_extracted: int = 0
    ai_extracted: int = 0
    pattern_confidence_avg: float = 0.0
    ai_confidence_avg: float = 0.0
    execution_time: float = 0.0
    file_size: int = 0
    page_count: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format"""
        return {
            "total_parameters": self.total_parameters,
            "pattern_extracted": self.pattern_extracted,
            "ai_extracted": self.ai_extracted,
            "pattern_confidence_avg": self.pattern_confidence_avg,
            "ai_confidence_avg": self.ai_confidence_avg,
            "execution_time": self.execution_time,
            "file_size": self.file_size,
            "page_count": self.page_count
        }

class AIIntegrationError(Exception):
    """Base exception for AI integration errors"""
    pass

class IntegratedExtractor:
    """
    Integrated Extractor that combines pattern-based and AI-based extraction
    
    This class provides methods to:
    1. Extract data using pattern-based extraction first
    2. Fall back to AI-based extraction when needed
    3. Merge and validate results from both methods
    4. Track extraction statistics and performance
    """
    
    def __init__(self, 
                mistral_api_key: str = None, 
                pattern_extractor: PDFExtractor = None,
                ai_extractor: MistralProcessor = None,
                debug: bool = False):
        """
        Initialize the integrated extractor
        
        Args:
            mistral_api_key: Mistral API key (optional if ai_extractor is provided)
            pattern_extractor: PDFExtractor instance (optional, will create if not provided)
            ai_extractor: MistralProcessor instance (optional, will create if not provided and API key is given)
            debug: Enable debug mode with additional logging
        """
        self.debug = debug
        if debug:
            logger.setLevel(logging.DEBUG)
        
        # Initialize pattern extractor
        self.pattern_extractor = pattern_extractor or PDFExtractor(debug=debug)
        
        # Initialize AI extractor if API key is provided
        self.ai_extractor = ai_extractor
        if not ai_extractor and mistral_api_key:
            self.ai_extractor = MistralProcessor(api_key=mistral_api_key, debug=debug)
        
        logger.info("Initialized IntegratedExtractor")
        logger.info(f"AI extraction available: {self.ai_extractor is not None}")
    
    async def extract_from_file(self, file_path: str, force_ai: bool = False) -> Tuple[DatasheetExtraction, ExtractionStats]:
        """
        Extract data from PDF file using integrated approach
        
        Args:
            file_path: Path to the PDF file
            force_ai: Force AI extraction even if pattern extraction is sufficient
            
        Returns:
            Tuple of (DatasheetExtraction result, ExtractionStats)
            
        Raises:
            AIIntegrationError: If extraction fails
        """
        logger.info(f"Processing file: {file_path}")
        start_time = time.time()
        
        try:
            stats = ExtractionStats()
            stats.file_size = os.path.getsize(file_path)
            
            # Get page count
            try:
                import fitz
                doc = fitz.open(file_path)
                stats.page_count = len(doc)
                doc.close()
            except:
                stats.page_count = 0
            
            # Step 1: Perform pattern-based extraction
            pattern_result = self.pattern_extractor.extract_from_file(file_path)
            
            # Step 2: Count extracted parameters and calculate confidence
            pattern_params_count = sum(len(variant.parameters) for variant in pattern_result.variants)
            pattern_confidence_sum = sum(
                param.confidence for variant in pattern_result.variants 
                for param in variant.parameters
            )
            
            if pattern_params_count > 0:
                stats.pattern_extracted = pattern_params_count
                stats.pattern_confidence_avg = pattern_confidence_sum / pattern_params_count
            
            # Step 3: Decide if AI extraction is needed
            needs_ai = (
                force_ai or 
                self._needs_ai_extraction(pattern_result, pattern_params_count, stats.pattern_confidence_avg)
            )
            
            # Step 4: Perform AI extraction if needed
            ai_result = None
            if needs_ai and self.ai_extractor:
                logger.info(f"Using AI extraction for {file_path}")
                
                # Read file content
                with open(file_path, "rb") as f:
                    file_content = f.read()
                
                # Extract using AI
                try:
                    ai_data = await self.ai_extractor.extract_from_pdf(
                        file_content, 
                        os.path.basename(file_path)
                    )
                    
                    # Convert to DatasheetExtraction format
                    ai_result = self._convert_ai_result_to_extraction(ai_data)
                    
                    # Update stats
                    ai_params_count = sum(len(variant.parameters) for variant in ai_result.variants)
                    ai_confidence_sum = sum(
                        param.confidence for variant in ai_result.variants 
                        for param in variant.parameters
                    )
                    
                    if ai_params_count > 0:
                        stats.ai_extracted = ai_params_count
                        stats.ai_confidence_avg = ai_confidence_sum / ai_params_count
                    
                except MistralProcessorError as e:
                    logger.warning(f"AI extraction failed: {str(e)}")
                    # Continue with pattern extraction result only
            
            # Step 5: Merge results if both methods were used
            final_result = pattern_result
            if ai_result:
                final_result = self._merge_extraction_results(pattern_result, ai_result)
            
            # Update total parameters count
            stats.total_parameters = sum(len(variant.parameters) for variant in final_result.variants)
            
            # Calculate execution time
            stats.execution_time = time.time() - start_time
            
            logger.info(f"Extraction completed in {stats.execution_time:.2f}s: "
                       f"{stats.pattern_extracted} pattern, {stats.ai_extracted} AI, "
                       f"{stats.total_parameters} total parameters")
            
            return final_result, stats
            
        except Exception as e:
            logger.error(f"Error in integrated extraction: {str(e)}")
            raise AIIntegrationError(f"Extraction failed: {str(e)}")
    
    async def extract_from_bytes(self, file_content: bytes, filename: str, force_ai: bool = False) -> Tuple[DatasheetExtraction, ExtractionStats]:
        """
        Extract data from PDF bytes using integrated approach
        
        Args:
            file_content: PDF file content as bytes
            filename: Original filename for reference
            force_ai: Force AI extraction even if pattern extraction is sufficient
            
        Returns:
            Tuple of (DatasheetExtraction result, ExtractionStats)
            
        Raises:
            AIIntegrationError: If extraction fails
        """
        logger.info(f"Processing bytes: {filename}")
        start_time = time.time()
        
        try:
            stats = ExtractionStats()
            stats.file_size = len(file_content)
            
            # Save to temporary file
            import tempfile
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
                tmp_file.write(file_content)
                tmp_path = tmp_file.name
            
            # Process the temporary file
            result, stats = await self.extract_from_file(tmp_path, force_ai)
            
            # Clean up
            os.unlink(tmp_path)
            
            return result, stats
            
        except Exception as e:
            logger.error(f"Error in integrated extraction from bytes: {str(e)}")
            raise AIIntegrationError(f"Extraction failed: {str(e)}")
    
    def _needs_ai_extraction(self, pattern_result: DatasheetExtraction, params_count: int, avg_confidence: float) -> bool:
        """
        Determine if AI extraction is needed based on pattern extraction results
        
        Args:
            pattern_result: Result from pattern extraction
            params_count: Number of parameters extracted
            avg_confidence: Average confidence of extracted parameters
            
        Returns:
            True if AI extraction is needed, False otherwise
        """
        # If no AI extractor available, we can't use AI
        if not self.ai_extractor:
            return False
        
        # If pattern extraction found very few parameters, use AI
        if params_count < MIN_PARAMETERS_THRESHOLD:
            logger.info(f"AI extraction needed: Only {params_count} parameters found")
            return True
        
        # If pattern extraction has low confidence, use AI
        if avg_confidence < MIN_PATTERN_CONFIDENCE:
            logger.info(f"AI extraction needed: Low confidence ({avg_confidence:.2f})")
            return True
        
        # If supplier or product family is unknown, use AI
        if pattern_result.supplier == "Unknown" or pattern_result.product_family == "General Electronics":
            logger.info("AI extraction needed: Unknown supplier or product family")
            return True
        
        # If no part numbers were extracted, use AI
        if not pattern_result.variants or all(v.part_number.startswith("Unknown") for v in pattern_result.variants):
            logger.info("AI extraction needed: No valid part numbers found")
            return True
        
        # Otherwise, pattern extraction is sufficient
        return False
    
    def _convert_ai_result_to_extraction(self, ai_data: Dict[str, Any]) -> DatasheetExtraction:
        """
        Convert AI extraction result to DatasheetExtraction format
        
        Args:
            ai_data: Result from AI extraction
            
        Returns:
            DatasheetExtraction object
        """
        variants = []
        
        # Process each variant
        for variant_data in ai_data.get('variants', []):
            parameters = []
            
            # Process each parameter
            for param_data in variant_data.get('parameters', []):
                parameter = Parameter(
                    name=param_data.get('name', ''),
                    value=param_data.get('value', ''),
                    unit=param_data.get('unit', ''),
                    category=param_data.get('category', 'general'),
                    confidence=param_data.get('confidence', 0.7),
                    extraction_method="ai"  # Mark as AI-extracted
                )
                parameters.append(parameter)
            
            # Create variant
            variant = PartVariant(
                part_number=variant_data.get('part_number', 'Unknown'),
                parameters=parameters,
                description=variant_data.get('description', '')
            )
            variants.append(variant)
        
        # Create extraction result
        result = DatasheetExtraction(
            supplier=ai_data.get('supplier', 'Unknown'),
            product_family=ai_data.get('product_family', 'Unknown'),
            variants=variants,
            metadata={"extraction_method": "ai"}
        )
        
        return result
    
    def _merge_extraction_results(self, pattern_result: DatasheetExtraction, ai_result: DatasheetExtraction) -> DatasheetExtraction:
        """
        Merge results from pattern and AI extraction
        
        Args:
            pattern_result: Result from pattern extraction
            ai_result: Result from AI extraction
            
        Returns:
            Merged DatasheetExtraction object
        """
        logger.info("Merging pattern and AI extraction results")
        
        # Use best supplier and product family
        supplier = pattern_result.supplier
        if supplier == "Unknown" and ai_result.supplier != "Unknown":
            supplier = ai_result.supplier
        
        product_family = pattern_result.product_family
        if product_family == "General Electronics" and ai_result.product_family != "Unknown":
            product_family = ai_result.product_family
        
        # Merge variants
        all_variants = {}
        
        # Process pattern variants first
        for variant in pattern_result.variants:
            all_variants[variant.part_number] = {
                "part_number": variant.part_number,
                "description": variant.description,
                "parameters": {param.name: param for param in variant.parameters}
            }
        
        # Process AI variants, merging with pattern variants if they exist
        for variant in ai_result.variants:
            if variant.part_number in all_variants:
                # Merge with existing variant
                existing = all_variants[variant.part_number]
                
                # Update description if empty
                if not existing["description"] and variant.description:
                    existing["description"] = variant.description
                
                # Merge parameters
                for param in variant.parameters:
                    if param.name in existing["parameters"]:
                        # Parameter exists in both - use the one with higher confidence
                        existing_param = existing["parameters"][param.name]
                        if param.confidence > existing_param.confidence:
                            # Use AI parameter but boost confidence if both methods found it
                            param.confidence = min(1.0, param.confidence + CONFIDENCE_BOOST)
                            existing["parameters"][param.name] = param
                        else:
                            # Keep pattern parameter but boost confidence
                            existing_param.confidence = min(1.0, existing_param.confidence + CONFIDENCE_BOOST)
                    else:
                        # New parameter from AI
                        existing["parameters"][param.name] = param
            else:
                # New variant from AI
                all_variants[variant.part_number] = {
                    "part_number": variant.part_number,
                    "description": variant.description,
                    "parameters": {param.name: param for param in variant.parameters}
                }
        
        # Convert merged data back to variants list
        merged_variants = []
        for variant_data in all_variants.values():
            variant = PartVariant(
                part_number=variant_data["part_number"],
                parameters=list(variant_data["parameters"].values()),
                description=variant_data["description"]
            )
            merged_variants.append(variant)
        
        # Create merged result
        merged_result = DatasheetExtraction(
            supplier=supplier,
            product_family=product_family,
            variants=merged_variants,
            metadata={
                "pattern_extraction": {
                    "supplier": pattern_result.supplier,
                    "product_family": pattern_result.product_family,
                    "variants_count": len(pattern_result.variants),
                    "parameters_count": sum(len(v.parameters) for v in pattern_result.variants)
                },
                "ai_extraction": {
                    "supplier": ai_result.supplier,
                    "product_family": ai_result.product_family,
                    "variants_count": len(ai_result.variants),
                    "parameters_count": sum(len(v.parameters) for v in ai_result.variants)
                },
                "merged": True
            }
        )
        
        return merged_result
    
    def validate_extraction(self, extraction: DatasheetExtraction) -> Dict[str, Any]:
        """
        Validate extraction results and provide quality metrics
        
        Args:
            extraction: Extraction result to validate
            
        Returns:
            Dictionary with validation metrics
        """
        # Count parameters by extraction method
        pattern_params = 0
        ai_params = 0
        total_confidence = 0.0
        
        for variant in extraction.variants:
            for param in variant.parameters:
                if param.extraction_method == "pattern":
                    pattern_params += 1
                elif param.extraction_method == "ai":
                    ai_params += 1
                total_confidence += param.confidence
        
        total_params = pattern_params + ai_params
        avg_confidence = total_confidence / total_params if total_params > 0 else 0
        
        # Check for missing critical parameters
        critical_params = {"temperature_range", "data_rate", "power_consumption"}
        found_critical = set()
        
        for variant in extraction.variants:
            for param in variant.parameters:
                if param.name in critical_params:
                    found_critical.add(param.name)
        
        missing_critical = critical_params - found_critical
        
        # Validate part numbers
        valid_part_numbers = 0
        for variant in extraction.variants:
            if variant.part_number and not variant.part_number.startswith("Unknown"):
                valid_part_numbers += 1
        
        # Calculate overall quality score
        quality_score = 0.0
        if total_params > 0:
            # Base score on parameters found
            param_score = min(1.0, total_params / 10)  # Max score at 10+ parameters
            confidence_score = avg_confidence
            critical_score = len(found_critical) / len(critical_params)
            part_score = min(1.0, valid_part_numbers)
            
            # Weighted average
            quality_score = (
                param_score * 0.4 +
                confidence_score * 0.3 +
                critical_score * 0.2 +
                part_score * 0.1
            )
        
        return {
            "total_parameters": total_params,
            "pattern_parameters": pattern_params,
            "ai_parameters": ai_params,
            "average_confidence": avg_confidence,
            "missing_critical_parameters": list(missing_critical),
            "valid_part_numbers": valid_part_numbers,
            "quality_score": quality_score,
            "quality_category": self._get_quality_category(quality_score)
        }
    
    def _get_quality_category(self, quality_score: float) -> str:
        """
        Get quality category based on quality score
        
        Args:
            quality_score: Quality score (0.0-1.0)
            
        Returns:
            Quality category string
        """
        if quality_score >= 0.9:
            return "Excellent"
        elif quality_score >= 0.7:
            return "Good"
        elif quality_score >= 0.5:
            return "Fair"
        elif quality_score >= 0.3:
            return "Poor"
        else:
            return "Very Poor"
    
    def get_extraction_fingerprint(self, file_content: bytes) -> str:
        """
        Generate a fingerprint for a PDF file
        
        Args:
            file_content: PDF file content as bytes
            
        Returns:
            SHA-256 hash of the file content
        """
        return hashlib.sha256(file_content).hexdigest()


# Example usage
if __name__ == "__main__":
    import sys
    import argparse
    
    parser = argparse.ArgumentParser(description="Integrated PDF extraction with pattern and AI")
    parser.add_argument("pdf_file", help="Path to PDF file")
    parser.add_argument("--api-key", help="Mistral API key")
    parser.add_argument("--force-ai", action="store_true", help="Force AI extraction")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    args = parser.parse_args()
    
    # Initialize extractors
    pattern_extractor = PDFExtractor(debug=args.debug)
    
    # Initialize AI extractor if API key is provided
    ai_extractor = None
    if args.api_key:
        ai_extractor = MistralProcessor(api_key=args.api_key, debug=args.debug)
    
    # Initialize integrated extractor
    extractor = IntegratedExtractor(
        pattern_extractor=pattern_extractor,
        ai_extractor=ai_extractor,
        debug=args.debug
    )
    
    # Process file
    try:
        loop = asyncio.get_event_loop()
        result, stats = loop.run_until_complete(
            extractor.extract_from_file(args.pdf_file, force_ai=args.force_ai)
        )
        
        # Validate result
        validation = extractor.validate_extraction(result)
        
        # Print results
        print("\n=== EXTRACTION RESULTS ===")
        print(f"Supplier: {result.supplier}")
        print(f"Product Family: {result.product_family}")
        print(f"Variants: {len(result.variants)}")
        
        for i, variant in enumerate(result.variants):
            print(f"\nVariant {i+1}: {variant.part_number}")
            print("Parameters:")
            for param in variant.parameters:
                print(f"  {param.name}: {param.value} {param.unit} "
                     f"({param.extraction_method}, confidence: {param.confidence:.2f})")
        
        print("\n=== EXTRACTION STATS ===")
        print(f"Total parameters: {stats.total_parameters}")
        print(f"Pattern extracted: {stats.pattern_extracted}")
        print(f"AI extracted: {stats.ai_extracted}")
        print(f"Pattern confidence: {stats.pattern_confidence_avg:.2f}")
        print(f"AI confidence: {stats.ai_confidence_avg:.2f}")
        print(f"Execution time: {stats.execution_time:.2f}s")
        
        print("\n=== VALIDATION ===")
        print(f"Quality score: {validation['quality_score']:.2f}")
        print(f"Quality category: {validation['quality_category']}")
        print(f"Missing critical parameters: {', '.join(validation['missing_critical_parameters']) or 'None'}")
        
    except Exception as e:
        print(f"Error: {str(e)}")
        sys.exit(1)
