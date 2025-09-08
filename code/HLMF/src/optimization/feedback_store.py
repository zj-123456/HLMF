"""
Feedback storage and retrieval modules for RLHF
"""

import os
import sqlite3
import json
import logging
from typing import Dict, List, Any, Optional, Tuple, Union
from datetime import datetime
import sys

# Thêm đường dẫn hiện tại vào PYTHONPATH
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

logger = logging.getLogger(__name__)

class FeedbackStore:
    """
    Feedback Repositories using SQLite
    Archive:
    - Feedback on the answer.
    - Compare the DPO pair (Chosen versus Rejected)
    - Statistics that use
    """

    def __init__(self, db_path: str):
        """
        Initialize the feedback store

        Args:
            db_path: Path to the SQLite database file
        """
        self.db_path = db_path

        # Ensure the directory exists
        os.makedirs(os.path.dirname(db_path), exist_ok=True)

        # Initialize the database
        try:
            self._initialize_db()
            logger.info(f"Initialized feedback database at {db_path}")
        except Exception as e:
            logger.error(f"Error initializing database: {e}")
            # Attempt to repair the database
            self._fix_database_schema()

    def _initialize_db(self) -> None:
        """Initialize the database schema"""
        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Feedback table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS feedback (
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

            # Comparisons table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS comparisons (
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

            # Stats table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS stats (
                id TEXT PRIMARY KEY,
                timestamp TEXT NOT NULL,
                stat_type TEXT NOT NULL,
                value REAL NOT NULL,
                metadata TEXT
            )
            ''')

            # Indexes
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_feedback_conversation ON feedback(conversation_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_feedback_timestamp ON feedback(timestamp)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_comparisons_conversation ON comparisons(conversation_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_stats_type ON stats(stat_type)')

            conn.commit()

        except Exception as e:
            logger.error(f"Error initializing database: {e}")
            if conn:
                conn.rollback()
            raise
        finally:
            if conn:
                conn.close()

    def _fix_database_schema(self) -> bool:
        """
        Fix schema issues in the database

        Returns:
            True if successful, False otherwise
        """
        conn = None
        try:
            # Backup the database before fixing
            if os.path.exists(self.db_path):
                backup_path = f"{self.db_path}.backup"
                with open(self.db_path, 'rb') as src, open(backup_path, 'wb') as dst:
                    dst.write(src.read())
                logger.info(f"Backed up database to {backup_path}")

            # Connect to the database
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Check if the feedback table exists
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='feedback'")
            if cursor.fetchone():
                # Check the current table structure
                cursor.execute("PRAGMA table_info(feedback)")
                columns = cursor.fetchall()
                column_names = [col[1] for col in columns]

                # Check if the conversation_id column exists
                if "conversation_id" not in column_names:
                    # Create a temporary table to store data
                    cursor.execute("CREATE TABLE feedback_temp AS SELECT * FROM feedback")

                    # Drop the old table
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
                    try:
                        cursor.execute("SELECT * FROM feedback_temp LIMIT 1")
                        row = cursor.fetchone()
                        if row:
                            # Get column names from the temporary table
                            cursor.execute("PRAGMA table_info(feedback_temp)")
                            temp_columns = cursor.fetchall()
                            temp_column_names = [col[1] for col in temp_columns]

                            # Find common columns between the two tables
                            common_columns = [col for col in temp_column_names if col != "conversation_id"]
                            common_columns_str = ", ".join(common_columns)

                            # Copy data, setting conversation_id to empty string by default
                            insert_query = f"INSERT INTO feedback ({common_columns_str}, conversation_id) SELECT {common_columns_str}, '' FROM feedback_temp"
                            cursor.execute(insert_query)
                            logger.info(f"Moved {cursor.rowcount} records from the temporary table")

                    except Exception as e:
                        logger.error(f"Error moving data: {e}")

                    # Drop the temporary table
                    cursor.execute("DROP TABLE IF EXISTS feedback_temp")

                    # Recreate indexes
                    cursor.execute('CREATE INDEX IF NOT EXISTS idx_feedback_conversation ON feedback(conversation_id)')
                    cursor.execute('CREATE INDEX IF NOT EXISTS idx_feedback_timestamp ON feedback(timestamp)')

                    conn.commit()
                    logger.info("Fixed feedback table structure, added conversation_id column")
            else:
                # Create a new feedback table if it doesn't exist
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
                conn.commit()
                logger.info("Created new feedback table")

            # Check the comparisons table
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='comparisons'")
            if not cursor.fetchone():
                # Create the comparisons table if it doesn't exist
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
                cursor.execute(
                    'CREATE INDEX IF NOT EXISTS idx_comparisons_conversation ON comparisons(conversation_id)')
                conn.commit()
                logger.info("Created comparisons table")

            # Check the stats table
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='stats'")
            if not cursor.fetchone():
                # Create the stats table if it doesn't exist
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

            logger.info("Completed database schema repair")
            return True

        except Exception as e:
            logger.error(f"Error repairing database: {e}")
            if conn:
                conn.rollback()
            return False
        finally:
            if conn:
                conn.close()

    def save_feedback(self, feedback_data: Dict[str, Any]) -> Optional[str]:
        """
        Save a feedback record

        Args:
            feedback_data: Dict containing feedback data

        Returns:
            ID of the record if successful, None otherwise
        """
        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Prepare data
            feedback_id = feedback_data.get("id")
            if not feedback_id:
                return None

            # Ensure conversation_id is not null
            conversation_id = feedback_data.get("conversation_id", "")

            # Convert responses to JSON
            responses_json = json.dumps(feedback_data.get("responses", {}),
                                        ensure_ascii=False)

            # Convert metadata to JSON
            metadata = {k: v for k, v in feedback_data.items()
                        if k not in ["id", "timestamp", "conversation_id", "query",
                                     "responses", "selected_response",
                                     "feedback_score", "feedback_text"]}
            metadata_json = json.dumps(metadata, ensure_ascii=False) if metadata else None

            # Insert into the database
            cursor.execute('''
            INSERT OR REPLACE INTO feedback 
            (id, timestamp, conversation_id, query, responses, selected_response, 
             feedback_score, feedback_text, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                feedback_id,
                feedback_data.get("timestamp", datetime.now().isoformat()),
                conversation_id,
                feedback_data.get("query", ""),
                responses_json,
                feedback_data.get("selected_response", ""),
                feedback_data.get("feedback_score"),
                feedback_data.get("feedback_text"),
                metadata_json
            ))

            conn.commit()
            return feedback_id

        except Exception as e:
            logger.error(f"Error saving feedback: {e}")
            if conn:
                conn.rollback()
            # Attempt to fix schema and retry
            if "no such column: conversation_id" in str(e):
                self._fix_database_schema()
                return self.save_feedback(feedback_data)
            return None
        finally:
            if conn:
                conn.close()

    def save_comparison(self, comparison_data: Dict[str, Any]) -> Optional[str]:
        """
        Lưu bản ghi so sánh cặp

        Args:
            comparison_data: Dict chứa dữ liệu so sánh

        Returns:
            ID của bản ghi nếu thành công, None nếu thất bại
        """
        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Chuẩn bị dữ liệu
            comparison_id = comparison_data.get("id")
            if not comparison_id:
                return None

            # Đảm bảo conversation_id không bị null
            conversation_id = comparison_data.get("conversation_id", "")

            # Chuyển đổi metadata thành JSON
            metadata = {k: v for k, v in comparison_data.items()
                      if k not in ["id", "timestamp", "conversation_id", "query",
                                 "chosen", "rejected", "chosen_model", "rejected_model"]}
            metadata_json = json.dumps(metadata, ensure_ascii=False) if metadata else None

            # Chèn vào cơ sở dữ liệu
            cursor.execute('''
            INSERT OR REPLACE INTO comparisons 
            (id, timestamp, conversation_id, query, chosen, rejected, 
             chosen_model, rejected_model, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                comparison_id,
                comparison_data.get("timestamp", datetime.now().isoformat()),
                conversation_id,
                comparison_data.get("query", ""),
                comparison_data.get("chosen", ""),
                comparison_data.get("rejected", ""),
                comparison_data.get("chosen_model", ""),
                comparison_data.get("rejected_model", ""),
                metadata_json
            ))

            conn.commit()
            return comparison_id

        except Exception as e:
            logger.error(f"Lỗi khi lưu so sánh: {e}")
            if conn:
                conn.rollback()
            # Thử sửa lỗi schema và thử lại
            if "no such column: conversation_id" in str(e):
                self._fix_database_schema()
                return self.save_comparison(comparison_data)
            return None
        finally:
            if conn:
                conn.close()

    # Các phương thức khác giữ nguyên...
    # (Các phương thức get_feedback, get_comparison, get_all_feedback, v.v.)

    def get_feedback(self, feedback_id: str) -> Optional[Dict[str, Any]]:
        """
        Lấy bản ghi phản hồi theo ID

        Args:
            feedback_id: ID của bản ghi phản hồi

        Returns:
            Dict chứa dữ liệu phản hồi hoặc None nếu không tìm thấy
        """
        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Truy vấn cơ sở dữ liệu
            cursor.execute('''
            SELECT * FROM feedback WHERE id = ?
            ''', (feedback_id,))

            row = cursor.fetchone()
            if not row:
                return None

            # Chuyển đổi từ Row sang Dict
            feedback_data = dict(row)

            # Chuyển đổi JSON thành Dict
            feedback_data["responses"] = json.loads(feedback_data["responses"])
            if feedback_data["metadata"]:
                metadata = json.loads(feedback_data["metadata"])
                for key, value in metadata.items():
                    feedback_data[key] = value

            del feedback_data["metadata"]

            return feedback_data

        except Exception as e:
            logger.error(f"Lỗi khi lấy phản hồi: {e}")
            return None
        finally:
            if conn:
                conn.close()

    def get_comparison(self, comparison_id: str) -> Optional[Dict[str, Any]]:
        """
        Lấy bản ghi so sánh cặp theo ID

        Args:
            comparison_id: ID của bản ghi so sánh

        Returns:
            Dict chứa dữ liệu so sánh hoặc None nếu không tìm thấy
        """
        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Truy vấn cơ sở dữ liệu
            cursor.execute('''
            SELECT * FROM comparisons WHERE id = ?
            ''', (comparison_id,))

            row = cursor.fetchone()
            if not row:
                return None

            # Chuyển đổi từ Row sang Dict
            comparison_data = dict(row)

            # Chuyển đổi JSON thành Dict
            if comparison_data["metadata"]:
                metadata = json.loads(comparison_data["metadata"])
                for key, value in metadata.items():
                    comparison_data[key] = value

            del comparison_data["metadata"]

            return comparison_data

        except Exception as e:
            logger.error(f"Lỗi khi lấy so sánh: {e}")
            return None
        finally:
            if conn:
                conn.close()
    
    def get_all_feedback(self) -> List[Dict[str, Any]]:
        """
        Lấy tất cả bản ghi phản hồi
        
        Returns:
            Danh sách các Dict chứa dữ liệu phản hồi
        """
        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Lấy tất cả phản hồi
            try:
                cursor.execute('''
                SELECT * FROM feedback ORDER BY timestamp DESC
                ''')
                feedback_rows = cursor.fetchall()
            except sqlite3.OperationalError as e:
                if "no such column: conversation_id" in str(e):
                    self._fix_database_schema()
                    conn.close()
                    return self.get_all_feedback()
                feedback_rows = []
            
            # Lấy tất cả so sánh
            try:
                cursor.execute('''
                SELECT * FROM comparisons ORDER BY timestamp DESC
                ''')
                comparison_rows = cursor.fetchall()
            except sqlite3.OperationalError:
                comparison_rows = []
            
            results = []
            
            # Xử lý các bản ghi phản hồi
            for row in feedback_rows:
                feedback_data = dict(row)
                
                # Chuyển đổi JSON thành Dict
                feedback_data["responses"] = json.loads(feedback_data["responses"])
                if feedback_data["metadata"]:
                    metadata = json.loads(feedback_data["metadata"])
                    for key, value in metadata.items():
                        feedback_data[key] = value
                        
                del feedback_data["metadata"]
                results.append(feedback_data)
                
            # Xử lý các bản ghi so sánh
            for row in comparison_rows:
                comparison_data = dict(row)
                
                # Chuyển đổi JSON thành Dict
                if comparison_data["metadata"]:
                    metadata = json.loads(comparison_data["metadata"])
                    for key, value in metadata.items():
                        comparison_data[key] = value
                        
                comparison_data["type"] = "pairwise_comparison"
                del comparison_data["metadata"]
                results.append(comparison_data)
                
            return results
            
        except Exception as e:
            logger.error(f"Lỗi khi lấy tất cả phản hồi: {e}")
            return []
        finally:
            if conn:
                conn.close()

    def get_feedback(self, feedback_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a feedback record by ID

        Args:
            feedback_id: ID of the feedback record

        Returns:
            Dict containing feedback data or None if not found
        """
        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Query the database
            cursor.execute('''
            SELECT * FROM feedback WHERE id = ?
            ''', (feedback_id,))

            row = cursor.fetchone()
            if not row:
                return None

            # Convert Row to Dict
            feedback_data = dict(row)

            # Convert JSON to Dict
            feedback_data["responses"] = json.loads(feedback_data["responses"])
            if feedback_data["metadata"]:
                metadata = json.loads(feedback_data["metadata"])
                for key, value in metadata.items():
                    feedback_data[key] = value

            del feedback_data["metadata"]

            return feedback_data

        except Exception as e:
            logger.error(f"Error retrieving feedback: {e}")
            return None
        finally:
            if conn:
                conn.close()

    def get_comparison(self, comparison_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a pairwise comparison record by ID

        Args:
            comparison_id: ID of the comparison record

        Returns:
            Dict containing comparison data or None if not found
        """
        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Query the database
            cursor.execute('''
            SELECT * FROM comparisons WHERE id = ?
            ''', (comparison_id,))

            row = cursor.fetchone()
            if not row:
                return None

            # Convert Row to Dict
            comparison_data = dict(row)

            # Convert JSON to Dict
            if comparison_data["metadata"]:
                metadata = json.loads(comparison_data["metadata"])
                for key, value in metadata.items():
                    comparison_data[key] = value

            del comparison_data["metadata"]

            return comparison_data

        except Exception as e:
            logger.error(f"Error retrieving comparison: {e}")
            return None
        finally:
            if conn:
                conn.close()

    def get_total_count(self) -> int:
        """
        Get the total number of feedback records

        Returns:
            The total number of feedback records
        """
        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('SELECT COUNT(*) FROM feedback')
            feedback_count = cursor.fetchone()[0]

            cursor.execute('SELECT COUNT(*) FROM comparisons')
            comparison_count = cursor.fetchone()[0]

            return feedback_count + comparison_count

        except Exception as e:
            logger.error(f"Error retrieving total record count: {e}")
            if "no such column: conversation_id" in str(e):
                self._fix_database_schema()
                return self.get_total_count()
            return 0
        finally:
            if conn:
                conn.close()

    def get_count_by_score(self, min_score: Optional[float] = None,
                           max_score: Optional[float] = None) -> int:
        """
        Get the number of feedback records within a score range

        Args:
            min_score: Minimum score (optional)
            max_score: Maximum score (optional)

        Returns:
            The number of feedback records within the score range
        """
        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Build the query based on conditions
            query = 'SELECT COUNT(*) FROM feedback WHERE feedback_score IS NOT NULL'
            params = []

            if min_score is not None:
                query += ' AND feedback_score >= ?'
                params.append(min_score)

            if max_score is not None:
                query += ' AND feedback_score <= ?'
                params.append(max_score)

            cursor.execute(query, params)
            count = cursor.fetchone()[0]

            return count

        except Exception as e:
            logger.error(f"Error retrieving feedback count by score: {e}")
            if "no such column: conversation_id" in str(e):
                self._fix_database_schema()
                return self.get_count_by_score(min_score, max_score)
            return 0
        finally:
            if conn:
                conn.close()

    def delete_feedback(self, feedback_id: str) -> bool:
        """
        Delete a feedback record

        Args:
            feedback_id: ID of the feedback record

        Returns:
            True if deletion is successful, False otherwise
        """
        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('DELETE FROM feedback WHERE id = ?', (feedback_id,))
            conn.commit()

            return cursor.rowcount > 0

        except Exception as e:
            logger.error(f"Error deleting feedback: {e}")
            if conn:
                conn.rollback()
            return False
        finally:
            if conn:
                conn.close()

    def delete_comparison(self, comparison_id: str) -> bool:
        """
        Delete a comparison record

        Args:
            comparison_id: ID of the comparison record

        Returns:
            True if deletion is successful, False otherwise
        """
        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('DELETE FROM comparisons WHERE id = ?', (comparison_id,))
            conn.commit()

            return cursor.rowcount > 0

        except Exception as e:
            logger.error(f"Error deleting comparison: {e}")
            if conn:
                conn.rollback()
            return False
        finally:
            if conn:
                conn.close()

    def clear_all_data(self) -> bool:
        """
        Delete all data

        Returns:
            True if deletion is successful, False otherwise
        """
        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('DELETE FROM feedback')
            cursor.execute('DELETE FROM comparisons')
            cursor.execute('DELETE FROM stats')
            conn.commit()

            return True

        except Exception as e:
            logger.error(f"Error deleting all data: {e}")
            if conn:
                conn.rollback()
            return False
        finally:
            if conn:
                conn.close()

    def update_stat(self, stat_type: str, value: float, metadata: Optional[Dict] = None) -> bool:
        """
        Cập nhật thống kê

        Args:
            stat_type: Loại thống kê
            value: Giá trị
            metadata: Dữ liệu bổ sung (tùy chọn)

        Returns:
            True nếu cập nhật thành công, False nếu không
        """
        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Tạo ID thống kê
            stat_id = f"{stat_type}_{datetime.now().strftime('%Y%m%d%H%M%S')}"

            # Chuyển đổi metadata thành JSON
            metadata_json = json.dumps(metadata, ensure_ascii=False) if metadata else None

            # Chèn vào cơ sở dữ liệu
            cursor.execute('''
            INSERT INTO stats (id, timestamp, stat_type, value, metadata)
            VALUES (?, ?, ?, ?, ?)
            ''', (
                stat_id,
                datetime.now().isoformat(),
                stat_type,
                value,
                metadata_json
            ))

            conn.commit()
            return True

        except Exception as e:
            logger.error(f"Lỗi khi cập nhật thống kê: {e}")
            if conn:
                conn.rollback()
            return False
        finally:
            if conn:
                conn.close()

    def get_stats(self, stat_type: Optional[str] = None,
                  limit: int = 100) -> List[Dict[str, Any]]:
        """
        Lấy thống kê

        Args:
            stat_type: Loại thống kê (tùy chọn)
            limit: Số lượng bản ghi tối đa

        Returns:
            Danh sách các Dict chứa thống kê
        """
        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Xây dựng truy vấn
            query = 'SELECT * FROM stats'
            params = []

            if stat_type:
                query += ' WHERE stat_type = ?'
                params.append(stat_type)

            query += ' ORDER BY timestamp DESC LIMIT ?'
            params.append(limit)

            cursor.execute(query, params)
            rows = cursor.fetchall()
            results = []

            for row in rows:
                stat_data = dict(row)

                # Chuyển đổi JSON thành Dict
                if stat_data["metadata"]:
                    metadata = json.loads(stat_data["metadata"])
                    for key, value in metadata.items():
                        stat_data[key] = value

                del stat_data["metadata"]
                results.append(stat_data)

            return results

        except Exception as e:
            logger.error(f"Lỗi khi lấy thống kê: {e}")
            return []
        finally:
            if conn:
                conn.close()

    def get_feedback_stats(self) -> Dict[str, Any]:
        """
        Retrieve aggregated feedback statistics

        Returns:
            Dict containing feedback statistics
        """
        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Number of feedback by score range
            cursor.execute('''
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN feedback_score >= 0.8 THEN 1 ELSE 0 END) as positive,
                SUM(CASE WHEN feedback_score <= 0.3 THEN 1 ELSE 0 END) as negative,
                SUM(CASE WHEN feedback_score > 0.3 AND feedback_score < 0.8 THEN 1 ELSE 0 END) as neutral,
                AVG(feedback_score) as avg_score
            FROM feedback
            WHERE feedback_score IS NOT NULL
            ''')

            score_stats = cursor.fetchone()

            # Number of feedback by model
            cursor.execute('''
            SELECT selected_response, COUNT(*) as count
            FROM feedback
            GROUP BY selected_response
            ORDER BY count DESC
            ''')

            model_stats = {row[0]: row[1] for row in cursor.fetchall()}

            # Number of pairwise comparisons
            cursor.execute('SELECT COUNT(*) FROM comparisons')
            comparison_count = cursor.fetchone()[0]

            # Statistics over time
            cursor.execute('''
            SELECT 
                strftime('%Y-%m-%d', timestamp) as date,
                COUNT(*) as count
            FROM feedback
            GROUP BY date
            ORDER BY date DESC
            LIMIT 30
            ''')

            daily_stats = {row[0]: row[1] for row in cursor.fetchall()}

            return {
                "total_feedback": score_stats[0] if score_stats else 0,
                "positive_feedback": score_stats[1] if score_stats else 0,
                "negative_feedback": score_stats[2] if score_stats else 0,
                "neutral_feedback": score_stats[3] if score_stats else 0,
                "average_score": score_stats[4] if score_stats else 0,
                "model_distribution": model_stats,
                "comparison_count": comparison_count,
                "daily_stats": daily_stats
            }

        except Exception as e:
            logger.error(f"Error retrieving feedback statistics: {e}")
            if "no such column: conversation_id" in str(e):
                self._fix_database_schema()
                return self.get_feedback_stats()
            return {}
        finally:
            if conn:
                conn.close()

    def backup_database(self, backup_path: Optional[str] = None) -> bool:
        """
        Backup the database

        Args:
            backup_path: Path to the backup file (optional)

        Returns:
            True if backup is successful, False otherwise
        """
        if not backup_path:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_dir = os.path.join(os.path.dirname(self.db_path), "backups")
            os.makedirs(backup_dir, exist_ok=True)
            backup_path = os.path.join(backup_dir, f"feedback_backup_{timestamp}.db")

        source_conn = None
        dest_conn = None

        try:
            # Connect to the source database
            source_conn = sqlite3.connect(self.db_path)

            # Ensure the destination directory exists
            os.makedirs(os.path.dirname(backup_path), exist_ok=True)

            # Backup the database
            with open(backup_path, 'wb') as f:
                for line in source_conn.iterdump():
                    f.write(f"{line}\n".encode('utf-8'))

            logger.info(f"Backed up database to {backup_path}")
            return True

        except Exception as e:
            logger.error(f"Error backing up database: {e}")
            return False
        finally:
            if source_conn:
                source_conn.close()
            if dest_conn:
                dest_conn.close()

    def restore_database(self, backup_path: str) -> bool:
        """
        Restore the database from a backup

        Args:
            backup_path: Path to the backup file

        Returns:
            True if restoration is successful, False otherwise
        """
        if not os.path.exists(backup_path):
            logger.error(f"Backup file does not exist: {backup_path}")
            return False

        # Create a backup before restoring
        self.backup_database()

        conn = None
        try:
            # Delete the current database
            if os.path.exists(self.db_path):
                os.remove(self.db_path)

            # Initialize a new database
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Read and execute SQL commands from the backup file
            with open(backup_path, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip() and not line.startswith('PRAGMA') and not line.startswith(
                            'BEGIN') and not line.startswith('COMMIT'):
                        cursor.execute(line)

            conn.commit()
            logger.info(f"Restored database from {backup_path}")
            return True

        except Exception as e:
            logger.error(f"Error restoring database: {e}")
            if conn:
                conn.rollback()
            return False
        finally:
            if conn:
                conn.close()