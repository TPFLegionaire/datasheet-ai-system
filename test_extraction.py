#!/usr/bin/env python3
"""
Test Extraction Script for Datasheet AI Comparison System

This script demonstrates the PDF extraction and database functionality:
1. Accepts a PDF file argument
2. Extracts data using the PDFExtractor
3. Displays the extracted data
4. Saves the data to the database
5. Retrieves and verifies the data

Usage:
    python test_extraction.py path/to/datasheet.pdf
"""

import os
import sys
import json
import argparse
from typing import Dict, Any
import pandas as pd
from pdf_extractor import PDFExtractor
from database import DatabaseManager

def print_section(title):
    """Print a section header"""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)

def print_json(data):
    """Pretty print JSON data"""
    print(json.dumps(data, indent=2))

def print_parameters(variants):
    """Print parameters from variants in a tabular format"""
    print("\nExtracted Parameters:")
    print("-" * 80)
    print(f"{'Part Number':<20} {'Parameter':<20} {'Value':<20} {'Unit':<10}")
    print("-" * 80)
    
    for variant in variants:
        part_number = variant.get('part_number', 'Unknown')
        for param in variant.get('parameters', []):
            name = param.get('name', '')
            value = param.get('value', '')
            unit = param.get('unit', '')
            print(f"{part_number:<20} {name:<20} {str(value):<20} {unit:<10}")

def verify_database_save(db_manager, datasheet_id, extraction_result):
    """Verify that data was correctly saved to database"""
    print_section("DATABASE VERIFICATION")
    
    # Retrieve datasheet
    datasheet = db_manager.get_datasheet(datasheet_id)
    if not datasheet:
        print("❌ Failed to retrieve datasheet from database!")
        return False
    
    print(f"✅ Retrieved datasheet ID: {datasheet_id}")
    
    # Verify supplier and product family
    original_supplier = extraction_result.supplier
    db_supplier = datasheet.get('supplier')
    
    original_product_family = extraction_result.product_family
    db_product_family = datasheet.get('product_family')
    
    print(f"Supplier: {original_supplier} -> {db_supplier} {'✅' if original_supplier == db_supplier else '❌'}")
    print(f"Product Family: {original_product_family} -> {db_product_family} {'✅' if original_product_family == db_product_family else '❌'}")
    
    # Get parameters for each variant
    for variant in extraction_result.variants:
        part_number = variant.part_number
        print(f"\nVerifying parameters for part: {part_number}")
        
        # Get parameters from database
        df = db_manager.get_parameters_comparison("*")
        part_params = df[df['part_number'] == part_number]
        
        if part_params.empty:
            print(f"❌ No parameters found for part {part_number}")
            continue
        
        print(f"✅ Found {len(part_params)} parameters for part {part_number}")
        print(part_params)
    
    return True

def main():
    """Main function"""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Test PDF extraction and database functionality')
    parser.add_argument('pdf_file', help='Path to PDF file to process')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    args = parser.parse_args()
    
    # Check if file exists
    if not os.path.exists(args.pdf_file):
        print(f"Error: File not found: {args.pdf_file}")
        return 1
    
    # Check if file is a PDF
    if not args.pdf_file.lower().endswith('.pdf'):
        print(f"Error: File is not a PDF: {args.pdf_file}")
        return 1
    
    try:
        print_section("PDF EXTRACTION")
        print(f"Processing file: {args.pdf_file}")
        
        # Initialize extractor
        extractor = PDFExtractor(debug=args.debug)
        
        # Extract data
        extraction_result = extractor.extract_from_file(args.pdf_file)
        
        # Print extraction results
        print(f"\nExtracted data from: {os.path.basename(args.pdf_file)}")
        print(f"Supplier: {extraction_result.supplier}")
        print(f"Product Family: {extraction_result.product_family}")
        print(f"Variants: {len(extraction_result.variants)}")
        
        # Print parameters
        variants_dict = [vars(v) for v in extraction_result.variants]
        for i, variant in enumerate(variants_dict):
            variant['parameters'] = [vars(p) for p in extraction_result.variants[i].parameters]
        
        print_parameters(variants_dict)
        
        # Save to database
        print_section("DATABASE STORAGE")
        db_manager = DatabaseManager(debug=args.debug)
        
        datasheet_id = db_manager.save_datasheet(
            supplier=extraction_result.supplier,
            product_family=extraction_result.product_family,
            filename=os.path.basename(args.pdf_file),
            data=extraction_result.to_dict()
        )
        
        print(f"✅ Saved to database with ID: {datasheet_id}")
        
        # Verify database save
        verify_database_save(db_manager, datasheet_id, extraction_result)
        
        print("\n✅ Test completed successfully")
        return 0
        
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        if args.debug:
            import traceback
            traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
