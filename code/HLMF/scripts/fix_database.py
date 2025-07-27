#!/usr/bin/env python
"""
Database structure repair script
"""

import os
import sys
import argparse
import sqlite3
import logging
import shutil
from datetime import datetime

# Add root directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Initialize default logger
logger = logging.getLogger("fix_database")

def setup_logging(log_level=logging.INFO):
    """Logging configuration"""
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        handlers=[logging.StreamHandler()]
    )
    return logger

def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description="Repair database structure")
    parser.add_argument("--db", type=str, default="data/feedback.db",
                        help="Path to response database file")
    parser.add_argument("--backup", action="store_true",
                        help="Create a backup before repairing")
    parser.add_argument("--force", action="store_true",
                        help="Overwrite if table already exists")
    parser.add_argument("--verbose", action="store_true",
                        help="Show repair process details")
    parser.add_argument("--log-level", type=str, default="INFO",
                        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
                        help="Logging level")
    
    return parser.parse_args()

def fix_database_schema(db_path: str, force: bool = False, backup: bool = True) -> bool:
    """
    Fix schema error in database feedback
    
    Args:
        db_path: Path to database file
        force: True to overwrite if table already exists
        backup: True to create backup before repair

    Returns:
        True if repair is successful, False otherwise
        """
    # Check if file exists
    if not os.path.exists(db_path):
        logger.error(f"Database does not exist: {db_path}")
        return False
    
    # Backup database if required
    if backup:
        backup_path = f"{db_path}.backup_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        try:
            shutil.copy2(db_path, backup_path)
            logger.info(f"Database backed up to {backup_path}")
        except Exception as e:
            logger.error(f"Unable to backup database: {e}")
            if not force:
                return False
    
    conn = None
    try:
        # Connect to database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check database structure
        logger.info("Check database structure...")
        
        # Check feedback table
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='feedback'")
        feedback_exists = cursor.fetchone() is not None
        
        if feedback_exists:
            logger.info("Feedback table already exists, check structure...")
            cursor.execute("PRAGMA table_info(feedback)")
            columns = {col[1]: col for col in cursor.fetchall()}
            
            if "conversation_id" not in columns:
                logger.warning("Column conversation_id does not exist in feedback table, please fix it...")
                
                # Create temporary table with new structure
                cursor.execute('''
                CREATE TABLE feedback_temp (
                    id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    conversation_id TEXT NOT NULL,
                    query TEXT NOT NULL,
                    responses TEXT NOT NULL,
                    selected_response TEXT NOT NULL,
                    feedback_score REAL,
                    feedback_text TEXT,
                    metadata TEXT
                )
                ''')
                
                # Copy data
                try:
                    # Get the names of existing columns
                    existing_columns = list(columns.keys())
                    column_str = ", ".join(existing_columns)
                    
                    # Copy the data and add a default value for conversation_id
                    cursor.execute(f"INSERT INTO feedback_temp ({column_str}, conversation_id) SELECT {column_str}, '' FROM feedback")
                    copy_count = cursor.rowcount
                    logger.info(f"Copied {copy_count} data rows from old table")
                    
                    # Delete old table
                    cursor.execute("DROP TABLE feedback")
                    
                    # Rename clipboard to feedback
                    cursor.execute("ALTER TABLE feedback_temp RENAME TO feedback")
                    
                    # Recreate indexes
                    cursor.execute('CREATE INDEX IF NOT EXISTS idx_feedback_conversation ON feedback(conversation_id)')
                    cursor.execute('CREATE INDEX IF NOT EXISTS idx_feedback_timestamp ON feedback(timestamp)')
                    
                    logger.info("Feedback board successfully repaired")
                    
                except Exception as e:
                    logger.error(f"Error copying data: {e}")
                    conn.rollback()
                    return False
            else:
                logger.info("The feedback table structure is correct.")
        else:
            logger.info("Feedback table does not exist, create new one...")
            cursor.execute('''
            CREATE TABLE feedback (
                id TEXT PRIMARY KEY,
                timestamp TEXT NOT NULL,
                conversation_id TEXT NOT NULL,
                query TEXT NOT NULL,
                responses TEXT NOT NULL,
                selected_response TEXT NOT NULL,
                feedback_score REAL,
                feedback_text TEXT,
                metadata TEXT
            )
            ''')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_feedback_conversation ON feedback(conversation_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_feedback_timestamp ON feedback(timestamp)')
            logger.info("New feedback table created")
        
        # Kiểm tra bảng comparisons
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='comparisons'")
        comparisons_exists = cursor.fetchone() is not None
        
        if not comparisons_exists:
            logger.info("Comparisons table does not exist, create new one...")
            cursor.execute('''
            CREATE TABLE comparisons (
                id TEXT PRIMARY KEY,
                timestamp TEXT NOT NULL,
                conversation_id TEXT NOT NULL,
                query TEXT NOT NULL,
                chosen TEXT NOT NULL,
                rejected TEXT NOT NULL,
                chosen_model TEXT NOT NULL,
                rejected_model TEXT NOT NULL,
                metadata TEXT
            )
            ''')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_comparisons_conversation ON comparisons(conversation_id)')
            logger.info("Created new comparisons table")
        else:
            logger.info("Comparisons table already exists")
            
            # Check the comparisons table structure
            cursor.execute("PRAGMA table_info(comparisons)")
            columns = {col[1]: col for col in cursor.fetchall()}
            
            if "conversation_id" not in columns:
                logger.warning("Column conversation_id does not exist in comparisons table, proceed to repair...")
                
                # Create temporary table
                cursor.execute('''
                CREATE TABLE comparisons_temp (
                    id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    conversation_id TEXT NOT NULL,
                    query TEXT NOT NULL,
                    chosen TEXT NOT NULL,
                    rejected TEXT NOT NULL,
                    chosen_model TEXT NOT NULL,
                    rejected_model TEXT NOT NULL,
                    metadata TEXT
                )
                ''')
                
                try:
                    # Get the names of existing columns
                    existing_columns = list(columns.keys())
                    column_str = ", ".join(existing_columns)
                    
                    # Copy data
                    cursor.execute(f"INSERT INTO comparisons_temp ({column_str}, conversation_id) SELECT {column_str}, '' FROM comparisons")
                    copy_count = cursor.rowcount
                    logger.info(f"Copied {copy_count} data rows from comparisons table")
                    
                    # Delete old table
                    cursor.execute("DROP TABLE comparisons")
                    
                    # Rename the clipboard
                    cursor.execute("ALTER TABLE comparisons_temp RENAME TO comparisons")
                    
                    # Recreate index
                    cursor.execute('CREATE INDEX IF NOT EXISTS idx_comparisons_conversation ON comparisons(conversation_id)')
                    
                    logger.info("Successfully repaired comparisons table")
                except Exception as e:
                    logger.error(f"Error copying comparisons data: {e}")
        
        # Check the stats table
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='stats'")
        stats_exists = cursor.fetchone() is not None
        
        if not stats_exists:
            logger.info("The stats table does not exist, create a new one...")
            cursor.execute('''
            CREATE TABLE stats (
                id TEXT PRIMARY KEY,
                timestamp TEXT NOT NULL,
                stat_type TEXT NOT NULL,
                value REAL NOT NULL,
                metadata TEXT
            )
            ''')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_stats_type ON stats(stat_type)')
            logger.info("Đã tạo bảng stats mới")
        else:
            logger.info("New stats table created")
        
        conn.commit()
        logger.info("Database repair completed successfully!")
        return True
        
    except Exception as e:
        logger.error(f"Error while repairing database: {e}")
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()

def main():
    """Main function"""
    args = parse_args()
    
    # Set up logging
    global logger
    log_level = getattr(logging, args.log_level)
    logger = setup_logging(log_level)
    
    # Print information
    logger.info(f"Start database repair: {args.db}")
    if args.backup:
        logger.info("Will create backup before repair")
    if args.force:
        logger.info("Force mode enabled: will overwrite existing tables if needed")
    
    # Repair database
    success = fix_database_schema(args.db, force=args.force, backup=args.backup)
    
    if success:
        logger.info("Database repair successful!")
    else:
        logger.error("Database repair failed!")
        sys.exit(1)

if __name__ == "__main__":
    main()