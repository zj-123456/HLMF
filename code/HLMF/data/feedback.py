import os
import sqlite3
import logging

logger = logging.getLogger(__name__)#创建一个日志记录器，方便记录调试信息和错误。
#修复 SQLite 数据库的表结构，特别是 feedback 表的 conversation_id 列，以及确保 comparisons 和 stats 表的存在。代码同时包含了日志记录和错误处理机制，以确保数据库的安全性。
def fix_database_schema(db_path: str) -> bool:
    """
    Fix schema error in database feedback

    Args:
        db_path: Path to database file

    Returns:
        True if the edit is successful, False otherwise
    """
    # Check if file exists
    if not os.path.exists(db_path):#如果数据库文件不存在，记录错误日志并返回 False。
        logger.error(f"Database does not exist: {db_path}")
        return False
    
    conn = None
    try:
        # Backup database before editing
        backup_path = f"{db_path}.backup"
        
        with open(db_path, 'rb') as src, open(backup_path, 'wb') as dst:
            dst.write(src.read())
        logger.info(f"Database backed up to {backup_path}")#在执行任何修改前，先创建数据库文件的备份，防止数据丢失。
        
        # Connect to database创建数据库连接和游标对象，用于执行 SQL 语句。
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check current table structure检查 feedback 表是否缺少 conversation_id 列
        cursor.execute("PRAGMA table_info(feedback)")
        columns = cursor.fetchall()
        column_names = [col[1] for col in columns]
        
        # Check if the conversation_id column exists如果 feedback 表中没有 conversation_id 列，则执行修复。
        if "conversation_id" not in column_names:
            # Create a temporary table to store data先创建 feedback_temp 作为 feedback 的备份
            cursor.execute("CREATE TABLE feedback_temp AS SELECT * FROM feedback")
            
            # Delete old table删除 feedback 表
            cursor.execute("DROP TABLE feedback")
            
            # Recreate the table with the correct structure

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
            
            # Move data from the temporary table to the new table if there is data
            #  #重新创建 feedback 表，并添加 conversation_id 列。
            cursor.execute("PRAGMA table_info(feedback_temp)")
            temp_columns = cursor.fetchall()
            temp_column_names = [col[1] for col in temp_columns]
            
            if temp_column_names:
                # Find common columns between two tables
                common_columns = [col for col in temp_column_names if col in column_names]
                common_columns_str = ", ".join(common_columns)
                
                # Copy data, set default conversation_id to empty string
                try:
                    cursor.execute(f"INSERT INTO feedback ({common_columns_str}, conversation_id) SELECT {common_columns_str}, '' FROM feedback_temp")
                    logger.info(f"Moved {cursor.rowcount} records from clipboard")
                except Exception as e:
                    logger.error(f"Error while moving data: {e}")
            
            # Clear clipboard
            cursor.execute("DROP TABLE feedback_temp")
            
            # Recreate index
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_feedback_conversation ON feedback(conversation_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_feedback_timestamp ON feedback(timestamp)')
            
            conn.commit()
            logger.info("Fixed feedback table structure, added conversation_id column")
        
        # Check the comparisons table
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='comparisons'")
        if not cursor.fetchone():
            # Create comparisons table if it does not exist
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
            conn.commit()
            logger.info("Comparisons table created")
        
        # Check the stats table
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='stats'")
        if not cursor.fetchone():
            # Create stats table if it does not exist
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
            conn.commit()
            logger.info("Created stats table")
        
        logger.info("Database structure repair completed")
        return True
        
    except Exception as e:
        logger.error(f"Error while repairing database: {e}")
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()

# Script to run directly if needed
if __name__ == "__main__":
    # Thiết lập logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Default path
    default_db_path = "data/feedback.db"
    
    # Check if a path is provided
    import sys
    db_path = sys.argv[1] if len(sys.argv) > 1 else default_db_path
    
    # Repair database
    if fix_database_schema(db_path):
        print(f"Database repaired successfully: {db_path}")
    else:
        print(f"Unable to repair database: {db_path}")