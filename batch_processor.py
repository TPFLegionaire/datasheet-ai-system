#!/usr/bin/env python3
"""
Batch Processing Module for Datasheet AI Comparison System

This module provides functionality for processing multiple datasheet files in batch:
1. Parallel processing with configurable concurrency
2. Progress tracking and status updates
3. Graceful error handling
4. Processing summary generation
5. Both synchronous and asynchronous modes
6. Integration with IntegratedExtractor or fallback to PDFExtractor
"""

import os
import time
import asyncio
import logging
import concurrent.futures
from enum import Enum
from typing import Dict, List, Optional, Any, Union, Tuple, Callable
from dataclasses import dataclass, field
import traceback
from datetime import datetime
import json
import hashlib
from pathlib import Path

# Import our modules
try:
    from pdf_extractor import PDFExtractor, DatasheetExtraction
    from ai_integration import IntegratedExtractor, ExtractionStats
    from database import DatabaseManager
except ImportError:
    # For standalone usage
    PDFExtractor = None
    IntegratedExtractor = None
    DatabaseManager = None
    DatasheetExtraction = Any
    ExtractionStats = Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('batch_processor')

class ProcessingStatus(Enum):
    """Enum for file processing status"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"

@dataclass
class FileTask:
    """Represents a file to be processed"""
    file_path: str
    file_name: str
    file_size: int
    file_hash: Optional[str] = None
    status: ProcessingStatus = ProcessingStatus.PENDING
    error_message: Optional[str] = None
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    result: Optional[Dict[str, Any]] = None
    extraction_stats: Optional[Dict[str, Any]] = None
    
    @property
    def duration(self) -> float:
        """Get processing duration in seconds"""
        if self.start_time is None:
            return 0
        if self.end_time is None:
            return time.time() - self.start_time
        return self.end_time - self.start_time
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "file_path": self.file_path,
            "file_name": self.file_name,
            "file_size": self.file_size,
            "file_hash": self.file_hash,
            "status": self.status.value,
            "error_message": self.error_message,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration": self.duration,
            "result": self.result,
            "extraction_stats": self.extraction_stats
        }

@dataclass
class BatchResult:
    """Results of a batch processing operation"""
    total_files: int = 0
    completed_files: int = 0
    failed_files: int = 0
    skipped_files: int = 0
    total_parameters: int = 0
    total_duration: float = 0
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    tasks: Dict[str, FileTask] = field(default_factory=dict)
    
    @property
    def success_rate(self) -> float:
        """Get success rate as percentage"""
        if self.total_files == 0:
            return 0
        return (self.completed_files / self.total_files) * 100
    
    @property
    def is_complete(self) -> bool:
        """Check if batch processing is complete"""
        return self.completed_files + self.failed_files + self.skipped_files >= self.total_files
    
    @property
    def duration(self) -> float:
        """Get batch processing duration in seconds"""
        if self.end_time is None:
            return time.time() - self.start_time
        return self.end_time - self.start_time
    
    @property
    def progress(self) -> float:
        """Get progress as percentage"""
        if self.total_files == 0:
            return 0
        return ((self.completed_files + self.failed_files + self.skipped_files) / self.total_files) * 100
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "total_files": self.total_files,
            "completed_files": self.completed_files,
            "failed_files": self.failed_files,
            "skipped_files": self.skipped_files,
            "total_parameters": self.total_parameters,
            "total_duration": self.total_duration,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration": self.duration,
            "progress": self.progress,
            "success_rate": self.success_rate,
            "is_complete": self.is_complete,
            "tasks": {k: v.to_dict() for k, v in self.tasks.items()}
        }
    
    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of the batch processing results"""
        return {
            "total_files": self.total_files,
            "completed_files": self.completed_files,
            "failed_files": self.failed_files,
            "skipped_files": self.skipped_files,
            "success_rate": f"{self.success_rate:.1f}%",
            "total_parameters": self.total_parameters,
            "duration": f"{self.duration:.2f}s",
            "avg_time_per_file": f"{(self.total_duration / self.total_files if self.total_files > 0 else 0):.2f}s",
            "avg_parameters_per_file": f"{(self.total_parameters / self.completed_files if self.completed_files > 0 else 0):.1f}"
        }

class BatchProcessor:
    """
    Batch Processor for datasheet files
    
    This class provides methods to process multiple datasheet files in batch,
    with support for parallel processing, progress tracking, and error handling.
    """
    
    def __init__(self, 
                max_workers: int = 4, 
                db_manager: Optional[Any] = None,
                integrated_extractor: Optional[Any] = None,
                pattern_extractor: Optional[Any] = None,
                force_ai: bool = False,
                debug: bool = False):
        """
        Initialize the batch processor
        
        Args:
            max_workers: Maximum number of worker threads/processes
            db_manager: DatabaseManager instance for storing results
            integrated_extractor: IntegratedExtractor instance
            pattern_extractor: PDFExtractor instance
            force_ai: Force AI extraction even if pattern extraction is sufficient
            debug: Enable debug mode with additional logging
        """
        self.max_workers = max_workers
        self.db_manager = db_manager
        self.integrated_extractor = integrated_extractor
        self.pattern_extractor = pattern_extractor
        self.force_ai = force_ai
        self.debug = debug
        
        if debug:
            logger.setLevel(logging.DEBUG)
        
        # Initialize extractors if not provided
        if self.pattern_extractor is None:
            if PDFExtractor is not None:
                self.pattern_extractor = PDFExtractor(debug=debug)
            else:
                logger.warning("PDFExtractor not available, extraction will fail")
        
        logger.info(f"Initialized BatchProcessor with max_workers={max_workers}")
        logger.info(f"Using integrated_extractor: {self.integrated_extractor is not None}")
        logger.info(f"Using pattern_extractor: {self.pattern_extractor is not None}")
        logger.info(f"Using db_manager: {self.db_manager is not None}")
    
    def process_batch_sync(self, file_paths: List[str], 
                          progress_callback: Optional[Callable[[BatchResult], None]] = None) -> BatchResult:
        """
        Process a batch of files synchronously
        
        Args:
            file_paths: List of file paths to process
            progress_callback: Callback function for progress updates
            
        Returns:
            BatchResult object with processing results
        """
        # Initialize batch result
        result = BatchResult(total_files=len(file_paths))
        
        # Create tasks for each file
        for file_path in file_paths:
            file_name = os.path.basename(file_path)
            file_size = os.path.getsize(file_path)
            
            # Create task
            task = FileTask(
                file_path=file_path,
                file_name=file_name,
                file_size=file_size
            )
            
            # Add to result
            result.tasks[file_path] = task
        
        # Process files with thread pool
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit tasks
            future_to_path = {
                executor.submit(self._process_file, file_path): file_path
                for file_path in file_paths
            }
            
            # Process results as they complete
            for future in concurrent.futures.as_completed(future_to_path):
                file_path = future_to_path[future]
                task = result.tasks[file_path]
                
                try:
                    # Get result
                    task_result, extraction_stats = future.result()
                    
                    # Update task
                    task.status = ProcessingStatus.COMPLETED
                    task.end_time = time.time()
                    task.result = task_result
                    task.extraction_stats = extraction_stats
                    
                    # Update batch result
                    result.completed_files += 1
                    result.total_duration += task.duration
                    
                    # Count parameters
                    if task_result and "variants" in task_result:
                        param_count = sum(
                            len(variant.get("parameters", [])) 
                            for variant in task_result["variants"]
                        )
                        result.total_parameters += param_count
                    
                    logger.info(f"Completed processing {task.file_name} in {task.duration:.2f}s")
                    
                except Exception as e:
                    # Update task with error
                    task.status = ProcessingStatus.FAILED
                    task.end_time = time.time()
                    task.error_message = str(e)
                    
                    # Update batch result
                    result.failed_files += 1
                    result.total_duration += task.duration
                    
                    logger.error(f"Failed to process {task.file_name}: {str(e)}")
                
                # Call progress callback
                if progress_callback:
                    try:
                        progress_callback(result)
                    except Exception as e:
                        logger.error(f"Error in progress callback: {str(e)}")
        
        # Update batch result
        result.end_time = time.time()
        
        return result
    
    async def process_batch_async(self, file_paths: List[str],
                                progress_callback: Optional[Callable[[BatchResult], None]] = None) -> BatchResult:
        """
        Process a batch of files asynchronously
        
        Args:
            file_paths: List of file paths to process
            progress_callback: Callback function for progress updates
            
        Returns:
            BatchResult object with processing results
        """
        # Initialize batch result
        result = BatchResult(total_files=len(file_paths))
        
        # Create tasks for each file
        for file_path in file_paths:
            file_name = os.path.basename(file_path)
            file_size = os.path.getsize(file_path)
            
            # Create task
            task = FileTask(
                file_path=file_path,
                file_name=file_name,
                file_size=file_size
            )
            
            # Add to result
            result.tasks[file_path] = task
        
        # Create semaphore to limit concurrency
        semaphore = asyncio.Semaphore(self.max_workers)
        
        # Create processing tasks
        async def process_file_async(file_path: str):
            async with semaphore:
                # Get task
                task = result.tasks[file_path]
                
                try:
                    # Update task status
                    task.status = ProcessingStatus.PROCESSING
                    task.start_time = time.time()
                    
                    # Process file
                    task_result, extraction_stats = await self._process_file_async(file_path)
                    
                    # Update task
                    task.status = ProcessingStatus.COMPLETED
                    task.end_time = time.time()
                    task.result = task_result
                    task.extraction_stats = extraction_stats
                    
                    # Update batch result
                    result.completed_files += 1
                    result.total_duration += task.duration
                    
                    # Count parameters
                    if task_result and "variants" in task_result:
                        param_count = sum(
                            len(variant.get("parameters", [])) 
                            for variant in task_result["variants"]
                        )
                        result.total_parameters += param_count
                    
                    logger.info(f"Completed processing {task.file_name} in {task.duration:.2f}s")
                    
                except Exception as e:
                    # Update task with error
                    task.status = ProcessingStatus.FAILED
                    task.end_time = time.time()
                    task.error_message = str(e)
                    
                    # Update batch result
                    result.failed_files += 1
                    result.total_duration += task.duration
                    
                    logger.error(f"Failed to process {task.file_name}: {str(e)}")
                
                # Call progress callback
                if progress_callback:
                    try:
                        progress_callback(result)
                    except Exception as e:
                        logger.error(f"Error in progress callback: {str(e)}")
        
        # Create and gather tasks
        tasks = [process_file_async(file_path) for file_path in file_paths]
        await asyncio.gather(*tasks)
        
        # Update batch result
        result.end_time = time.time()
        
        return result
    
    def _process_file(self, file_path: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """
        Process a single file synchronously
        
        Args:
            file_path: Path to the file
            
        Returns:
            Tuple of (extraction_result, extraction_stats)
            
        Raises:
            Exception: If processing fails
        """
        logger.info(f"Processing file: {file_path}")
        
        try:
            # Calculate file hash
            file_hash = self._calculate_file_hash(file_path)
            
            # Check if file already exists in database
            if self.db_manager:
                existing = self._check_file_exists(file_hash)
                if existing:
                    logger.info(f"File {file_path} already exists in database with ID {existing}")
                    return {"existing_id": existing}, {"skipped": True}
            
            # Extract data
            if self.integrated_extractor:
                # Use integrated extractor (pattern + AI)
                with open(file_path, "rb") as f:
                    file_content = f.read()
                
                # Run extraction synchronously
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                result, stats = loop.run_until_complete(
                    self.integrated_extractor.extract_from_bytes(
                        file_content,
                        os.path.basename(file_path),
                        force_ai=self.force_ai
                    )
                )
                loop.close()
                
                # Convert to dict
                result_dict = result.to_dict()
                stats_dict = stats.to_dict() if hasattr(stats, "to_dict") else vars(stats)
                
            elif self.pattern_extractor:
                # Use pattern extractor only
                result = self.pattern_extractor.extract_from_file(file_path)
                
                # Convert to dict
                result_dict = result.to_dict()
                stats_dict = {
                    "total_parameters": sum(len(variant.get("parameters", [])) for variant in result_dict["variants"]),
                    "pattern_extracted": sum(len(variant.get("parameters", [])) for variant in result_dict["variants"]),
                    "ai_extracted": 0,
                    "execution_time": 0,
                    "file_size": os.path.getsize(file_path)
                }
            else:
                raise ValueError("No extractor available")
            
            # Save to database if available
            if self.db_manager:
                datasheet_id = self.db_manager.save_datasheet(
                    supplier=result_dict.get("supplier", "Unknown"),
                    product_family=result_dict.get("product_family", "Unknown"),
                    filename=os.path.basename(file_path),
                    data=result_dict,
                    file_hash=file_hash
                )
                
                # Add database ID to result
                result_dict["datasheet_id"] = datasheet_id
            
            return result_dict, stats_dict
            
        except Exception as e:
            logger.error(f"Error processing {file_path}: {str(e)}")
            if self.debug:
                logger.error(traceback.format_exc())
            raise
    
    async def _process_file_async(self, file_path: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """
        Process a single file asynchronously
        
        Args:
            file_path: Path to the file
            
        Returns:
            Tuple of (extraction_result, extraction_stats)
            
        Raises:
            Exception: If processing fails
        """
        logger.info(f"Processing file asynchronously: {file_path}")
        
        try:
            # Calculate file hash
            file_hash = self._calculate_file_hash(file_path)
            
            # Check if file already exists in database
            if self.db_manager:
                existing = self._check_file_exists(file_hash)
                if existing:
                    logger.info(f"File {file_path} already exists in database with ID {existing}")
                    return {"existing_id": existing}, {"skipped": True}
            
            # Extract data
            if self.integrated_extractor:
                # Use integrated extractor (pattern + AI)
                with open(file_path, "rb") as f:
                    file_content = f.read()
                
                # Run extraction asynchronously
                result, stats = await self.integrated_extractor.extract_from_bytes(
                    file_content,
                    os.path.basename(file_path),
                    force_ai=self.force_ai
                )
                
                # Convert to dict
                result_dict = result.to_dict()
                stats_dict = stats.to_dict() if hasattr(stats, "to_dict") else vars(stats)
                
            elif self.pattern_extractor:
                # Use pattern extractor only (run in thread pool to avoid blocking)
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(
                    None, self.pattern_extractor.extract_from_file, file_path
                )
                
                # Convert to dict
                result_dict = result.to_dict()
                stats_dict = {
                    "total_parameters": sum(len(variant.get("parameters", [])) for variant in result_dict["variants"]),
                    "pattern_extracted": sum(len(variant.get("parameters", [])) for variant in result_dict["variants"]),
                    "ai_extracted": 0,
                    "execution_time": 0,
                    "file_size": os.path.getsize(file_path)
                }
            else:
                raise ValueError("No extractor available")
            
            # Save to database if available
            if self.db_manager:
                # Run in thread pool to avoid blocking
                loop = asyncio.get_event_loop()
                datasheet_id = await loop.run_in_executor(
                    None,
                    lambda: self.db_manager.save_datasheet(
                        supplier=result_dict.get("supplier", "Unknown"),
                        product_family=result_dict.get("product_family", "Unknown"),
                        filename=os.path.basename(file_path),
                        data=result_dict,
                        file_hash=file_hash
                    )
                )
                
                # Add database ID to result
                result_dict["datasheet_id"] = datasheet_id
            
            return result_dict, stats_dict
            
        except Exception as e:
            logger.error(f"Error processing {file_path}: {str(e)}")
            if self.debug:
                logger.error(traceback.format_exc())
            raise
    
    def _calculate_file_hash(self, file_path: str) -> str:
        """
        Calculate SHA-256 hash of a file
        
        Args:
            file_path: Path to the file
            
        Returns:
            SHA-256 hash as hex string
        """
        sha256_hash = hashlib.sha256()
        
        with open(file_path, "rb") as f:
            # Read in 64kb chunks
            for byte_block in iter(lambda: f.read(65536), b""):
                sha256_hash.update(byte_block)
        
        return sha256_hash.hexdigest()
    
    def _check_file_exists(self, file_hash: str) -> Optional[int]:
        """
        Check if a file with the same hash already exists in the database
        
        Args:
            file_hash: SHA-256 hash of the file
            
        Returns:
            Datasheet ID if exists, None otherwise
        """
        if not self.db_manager:
            return None
        
        try:
            # Check if file exists in database
            with self.db_manager.get_connection() as conn:
                c = conn.cursor()
                c.execute("SELECT id FROM datasheets WHERE file_hash = ?", (file_hash,))
                result = c.fetchone()
                
                if result:
                    return result[0]
                
                return None
                
        except Exception as e:
            logger.warning(f"Error checking file existence: {str(e)}")
            return None
    
    def process_directory(self, directory_path: str, 
                         file_pattern: str = "*.pdf",
                         recursive: bool = False,
                         progress_callback: Optional[Callable[[BatchResult], None]] = None) -> BatchResult:
        """
        Process all matching files in a directory
        
        Args:
            directory_path: Path to the directory
            file_pattern: Glob pattern for matching files
            recursive: Whether to search recursively
            progress_callback: Callback function for progress updates
            
        Returns:
            BatchResult object with processing results
        """
        # Find matching files
        if recursive:
            file_paths = []
            for root, _, files in os.walk(directory_path):
                for file in files:
                    if Path(file).match(file_pattern):
                        file_paths.append(os.path.join(root, file))
        else:
            file_paths = list(Path(directory_path).glob(file_pattern))
            file_paths = [str(p) for p in file_paths if p.is_file()]
        
        logger.info(f"Found {len(file_paths)} matching files in {directory_path}")
        
        # Process batch
        return self.process_batch_sync(file_paths, progress_callback)
    
    async def process_directory_async(self, directory_path: str, 
                                    file_pattern: str = "*.pdf",
                                    recursive: bool = False,
                                    progress_callback: Optional[Callable[[BatchResult], None]] = None) -> BatchResult:
        """
        Process all matching files in a directory asynchronously
        
        Args:
            directory_path: Path to the directory
            file_pattern: Glob pattern for matching files
            recursive: Whether to search recursively
            progress_callback: Callback function for progress updates
            
        Returns:
            BatchResult object with processing results
        """
        # Find matching files
        if recursive:
            file_paths = []
            for root, _, files in os.walk(directory_path):
                for file in files:
                    if Path(file).match(file_pattern):
                        file_paths.append(os.path.join(root, file))
        else:
            file_paths = list(Path(directory_path).glob(file_pattern))
            file_paths = [str(p) for p in file_paths if p.is_file()]
        
        logger.info(f"Found {len(file_paths)} matching files in {directory_path}")
        
        # Process batch
        return await self.process_batch_async(file_paths, progress_callback)
    
    def save_batch_result(self, result: BatchResult, output_path: str):
        """
        Save batch result to a JSON file
        
        Args:
            result: BatchResult object
            output_path: Path to save the result
        """
        try:
            with open(output_path, "w") as f:
                json.dump(result.to_dict(), f, indent=2)
            
            logger.info(f"Batch result saved to {output_path}")
            
        except Exception as e:
            logger.error(f"Error saving batch result: {str(e)}")


# Example usage
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Batch process datasheet PDFs")
    parser.add_argument("--input", required=True, help="Input directory or file")
    parser.add_argument("--output", help="Output JSON file for batch result")
    parser.add_argument("--recursive", action="store_true", help="Search recursively")
    parser.add_argument("--pattern", default="*.pdf", help="File pattern (default: *.pdf)")
    parser.add_argument("--workers", type=int, default=4, help="Maximum worker threads")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    parser.add_argument("--api-key", help="Mistral API key for AI extraction")
    parser.add_argument("--force-ai", action="store_true", help="Force AI extraction")
    args = parser.parse_args()
    
    # Initialize components
    pattern_extractor = PDFExtractor(debug=args.debug)
    db_manager = DatabaseManager(debug=args.debug)
    
    # Initialize AI extractor if API key is provided
    integrated_extractor = None
    if args.api_key and IntegratedExtractor is not None:
        from mistral_processor import MistralProcessor
        ai_extractor = MistralProcessor(api_key=args.api_key, debug=args.debug)
        integrated_extractor = IntegratedExtractor(
            pattern_extractor=pattern_extractor,
            ai_extractor=ai_extractor,
            debug=args.debug
        )
    
    # Initialize batch processor
    processor = BatchProcessor(
        max_workers=args.workers,
        db_manager=db_manager,
        integrated_extractor=integrated_extractor,
        pattern_extractor=pattern_extractor,
        force_ai=args.force_ai,
        debug=args.debug
    )
    
    # Progress callback
    def progress_callback(result: BatchResult):
        print(f"\rProgress: {result.progress:.1f}% ({result.completed_files}/{result.total_files} completed, {result.failed_files} failed)", end="")
    
    try:
        # Process input
        if os.path.isdir(args.input):
            # Process directory
            result = processor.process_directory(
                args.input,
                file_pattern=args.pattern,
                recursive=args.recursive,
                progress_callback=progress_callback
            )
        elif os.path.isfile(args.input):
            # Process single file
            result = processor.process_batch_sync(
                [args.input],
                progress_callback=progress_callback
            )
        else:
            print(f"Input not found: {args.input}")
            exit(1)
        
        # Print summary
        print("\n\nBatch Processing Summary:")
        summary = result.get_summary()
        for key, value in summary.items():
            print(f"{key}: {value}")
        
        # Save result if output path is provided
        if args.output:
            processor.save_batch_result(result, args.output)
        
    except KeyboardInterrupt:
        print("\nProcessing interrupted by user")
        exit(130)
    except Exception as e:
        print(f"\nError: {str(e)}")
        if args.debug:
            traceback.print_exc()
        exit(1)
