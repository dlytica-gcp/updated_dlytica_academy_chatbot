import os
import psycopg2
from psycopg2 import pool
from psycopg2.extras import DictCursor
from datetime import datetime
from dotenv import load_dotenv
from contextlib import contextmanager

load_dotenv()

class Database:
    def __init__(self):
        self.connection_pool = None
        self._initialize_pool()
        self._ensure_tables_exist()

    def _initialize_pool(self):
        """Initialize the connection pool"""
        try:
            self.connection_pool = psycopg2.pool.ThreadedConnectionPool(
                minconn=1,
                maxconn=10,
                dbname=os.getenv("DB_NAME"),
                user=os.getenv("DB_USER"),
                password=os.getenv("DB_PASSWORD"),
                host=os.getenv("DB_HOST"),
                port=os.getenv("DB_PORT")
            )
            dbname=os.getenv("DB_NAME"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            host=os.getenv("DB_HOST"),
            port=os.getenv("DB_PORT")
            print(dbname, user, host, port, password)
            
        except Exception as e:
            print(f"Error creating connection pool: {e}")
            raise

    def _ensure_tables_exist(self):
        """Ensure all required tables exist in the database"""
        with self.get_cursor() as cursor:
            # Create session_metadata table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS session_metadata (
                    session_id VARCHAR(36) PRIMARY KEY,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    expired_at TIMESTAMP,
                    last_activity TIMESTAMP NOT NULL,
                    user_agent TEXT,
                    ip_address VARCHAR(45)
                )
            """);
            # Create user_data table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_data (
                    id SERIAL PRIMARY KEY,
                    session_id VARCHAR(36) NOT NULL,
                    name TEXT NOT NULL,
                    phone TEXT NOT NULL,
                    email TEXT NOT NULL,
                    date TEXT,
                    time TEXT,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (session_id) REFERENCES session_metadata(session_id) ON DELETE CASCADE
                )
            """);
            
            # Create conversation_history table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS conversation_history (
                    id SERIAL PRIMARY KEY,
                    session_id VARCHAR(36) NOT NULL,
                    user_message TEXT NOT NULL,
                    bot_response TEXT NOT NULL,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (session_id) REFERENCES session_metadata(session_id) ON DELETE CASCADE
                )
            """);
            
            # Create indexes for better performance
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_conversation_history_session_id 
                ON conversation_history(session_id)
            """);
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_user_data_session_id 
                ON user_data(session_id)
            """);
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_user_data_email 
                ON user_data(email)
            """);

    @contextmanager
    def get_cursor(self):
        """Context manager for getting a cursor"""
        conn = None
        cursor = None
        try:
            conn = self.connection_pool.getconn()
            cursor = conn.cursor(cursor_factory=DictCursor)
            yield cursor
            conn.commit()
        except Exception as e:
            if conn:
                conn.rollback()
            print(f"Database operation failed: {e}")
            raise
        finally:
            if cursor:
                cursor.close()
            if conn:
                self.connection_pool.putconn(conn)

    def save_user_data(self, user_info, session_id):
        """Save user data to the database"""
        try:
            with self.get_cursor() as cursor:
                # First, check if there's an existing appointment for this user
                if user_info.get('email') and user_info.get('phone'):
                    cursor.execute("""
                        SELECT id FROM user_data 
                        WHERE email = %s AND phone = %s AND status = 'confirmed'
                        LIMIT 1
                    """, (user_info.get('email'), user_info.get('phone')))
                    existing = cursor.fetchone()
                    if existing:
                        raise ValueError("User already has a confirmed appointment")

                # Insert new appointment
                cursor.execute("""
                    INSERT INTO user_data 
                    (name, phone, email, date, time, status, created_at, session_id)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (
                    user_info.get('name'),
                    user_info.get('phone'),
                    user_info.get('email'),
                    user_info.get('date'),
                    user_info.get('time'),
                    user_info.get('status', 'confirmed'),
                    datetime.now(),
                    session_id
                ))
                return cursor.fetchone()[0]
        except Exception as e:
            print(f"Error saving user data: {e}")
            raise
            
    def cancel_booking(self, email, date=None, time=None):
        """Cancel a specific booking or any booking for email"""
        try:
            with self.get_cursor() as cursor:
                if date and time:
                    cursor.execute("""
                        UPDATE user_data 
                        SET status = 'cancelled'
                        WHERE email = %s AND date = %s AND time = %s
                        RETURNING id
                    """, (email, date, time))
                else:
                    cursor.execute("""
                        UPDATE user_data 
                        SET status = 'cancelled'
                        WHERE email = %s AND status = 'confirmed'
                        RETURNING id
                    """, (email,))
                return cursor.fetchone() is not None
        except Exception as e:
            print(f"Error canceling booking: {e}")
            return False

    def cancel_any_booking(self, email):
        """Cancel any confirmed booking for this email"""
        return self.cancel_booking(email)

    def log_conversation(self, session_id, user_message, bot_response):
        """Log a conversation exchange"""
        try:
            with self.get_cursor() as cursor:
                cursor.execute("""
                    INSERT INTO conversation_history 
                    (session_id, user_message, bot_response)
                    VALUES (%s, %s, %s)
                """, (session_id, user_message, bot_response))
        except Exception as e:
            print(f"Error logging conversation: {e}")
            raise
        
    def get_user_history(self, session_id):
        """Get conversation history for a session"""
        try:
            with self.get_cursor() as cursor:
                cursor.execute("""
                    SELECT user_message, bot_response, created_at
                    FROM conversation_history
                    WHERE session_id = %s
                    ORDER BY created_at ASC
                """, (session_id,))
                return cursor.fetchall()
        except Exception as e:
            print(f"Error getting user history: {e}")
            return []

    def log_session_start(self, session_id, user_agent=None, ip_address=None):
        """Log a new session start"""
        try:
            with self.get_cursor() as cursor:
                cursor.execute("""
                    INSERT INTO session_metadata 
                    (session_id, last_activity, user_agent, ip_address)
                    VALUES (%s, CURRENT_TIMESTAMP, %s, %s)
                    ON CONFLICT (session_id) 
                    DO UPDATE SET 
                        last_activity = EXCLUDED.last_activity,
                        expired_at = NULL,
                        user_agent = EXCLUDED.user_agent,
                        ip_address = EXCLUDED.ip_address;
                """, (session_id, user_agent, ip_address))

        except Exception as e:
            print(f"Error logging session start: {e}")
            raise

    def log_session_end(self, session_id):
        """Mark a session as ended"""
        try:
            with self.get_cursor() as cursor:
                cursor.execute("""
                    UPDATE session_metadata 
                    SET expired_at = CURRENT_TIMESTAMP 
                    WHERE session_id = %s
                """, (session_id,))
        except Exception as e:
            print(f"Error logging session end: {e}")
            raise

    def close(self):
        """Close all connections in the pool"""
        if self.connection_pool:
            self.connection_pool.closeall()
            
    def check_existing_appointment(self, email: str, phone: str):
        """Check if the user has an active appointment."""
        try:
            with self.get_cursor() as cursor:
                cursor.execute("""
                    SELECT date, time, status 
                    FROM user_data
                    WHERE email = %s AND phone = %s
                    ORDER BY created_at DESC
                    LIMIT 1
                """, (email, phone))
                row = cursor.fetchone()
                if row:
                    # Return a dict with the appointment details
                    return {"date": row["date"], "time": row["time"], "status": row["status"]}
                return None
        except Exception as e:
            print(f"Error checking existing appointment: {e}")
            return None

        
    def has_active_booking(self, email: str) -> bool:
        """Check if the user has an active (confirmed) appointment"""
        try:
            with self.get_cursor() as cursor:
                cursor.execute("""
                    SELECT 1 FROM user_data
                    WHERE email = %s AND status = 'confirmed'
                    LIMIT 1
                """, (email,))
                return cursor.fetchone() is not None
        except Exception as e:
            print(f"Error checking active booking: {e}")
            return False
        
    def is_time_slot_available(self, date: str, time: str) -> bool:
        try:
            with self.get_cursor() as cursor:
                cursor.execute("""
                    SELECT 1 FROM user_data
                    WHERE date = %s AND time = %s AND status = 'confirmed'
                    LIMIT 1
                """, (date, time))
                return cursor.fetchone() is None  # True if no appointment exists
        except Exception as e:
            print(f"Error checking time slot availability: {e}")
            return True  # Default to available on error
        
    def get_confirmed_appointment(self, email, phone):
        try:
            with self.get_cursor() as cursor:
                cursor.execute("""
                    SELECT date, time FROM user_data
                    WHERE email = %s AND phone = %s AND status = 'confirmed'
                    ORDER BY created_at DESC
                    LIMIT 1
                """, (email, phone))
                row = cursor.fetchone()
                if row:
                    return {"date": row["date"], "time": row["time"]}
                return None
        except Exception as e:
            print(f"Error fetching confirmed appointment: {e}")
            return None




# Singleton database instance
db = Database()