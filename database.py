#!/usr/bin/env python3
"""
Database Module for Datasheet AI Comparison System

This module handles all database operations including:
- Database initialization and schema management
- Saving and retrieving datasheet information
- Parameter queries and comparison
- Database maintenance utilities
"""

import sqlite3
import json
import logging
import os
import pandas as pd
from typing import Dict, List, Optional, Any, Union, Tuple
from datetime import datetime
from contextlib import contextmanager
import shutil

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('database')

# Database constants
DATABASE_FILE = 'datasheet_system.db'
BACKUP_DIR = 'db_backups'

class DatabaseError(Exception):
    """Base exception for database errors"""
    pass

class DatabaseManager:
    """
    Database Manager for Datasheet AI Comparison System
    
    Handles all database operations including initialization,
    data storage, retrieval, and maintenance.
    """
    
    def __init__(self, db_file: str = DATABASE_FILE, debug: bool = False):
        """
        Initialize the database manager
        
        Args:
            db_file: Path to SQLite database file
            debug: Enable debug mode with additional logging
        """
        self.db_file = db_file
        self.debug = debug
        
        if debug:
            logger.setLevel(logging.DEBUG)
        
        # Ensure database exists and has correct schema
        self.init_database()
    
    @contextmanager
    def get_connection(self):
        """
        Context manager for database connections
        
        Yields:
            SQLite connection object
        
        Raises:
            DatabaseError: If connection fails
        """
        conn = None
        try:
            conn = sqlite3.connect(self.db_file)
            conn.row_factory = sqlite3.Row  # Return rows as dictionaries
            yield conn
        except sqlite3.Error as e:
            logger.error(f"Database connection error: {str(e)}")
            raise DatabaseError(f"Failed to connect to database: {str(e)}")
        finally:
            if conn:
                conn.close()
    
    def init_database(self):
        """
        Initialize SQLite database with required schema
        
        Creates tables if they don't exist:
        - datasheets: Stores datasheet metadata
        - parameters: Stores extracted parameters
        - queries: Stores user queries and responses
        - parts: Stores part information
        """
        logger.info(f"Initializing database: {self.db_file}")
        
        try:
            with self.get_connection() as conn:
                c = conn.cursor()
                
                # Create datasheets table
                c.execute('''
                    CREATE TABLE IF NOT EXISTS datasheets (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        supplier TEXT NOT NULL,
                        product_family TEXT,
                        upload_date TIMESTAMP,
                        file_name TEXT,
                        file_hash TEXT,
                        extracted_data TEXT,
                        processing_status TEXT DEFAULT 'complete',
                        error_message TEXT
                    )
                ''')
                
                # Create parameters table
                c.execute('''
                    CREATE TABLE IF NOT EXISTS parameters (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        datasheet_id INTEGER,
                        part_number TEXT,
                        parameter_name TEXT,
                        parameter_value TEXT,
                        unit TEXT,
                        category TEXT,
                        confidence REAL DEFAULT 1.0,
                        FOREIGN KEY (datasheet_id) REFERENCES datasheets (id)
                    )
                ''')
                
                # Create queries table
                c.execute('''
                    CREATE TABLE IF NOT EXISTS queries (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        query_text TEXT,
                        response TEXT,
                        query_date TIMESTAMP,
                        execution_time REAL
                    )
                ''')
                
                # Create parts table
                c.execute('''
                    CREATE TABLE IF NOT EXISTS parts (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        part_number TEXT UNIQUE,
                        supplier TEXT,
                        product_family TEXT,
                        description TEXT,
                        datasheet_id INTEGER,
                        FOREIGN KEY (datasheet_id) REFERENCES datasheets (id)
                    )
                ''')
                
                # Create indexes for better performance
                c.execute('CREATE INDEX IF NOT EXISTS idx_parameters_name ON parameters(parameter_name)')
                c.execute('CREATE INDEX IF NOT EXISTS idx_parameters_part ON parameters(part_number)')
                c.execute('CREATE INDEX IF NOT EXISTS idx_datasheets_supplier ON datasheets(supplier)')
                
                conn.commit()
                logger.info("Database schema initialized successfully")
                
        except Exception as e:
            logger.error(f"Database initialization error: {str(e)}")
            raise DatabaseError(f"Failed to initialize database: {str(e)}")
    
    def save_datasheet(self, 
                      supplier: str, 
                      product_family: str, 
                      filename: str, 
                      data: Dict,
                      file_hash: str = None,
                      status: str = 'complete',
                      error_message: str = None) -> int:
        """
        Save datasheet information to database
        
        Args:
            supplier: Supplier name
            product_family: Product family name
            filename: Original datasheet filename
            data: Extracted data dictionary
            file_hash: SHA-256 hash of file content (optional)
            status: Processing status ('complete', 'failed', 'processing')
            error_message: Error message if processing failed
            
        Returns:
            ID of the inserted datasheet record
            
        Raises:
            DatabaseError: If save operation fails
        """
        logger.info(f"Saving datasheet: {filename} from {supplier}")
        
        try:
            with self.get_connection() as conn:
                c = conn.cursor()
                
                # Begin transaction
                conn.execute('BEGIN')
                
                # Check if file with same hash already exists
                if file_hash:
                    c.execute('SELECT id FROM datasheets WHERE file_hash = ?', (file_hash,))
                    existing = c.fetchone()
                    if existing:
                        logger.warning(f"Datasheet with same hash already exists: {file_hash}")
                        return existing['id']
                
                # Insert datasheet record
                c.execute('''
                    INSERT INTO datasheets 
                    (supplier, product_family, upload_date, file_name, file_hash, extracted_data, processing_status, error_message)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    supplier, 
                    product_family, 
                    datetime.now(), 
                    filename, 
                    file_hash,
                    json.dumps(data),
                    status,
                    error_message
                ))
                
                datasheet_id = c.lastrowid
                
                # Insert parameters if status is complete
                if status == 'complete' and 'variants' in data:
                    self._save_parameters(conn, datasheet_id, data['variants'])
                    self._save_parts(conn, datasheet_id, supplier, product_family, data['variants'])
                
                # Commit transaction
                conn.commit()
                logger.info(f"Datasheet saved with ID: {datasheet_id}")
                
                return datasheet_id
                
        except Exception as e:
            logger.error(f"Error saving datasheet: {str(e)}")
            raise DatabaseError(f"Failed to save datasheet: {str(e)}")
    
    def _save_parameters(self, conn, datasheet_id: int, variants: List[Dict]):
        """
        Save parameters from variants to database
        
        Args:
            conn: SQLite connection
            datasheet_id: ID of the datasheet
            variants: List of variant dictionaries
        """
        c = conn.cursor()
        
        for variant in variants:
            part_number = variant.get('part_number', 'Unknown')
            
            for param in variant.get('parameters', []):
                c.execute('''
                    INSERT INTO parameters 
                    (datasheet_id, part_number, parameter_name, parameter_value, unit, category, confidence)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    datasheet_id, 
                    part_number,
                    param.get('name', ''), 
                    str(param.get('value', '')),
                    param.get('unit', ''),
                    param.get('category', 'general'),
                    param.get('confidence', 1.0)
                ))
    
    def _save_parts(self, conn, datasheet_id: int, supplier: str, product_family: str, variants: List[Dict]):
        """
        Save part information to database
        
        Args:
            conn: SQLite connection
            datasheet_id: ID of the datasheet
            supplier: Supplier name
            product_family: Product family name
            variants: List of variant dictionaries
        """
        c = conn.cursor()
        
        for variant in variants:
            part_number = variant.get('part_number', 'Unknown')
            description = variant.get('description', '')
            
            # Use INSERT OR IGNORE to handle duplicates
            c.execute('''
                INSERT OR IGNORE INTO parts
                (part_number, supplier, product_family, description, datasheet_id)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                part_number,
                supplier,
                product_family,
                description,
                datasheet_id
            ))
    
    def update_datasheet_status(self, datasheet_id: int, status: str, error_message: str = None):
        """
        Update processing status of a datasheet
        
        Args:
            datasheet_id: ID of the datasheet
            status: New status ('complete', 'failed', 'processing')
            error_message: Error message if processing failed
            
        Raises:
            DatabaseError: If update operation fails
        """
        try:
            with self.get_connection() as conn:
                c = conn.cursor()
                
                c.execute('''
                    UPDATE datasheets
                    SET processing_status = ?, error_message = ?
                    WHERE id = ?
                ''', (status, error_message, datasheet_id))
                
                conn.commit()
                logger.info(f"Updated datasheet {datasheet_id} status to {status}")
                
        except Exception as e:
            logger.error(f"Error updating datasheet status: {str(e)}")
            raise DatabaseError(f"Failed to update datasheet status: {str(e)}")
    
    def get_all_datasheets(self) -> pd.DataFrame:
        """
        Get all datasheets from database
        
        Returns:
            DataFrame containing datasheet records
        """
        try:
            with self.get_connection() as conn:
                query = """
                    SELECT id, supplier, product_family, upload_date, file_name, processing_status
                    FROM datasheets
                    ORDER BY upload_date DESC
                """
                df = pd.read_sql_query(query, conn)
                return df
                
        except Exception as e:
            logger.error(f"Error retrieving datasheets: {str(e)}")
            raise DatabaseError(f"Failed to retrieve datasheets: {str(e)}")
    
    def get_datasheet(self, datasheet_id: int) -> Dict:
        """
        Get a specific datasheet by ID
        
        Args:
            datasheet_id: ID of the datasheet
            
        Returns:
            Dictionary containing datasheet information
            
        Raises:
            DatabaseError: If retrieval fails
        """
        try:
            with self.get_connection() as conn:
                c = conn.cursor()
                
                c.execute('''
                    SELECT * FROM datasheets WHERE id = ?
                ''', (datasheet_id,))
                
                row = c.fetchone()
                
                if not row:
                    return None
                
                # Convert row to dict
                datasheet = dict(row)
                
                # Parse JSON data
                if datasheet.get('extracted_data'):
                    datasheet['extracted_data'] = json.loads(datasheet['extracted_data'])
                
                return datasheet
                
        except Exception as e:
            logger.error(f"Error retrieving datasheet {datasheet_id}: {str(e)}")
            raise DatabaseError(f"Failed to retrieve datasheet: {str(e)}")
    
    def get_parameters_comparison(self, parameter_name: str) -> pd.DataFrame:
        """
        Get parameter comparison across different parts
        
        Args:
            parameter_name: Name of parameter to compare
            
        Returns:
            DataFrame containing parameter comparison
        """
        try:
            with self.get_connection() as conn:
                query = """
                    SELECT d.supplier, p.part_number, p.parameter_value, p.unit, p.confidence
                    FROM parameters p
                    JOIN datasheets d ON p.datasheet_id = d.id
                    WHERE LOWER(p.parameter_name) LIKE LOWER(?)
                    ORDER BY d.supplier, p.part_number
                """
                df = pd.read_sql_query(query, conn, params=[f'%{parameter_name}%'])
                
                # Try to convert parameter_value to numeric for better sorting
                try:
                    df['parameter_value'] = pd.to_numeric(df['parameter_value'], errors='ignore')
                except:
                    pass
                
                return df
                
        except Exception as e:
            logger.error(f"Error comparing parameter {parameter_name}: {str(e)}")
            raise DatabaseError(f"Failed to compare parameter: {str(e)}")
    
    def get_unique_parameters(self) -> pd.DataFrame:
        """
        Get unique parameter names from database
        
        Returns:
            DataFrame containing unique parameter names
        """
        try:
            with self.get_connection() as conn:
                query = """
                    SELECT DISTINCT parameter_name, category, COUNT(*) as count
                    FROM parameters
                    GROUP BY parameter_name, category
                    ORDER BY count DESC
                """
                df = pd.read_sql_query(query, conn)
                return df
                
        except Exception as e:
            logger.error(f"Error retrieving unique parameters: {str(e)}")
            raise DatabaseError(f"Failed to retrieve parameters: {str(e)}")
    
    def get_suppliers(self) -> List[str]:
        """
        Get list of all suppliers
        
        Returns:
            List of supplier names
        """
        try:
            with self.get_connection() as conn:
                c = conn.cursor()
                
                c.execute('''
                    SELECT DISTINCT supplier FROM datasheets
                    ORDER BY supplier
                ''')
                
                suppliers = [row['supplier'] for row in c.fetchall()]
                return suppliers
                
        except Exception as e:
            logger.error(f"Error retrieving suppliers: {str(e)}")
            raise DatabaseError(f"Failed to retrieve suppliers: {str(e)}")
    
    def get_product_families(self) -> List[str]:
        """
        Get list of all product families
        
        Returns:
            List of product family names
        """
        try:
            with self.get_connection() as conn:
                c = conn.cursor()
                
                c.execute('''
                    SELECT DISTINCT product_family FROM datasheets
                    WHERE product_family IS NOT NULL
                    ORDER BY product_family
                ''')
                
                families = [row['product_family'] for row in c.fetchall()]
                return families
                
        except Exception as e:
            logger.error(f"Error retrieving product families: {str(e)}")
            raise DatabaseError(f"Failed to retrieve product families: {str(e)}")
    
    def save_query(self, query_text: str, response: str, execution_time: float) -> int:
        """
        Save user query and response
        
        Args:
            query_text: User query text
            response: AI response
            execution_time: Query execution time in seconds
            
        Returns:
            ID of the inserted query record
        """
        try:
            with self.get_connection() as conn:
                c = conn.cursor()
                
                c.execute('''
                    INSERT INTO queries
                    (query_text, response, query_date, execution_time)
                    VALUES (?, ?, ?, ?)
                ''', (
                    query_text,
                    response,
                    datetime.now(),
                    execution_time
                ))
                
                conn.commit()
                return c.lastrowid
                
        except Exception as e:
            logger.error(f"Error saving query: {str(e)}")
            raise DatabaseError(f"Failed to save query: {str(e)}")
    
    def get_recent_queries(self, limit: int = 10) -> pd.DataFrame:
        """
        Get recent user queries
        
        Args:
            limit: Maximum number of queries to return
            
        Returns:
            DataFrame containing recent queries
        """
        try:
            with self.get_connection() as conn:
                query = """
                    SELECT id, query_text, query_date, execution_time
                    FROM queries
                    ORDER BY query_date DESC
                    LIMIT ?
                """
                df = pd.read_sql_query(query, conn, params=[limit])
                return df
                
        except Exception as e:
            logger.error(f"Error retrieving recent queries: {str(e)}")
            raise DatabaseError(f"Failed to retrieve queries: {str(e)}")
    
    def get_metrics(self) -> Dict[str, Any]:
        """
        Get system metrics from database
        
        Returns:
            Dictionary containing system metrics
        """
        try:
            with self.get_connection() as conn:
                c = conn.cursor()
                
                # Get datasheet count
                c.execute("SELECT COUNT(*) FROM datasheets")
                datasheet_count = c.fetchone()[0]
                
                # Get parameter count
                c.execute("SELECT COUNT(DISTINCT parameter_name) FROM parameters")
                param_count = c.fetchone()[0]
                
                # Get part count
                c.execute("SELECT COUNT(DISTINCT part_number) FROM parameters")
                part_count = c.fetchone()[0]
                
                # Get supplier count
                c.execute("SELECT COUNT(DISTINCT supplier) FROM datasheets")
                supplier_count = c.fetchone()[0]
                
                # Get query count
                c.execute("SELECT COUNT(*) FROM queries")
                query_count = c.fetchone()[0]
                
                return {
                    "datasheets": datasheet_count,
                    "parameters": param_count,
                    "parts": part_count,
                    "suppliers": supplier_count,
                    "queries": query_count
                }
                
        except Exception as e:
            logger.error(f"Error retrieving metrics: {str(e)}")
            raise DatabaseError(f"Failed to retrieve metrics: {str(e)}")
    
    def search_parts(self, search_term: str) -> pd.DataFrame:
        """
        Search for parts by part number or supplier
        
        Args:
            search_term: Search term
            
        Returns:
            DataFrame containing matching parts
        """
        try:
            with self.get_connection() as conn:
                query = """
                    SELECT p.part_number, p.supplier, p.product_family, p.description, d.file_name
                    FROM parts p
                    JOIN datasheets d ON p.datasheet_id = d.id
                    WHERE p.part_number LIKE ? OR p.supplier LIKE ?
                    ORDER BY p.supplier, p.part_number
                """
                search_pattern = f"%{search_term}%"
                df = pd.read_sql_query(query, conn, params=[search_pattern, search_pattern])
                return df
                
        except Exception as e:
            logger.error(f"Error searching parts: {str(e)}")
            raise DatabaseError(f"Failed to search parts: {str(e)}")
    
    def get_part_details(self, part_number: str) -> Dict[str, Any]:
        """
        Get detailed information about a specific part
        
        Args:
            part_number: Part number to retrieve
            
        Returns:
            Dictionary containing part details and parameters
        """
        try:
            with self.get_connection() as conn:
                c = conn.cursor()
                
                # Get part information
                c.execute("""
                    SELECT p.*, d.file_name
                    FROM parts p
                    JOIN datasheets d ON p.datasheet_id = d.id
                    WHERE p.part_number = ?
                """, (part_number,))
                
                part = dict(c.fetchone() or {})
                
                if not part:
                    return None
                
                # Get parameters for this part
                query = """
                    SELECT parameter_name, parameter_value, unit, category
                    FROM parameters
                    WHERE part_number = ?
                    ORDER BY category, parameter_name
                """
                params_df = pd.read_sql_query(query, conn, params=[part_number])
                
                # Convert parameters DataFrame to list of dictionaries
                parameters = params_df.to_dict('records')
                
                # Add parameters to part dictionary
                part['parameters'] = parameters
                
                return part
                
        except Exception as e:
            logger.error(f"Error retrieving part details for {part_number}: {str(e)}")
            raise DatabaseError(f"Failed to retrieve part details: {str(e)}")
    
    def create_backup(self) -> str:
        """
        Create a backup of the database
        
        Returns:
            Path to the backup file
            
        Raises:
            DatabaseError: If backup fails
        """
        try:
            # Ensure backup directory exists
            if not os.path.exists(BACKUP_DIR):
                os.makedirs(BACKUP_DIR)
            
            # Generate backup filename with timestamp
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_file = os.path.join(BACKUP_DIR, f"datasheet_system_{timestamp}.db")
            
            # Copy database file
            shutil.copy2(self.db_file, backup_file)
            
            logger.info(f"Database backup created: {backup_file}")
            return backup_file
            
        except Exception as e:
            logger.error(f"Error creating database backup: {str(e)}")
            raise DatabaseError(f"Failed to create database backup: {str(e)}")
    
    def restore_backup(self, backup_file: str):
        """
        Restore database from backup
        
        Args:
            backup_file: Path to backup file
            
        Raises:
            DatabaseError: If restore fails
        """
        try:
            if not os.path.exists(backup_file):
                raise DatabaseError(f"Backup file not found: {backup_file}")
            
            # Close any open connections
            with self.get_connection() as conn:
                pass
            
            # Create a backup of current database before restoring
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            pre_restore_backup = os.path.join(BACKUP_DIR, f"pre_restore_{timestamp}.db")
            
            # Ensure backup directory exists
            if not os.path.exists(BACKUP_DIR):
                os.makedirs(BACKUP_DIR)
                
            shutil.copy2(self.db_file, pre_restore_backup)
            
            # Restore from backup
            shutil.copy2(backup_file, self.db_file)
            
            logger.info(f"Database restored from: {backup_file}")
            
        except Exception as e:
            logger.error(f"Error restoring database: {str(e)}")
            raise DatabaseError(f"Failed to restore database: {str(e)}")
    
    def vacuum_database(self):
        """
        Vacuum database to optimize storage and performance
        
        Raises:
            DatabaseError: If vacuum fails
        """
        try:
            with self.get_connection() as conn:
                conn.execute("VACUUM")
                logger.info("Database vacuum completed")
                
        except Exception as e:
            logger.error(f"Error vacuuming database: {str(e)}")
            raise DatabaseError(f"Failed to vacuum database: {str(e)}")
    
    def delete_datasheet(self, datasheet_id: int):
        """
        Delete a datasheet and all related data
        
        Args:
            datasheet_id: ID of the datasheet to delete
            
        Raises:
            DatabaseError: If deletion fails
        """
        try:
            with self.get_connection() as conn:
                c = conn.cursor()
                
                # Begin transaction
                conn.execute('BEGIN')
                
                # Delete parameters
                c.execute("DELETE FROM parameters WHERE datasheet_id = ?", (datasheet_id,))
                
                # Update parts table (don't delete, just remove datasheet_id reference)
                c.execute("""
                    UPDATE parts
                    SET datasheet_id = NULL
                    WHERE datasheet_id = ?
                """, (datasheet_id,))
                
                # Delete datasheet
                c.execute("DELETE FROM datasheets WHERE id = ?", (datasheet_id,))
                
                # Commit transaction
                conn.commit()
                
                logger.info(f"Datasheet {datasheet_id} deleted")
                
        except Exception as e:
            logger.error(f"Error deleting datasheet {datasheet_id}: {str(e)}")
            raise DatabaseError(f"Failed to delete datasheet: {str(e)}")


# Example usage
if __name__ == "__main__":
    # Initialize database manager
    db_manager = DatabaseManager(debug=True)
    
    # Print metrics
    metrics = db_manager.get_metrics()
    print("Database Metrics:")
    for key, value in metrics.items():
        print(f"  {key}: {value}")
    
    # Create backup
    backup_file = db_manager.create_backup()
    print(f"Backup created: {backup_file}")
