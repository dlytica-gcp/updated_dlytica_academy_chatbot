from datetime import datetime
import re
import sqlite3
from langchain.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Dict, Any, Type, Optional, List
from chatbot.tools.date_tool import DateExtractionTool
from pydantic import PrivateAttr


class BookingInput(BaseModel):
    action: str = Field(..., description="'book' or 'cancel'")
    date: str = Field(..., description="Appointment date in YYYY-MM-DD format")
    time: str = Field(..., description="Appointment time in HH:MM format")
    user_info: Dict[str, str] = Field(..., description="User details including name, phone, and email")


class AppointmentBookingTool(BaseTool):
    name: str = "appointment_booking"
    description: str = (
        "Books or cancels appointments.\n"
        "Input should include:\n"
        "- 'action': 'book' or 'cancel'\n"
        "- 'date': YYYY-MM-DD\n"
        "- 'time': HH:MM\n"
        "- 'user_info': dictionary with 'name', 'phone', and 'email'"
    )
    args_schema: Type[BaseModel] = BookingInput

    _user_info_collector: Any = PrivateAttr()
    _date_tool: DateExtractionTool = PrivateAttr()

    db_name: str = 'user_info.db'
    available_slots: List[str] = [
        "09:00", "10:00", "11:00",
        "12:00", "13:00", "14:00",
        "15:00", "16:00", "17:00"
    ]

    def __init__(self, user_info_collector, date_tool, **data):
        super().__init__(**data)
        self._user_info_collector = user_info_collector
        self._date_tool = date_tool
        self._initialize_appointment_database()

    def _initialize_appointment_database(self):
        try:
            with sqlite3.connect(self.db_name) as conn:
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS appointments (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        date TEXT NOT NULL,
                        time TEXT NOT NULL,
                        status TEXT DEFAULT 'confirmed',
                        created_at TEXT NOT NULL,
                        FOREIGN KEY (user_id) REFERENCES user_data (id)
                    )
                ''')
        except Exception as e:
            print(f"Error initializing appointment DB: {e}")

    def _run(self, booking_info: Dict[str, Any], run_manager=None) -> str:
        if booking_info.get('action') == 'book':
            return self.book_appointment(booking_info)
        return self.cancel_appointment(booking_info)

    def _parse_time(self, time_str: str) -> Optional[str]:
        try:
            time_str = time_str.strip().upper()
            if not any(ampm in time_str for ampm in ["AM", "PM"]):
                hour = int(re.search(r'\d+', time_str).group())
                time_str += " AM" if hour < 12 else " PM"
            if ":" not in time_str:
                parts = time_str.split()
                time_str = f"{parts[0]}:00 {parts[1]}"
            return datetime.strptime(time_str, "%I:%M %p").strftime("%H:%M")
        except Exception as e:
            print(f"Error parsing time: {e}")
            return None

    def get_booked_slots(self, date_str: str) -> List[str]:
        try:
            with sqlite3.connect(self.db_name) as conn:
                cursor = conn.execute(
                    'SELECT time FROM appointments WHERE date = ? AND status = "confirmed"', (date_str,)
                )
                return [row[0] for row in cursor.fetchall()]
        except Exception as e:
            print(f"Error fetching booked slots: {e}")
            return []

    def get_available_slots(self, date_str: str) -> (List[str], Optional[str]):
        try:
            datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            return [], "Invalid date format. Use YYYY-MM-DD."
        booked = self.get_booked_slots(date_str)
        return [slot for slot in self.available_slots if slot not in booked], None

    def extract_time_from_query(self, query: str) -> Optional[str]:
        match = re.search(r'\b(?:at|for|@)?\s*(\d{1,2}(?::\d{2})?\s*(?:AM|PM|am|pm)?)\b', query, re.IGNORECASE)
        return self._parse_time(match.group(1)) if match else None

    def get_user_id(self, user_info: Dict[str, str]) -> Optional[int]:
        try:
            with sqlite3.connect(self.db_name) as conn:
                cursor = conn.execute('''
                    SELECT id FROM user_data 
                    WHERE name = ? AND phone = ? AND email = ?
                    ORDER BY created_at DESC LIMIT 1
                ''', (user_info['name'], user_info['phone'], user_info['email']))
                row = cursor.fetchone()
                return row[0] if row else None
        except Exception as e:
            print(f"Error retrieving user ID: {e}")
            return None

    def save_appointment(self, user_id: int, date_str: str, time_str: str) -> bool:
        try:
            with sqlite3.connect(self.db_name) as conn:
                conn.execute('''
                    INSERT INTO appointments (user_id, date, time, created_at)
                    VALUES (?, ?, ?, ?)
                ''', (user_id, date_str, time_str, datetime.now().isoformat()))
            return True
        except Exception as e:
            print(f"Error saving appointment: {e}")
            return False

    def book_appointment(self, booking_info: Dict[str, Any]) -> str:
        query = booking_info.get('query', '')
        date_str = booking_info.get('date') or self._date_tool.extract_date(query)
        time_str = booking_info.get('time') or self.extract_time_from_query(query)
        user_info = booking_info.get('user_info', self._user_info_collector.get_user_info())

        if not all(user_info.get(k) for k in ["name", "phone", "email"]):
            self._user_info_collector.appointment_date = date_str
            self._user_info_collector.appointment_time = time_str
            return self._user_info_collector.start_collection()

        available_slots, error = self.get_available_slots(date_str)
        if error:
            return error

        if not time_str:
            return (
                f"Available slots on {self._format_date(date_str)}:\n" +
                "\n".join(f"- {slot}" for slot in available_slots) +
                "\n\nPlease specify a time (e.g., 'at 2:00 PM')."
            )

        if time_str not in available_slots:
            return (
                f"Sorry, {time_str} is not available on {self._format_date(date_str)}.\n"
                "Available times:\n" +
                "\n".join(f"- {slot}" for slot in available_slots)
            )
            
        user_id = self.get_user_id(user_info)

        # If not found, try saving to database and retrieve again
        if not user_id and self._user_info_collector.save_to_database():
            user_info = self._user_info_collector.get_user_info()
            user_id = self.get_user_id(user_info)

        if not user_id:
            return "Could not save your user information. Please try again."

        # **New check: Prevent multiple active bookings per user**
        if db.has_active_booking(user_id):
            return (
                f"You already have an active appointment booked. "
                f"Please cancel your existing appointment before booking a new one."
            )

        if self.save_appointment(user_id, date_str, time_str):
            return (
                f"Appointment confirmed for {self._format_date(date_str)} at {time_str}.\n"
                f"Details:\n- Name: {user_info['name']}\n"
                f"- Phone: {user_info['phone']}\n"
                f"- Email: {user_info['email']}"
            )
        return "Failed to save appointment. Please contact support."


    def cancel_appointment(self, booking_info: Dict[str, Any]) -> str:
        date_str = booking_info.get('date')
        user_info = booking_info.get('user_info', self._user_info_collector.get_user_info())

        if not date_str:
            return "Please provide the date of the appointment to cancel."

        user_id = self.get_user_id(user_info)
        if not user_id:
            return "We couldn't find your information."

        try:
            with sqlite3.connect(self.db_name) as conn:
                cursor = conn.execute('''
                    UPDATE appointments
                    SET status = 'cancelled'
                    WHERE user_id = ? AND date = ? AND status = 'confirmed'
                ''', (user_id, date_str))
                if cursor.rowcount > 0:
                    return f"Your appointment on {self._format_date(date_str)} has been cancelled."
                return "No confirmed appointment found for that date."
        except Exception as e:
            print(f"Error cancelling appointment: {e}")
            return "Failed to cancel appointment. Please try again later."

    def _format_date(self, date_str: str) -> str:
        try:
            return datetime.strptime(date_str, "%Y-%m-%d").strftime("%A, %B %d, %Y")
        except ValueError:
            return date_str
