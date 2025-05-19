import re
from datetime import datetime
from langchain.chains import ConversationChain
from langchain.memory import ConversationBufferMemory
from dateutil import parser as date_parser
from chatbot.tools.date_tool import DateExtractionTool
from chatbot.database import db
from datetime import datetime, timedelta
        
class UserInfoCollector:
    def __init__(self, llm, session_id=None):
        self.llm = llm
        self.session_id = session_id
        self.user_info = {
            "name": None,
            "phone": None,
            "email": None,
            "date": None,
            "time": None,
            "status": None,
            "created_at": None
        }
        self.current_field = None
        self.memory = ConversationBufferMemory()
        self.conversation = ConversationChain(llm=llm, memory=self.memory)
        self.date_tool = DateExtractionTool()

        # Add these attributes that the booking tool expects
        self.appointment_date = None
        self.appointment_time = None
        self.name = "user_info_collector"  # Add a name attribute
        # self.session_id = session_id

    def validate_name(self, name):
        name = name.strip()
        if len(name) < 3 or len(name.split()) < 2 or ' ' not in name:
            return False
        return bool(re.match(r"^[a-zA-Zà-üÀ-Ü'\- ]+$", name))

    def validate_email(self, email):
        pattern = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
        return bool(re.match(pattern, email))

    def clear_info(self):
        self.user_info = {
            "name": None,
            "phone": None,
            "email": None,
            "date": None,
            "time": None,
            "status": None,
            "created_at": None,
            "session_id": None
        }
        self.current_field = None
        
    def validate_appointment_time(self, date_str, time_str):
        """
        Validate if the selected date and time are not in the past and have at least 3 hours gap.
        """
        try:
            # Parse the given date and time
            appointment_datetime_str = f"{date_str} {time_str}"
            appointment_datetime = datetime.strptime(appointment_datetime_str, "%Y-%m-%d %H:%M")
            
            # Get current time
            current_datetime = datetime.now()

            # Ensure the appointment is not in the past
            if appointment_datetime < current_datetime:
                return False, "You cannot schedule an appointment in the past."

            # Ensure the appointment is at least 3 hours from now
            if appointment_datetime < current_datetime + timedelta(hours=3):
                return False, "Please schedule the appointment at least 3 hours from now."

            return True, None
        
        except Exception as e:
            print(f"Error validating appointment time: {e}")
            return False, "Invalid date or time format. Please try again."
        
    def validate_phone(self, phone):
        if not phone:
            return True
        cleaned = re.sub(r'(?!^\+)[\D]', '', phone)
        if not cleaned.startswith('+') and not cleaned.startswith('977'):
            if len(cleaned) == 10:
                return re.match(r'^97\d{8}$|^98\d{8}$', cleaned)
            return False
        if cleaned.startswith('977'):
            num = cleaned[3:]
            return len(num) == 10 and re.match(r'^97\d{8}$|^98\d{8}$', num)
        elif cleaned.startswith('+977'):
            num = cleaned[4:]
            return len(num) == 10 and re.match(r'^97\d{8}$|^98\d{8}$', num)
        elif cleaned.startswith('+'):
            country_codes = {
                '1': (10, 11), '44': (9, 10), '61': (8, 9),
                '49': (9, 11), '33': (8, 9), '81': (9, 10), '91': (10, 10)
            }
            for code, lengths in country_codes.items():
                if cleaned.startswith('+' + code):
                    num_len = len(cleaned[len(code) + 1:])
                    return lengths[0] <= num_len <= lengths[1]
            return 8 <= len(cleaned[1:]) <= 15
        return False

    def validate_time(self, time_input):
        try:
            # Handle "4pm" format
            if not any(c in time_input for c in [':', 'am', 'pm', 'AM', 'PM']):
                if time_input.isdigit():
                    hour = int(time_input)
                    time_input = f"{hour}:00 {'PM' if hour >= 12 else 'AM'}"
                else:
                    time_input = time_input.replace(' ', '') + ':00'
                    
            parsed_time = date_parser.parse(time_input).time()
            return parsed_time.strftime("%H:%M")
        except Exception as e:
            print(f"Time parsing error: {e}")
            return None
    
    def has_booking(self):
        """Check if the user has a booking in their user_info"""
        return (self.user_info.get("email") is not None and 
                self.user_info.get("date") is not None and 
                self.user_info.get("time") is not None and
                self.user_info.get("status") == "confirmed")
    
    def is_time_slot_available(self, date, time):
        """Check if the time slot is available for the given date"""
        try:
            return db.is_time_slot_available(date, time)
        except Exception as e:
            print(f"Error checking time slot availability: {e}")
            # Default to available if there's an error
            return True
    def _get_current_session_id(self):
        """Get the current session ID if available"""
        try:
            # This assumes you have access to the session ID somewhere
            # You'll need to adapt this to how your application manages sessions
            return getattr(self, "session_id", None)
        except Exception:
            return None

    def get_available_times(self):
        return ["09:00", "10:00", "11:00", "12:00", "13:00", "14:00", "15:00", "16:00", "17:00"]
    
    # def process_input(self, user_input):
        
    #     print(f"Processing input in UserInfoCollector: {user_input}, current_field: {self.current_field}")
    #     user_input_lower = user_input.lower()

    #     # If user already booked in this session & tries to book again
    #     if self.has_booking() and any(word in user_input_lower for word in ["yes", "book", "schedule", "make", "new"]):
    #         if "new" in user_input_lower or "another" in user_input_lower:
    #             self.clear_info()
    #             self.current_field = "name"
    #             return "Let's schedule a new appointment. What's your full name?"
    #         else:
    #             return (
    #                 f"You already have an appointment scheduled for {self.user_info['date']} at "
    #                 f"{self.user_info['time']}. To schedule a new appointment, please cancel the current one by saying 'cancel appointment'."
    #             )

    #     # If user wants to keep existing booking explicitly
    #     if self.has_booking() and any(word in user_input_lower for word in ["no", "keep", "maintain", "existing"]):
    #         return f"Great! Your appointment for {self.user_info['date']} at {self.user_info['time']} is confirmed."

    #     # Check if user already has a pending/confirmed appointment in DB (before fully collecting info)
    #     if self.user_info.get("email") and self.user_info.get("phone"):
    #         existing_appointment = db.check_existing_appointment(self.user_info["email"], self.user_info["phone"])
    #         if existing_appointment:
    #             self.user_info.update({
    #                 "date": existing_appointment.get("date"),
    #                 "time": existing_appointment.get("time"),
    #                 "status": existing_appointment.get("status")
    #             })
    #             if existing_appointment.get("status") == "confirmed":
    #                 return (f"You already have a pending appointment scheduled for {existing_appointment['date']} "
    #                         f"at {existing_appointment['time']}. If you'd like to cancel it, please say 'cancel appointment'.")
    #             elif existing_appointment.get("status") == "confirmed":
    #                 return (f"You already have a confirmed appointment for {existing_appointment['date']} "
    #                         f"at {existing_appointment['time']}. Please contact support if you'd like to change it.")

    #     # Collect Name
    #     if self.current_field == "name":
    #         name = user_input.strip()
    #         if not name:
    #             return "Please provide your full name. This field cannot be empty."
    #         if not self.validate_name(name):
    #             return "Please provide your complete full name (e.g., 'John Smith')."
    #         self.user_info["name"] = name
    #         self.current_field = "phone"
    #         return "Thank you! Please provide your phone number."

    #     # Collect Phone
    #     if self.current_field == "phone":
    #         if not user_input.strip():
    #             self.user_info["phone"] = ""
    #             self.current_field = "email"
    #             return "We'll contact you by email then. What's your email address?"
    #         if not self.validate_phone(user_input.strip()):
    #             return "Please enter a valid phone number (Nepali or international with country code)."
    #         self.user_info["phone"] = user_input.strip()
    #         self.current_field = "email"
    #         return "Great! What's your email address?"

    #     # Collect Email
    #     if self.current_field == "email":
    #         email = user_input.strip()
    #         if not email:
    #             return "Please provide your email address."
    #         if self.validate_email(email):
    #             self.user_info["email"] = email

    #             # Check DB for existing confirmed appointment
    #             existing_appointment = db.get_confirmed_appointment(email, self.user_info.get("phone", ""))
    #             if existing_appointment:
    #                 self.user_info.update({
    #                     "date": existing_appointment.get("date"),
    #                     "time": existing_appointment.get("time"),
    #                     "status": "confirmed"
    #                 })
    #                 self.current_field = None  # stop collecting since appointment exists
    #                 return (f"You already have a confirmed appointment for "
    #                         f"{existing_appointment['date']} at {existing_appointment['time']}. "
    #                         "If you'd like to book a new appointment, please cancel the previous booking first.")
    #             self.current_field = "date"
    #             return "Thanks! When would you like to schedule the appointment?"
    #         else:
    #             return "Please enter a valid email address."

    #     # Collect Date
    #     if self.current_field == "date":
    #         extracted_date = self.date_tool.extract_date(user_input)
    #         if extracted_date == "WEEKEND":
    #             return "Appointments cannot be scheduled on weekends. Please choose a weekday."
    #         elif extracted_date:
    #             self.user_info["date"] = extracted_date
    #             self.current_field = "time"
    #             return "What time would you prefer for the appointment?"
    #         else:
    #             return "Couldn't understand the date. Try formats like 'next Friday' or '2025-01-01'."

    #     # Collect Time and finalize booking
    #     if self.current_field == "time":
    #         formatted_time = self.validate_time(user_input)
    #         if formatted_time:
    #             if self.is_time_slot_available(self.user_info["date"], formatted_time):
    #                 if formatted_time in self.get_available_times():
    #                     self.user_info["time"] = formatted_time
    #                     self.user_info["created_at"] = datetime.now()
    #                     self.user_info["status"] = "confirmed"
    #                     self.current_field = None

    #                     # Save to database
    #                     session_id = self._get_current_session_id()
                        
    #                     session_id = self._get_current_session_id()
    #                     if not session_id:
    #                         # log or raise error or return message indicating session ID missing
    #                         print("Warning: session_id is None when trying to save appointment!")
    #                         return "Sorry, session information is missing. Please try again."
                        
    #                     try:
    #                         db.save_user_data(self.user_info, session_id)
    #                     except Exception as e:
    #                         return "Error saving your appointment. Please try again."

    #                     return (f"Thanks, {self.user_info['name']}! Your appointment is confirmed for:\n"
    #                             f"- Date: {self.user_info['date']}\n"
    #                             f"- Time: {formatted_time}\n"
    #                             f"Contact:\n"
    #                             f"- Email: {self.user_info['email']}\n"
    #                             f"- Phone: {self.user_info['phone'] or 'Not provided'}")
    #                 else:
    #                     return f"{formatted_time} is not available. Choose from: {', '.join(self.get_available_times())}"
    #             else:
    #                 return f"Sorry, {formatted_time} on {self.user_info['date']} is already booked. Please choose another time."
    #         else:
    #             return "Invalid time format. Try formats like '10 AM' or '14:30'."
            
    #         print(f"Processing input in UserInfoCollector: {user_input}, current_field: {self.current_field}")
    
    
    def process_input(self, user_input):
        print(f"Processing input in UserInfoCollector: {user_input}, current_field: {self.current_field}")
        user_input_lower = user_input.lower()

        # If user already booked in this session & tries to book again
        if self.has_booking() and any(word in user_input_lower for word in ["yes", "book", "schedule", "make", "new"]):
            if "new" in user_input_lower or "another" in user_input_lower:
                self.clear_info()
                self.current_field = "name"
                return "Let's schedule a new appointment. What's your full name?"
            else:
                return (
                    f"You already have an appointment scheduled for {self.user_info['date']} at "
                    f"{self.user_info['time']}. To schedule a new appointment, please cancel the current one by saying 'cancel appointment'."
                )

        # If user wants to keep existing booking explicitly
        if self.has_booking() and any(word in user_input_lower for word in ["no", "keep", "maintain", "existing"]):
            return f"Great! Your appointment for {self.user_info['date']} at {self.user_info['time']} is confirmed."

        # Check if user already has a pending/confirmed appointment in DB (before fully collecting info)
        if self.user_info.get("email") and self.user_info.get("phone"):
            existing_appointment = db.check_existing_appointment(self.user_info["email"], self.user_info["phone"])
            if existing_appointment:
                self.user_info.update({
                    "date": existing_appointment.get("date"),
                    "time": existing_appointment.get("time"),
                    "status": existing_appointment.get("status")
                })
                if existing_appointment.get("status") == "confirmed":
                    return (f"You already have a confirmed appointment for {existing_appointment['date']} "
                            f"at {existing_appointment['time']}. Please contact support if you'd like to change it.")

        # Collect Name
        if self.current_field == "name":
            name = user_input.strip()
            if not name:
                return "Please provide your full name. This field cannot be empty."
            if not self.validate_name(name):
                return "Please provide your complete full name (e.g., 'John Smith')."
            self.user_info["name"] = name
            self.current_field = "phone"
            return "Thank you! Please provide your phone number."

        # Collect Phone
        if self.current_field == "phone":
            if not user_input.strip():
                self.user_info["phone"] = ""
                self.current_field = "email"
                return "We'll contact you by email then. What's your email address?"
            if not self.validate_phone(user_input.strip()):
                return "Please enter a valid phone number (Nepali or international with country code)."
            self.user_info["phone"] = user_input.strip()
            self.current_field = "email"
            return "Great! What's your email address?"

        # Collect Email
        if self.current_field == "email":
            email = user_input.strip()
            if not email:
                return "Please provide your email address."
            if self.validate_email(email):
                self.user_info["email"] = email

                # Check DB for existing confirmed appointment
                existing_appointment = db.get_confirmed_appointment(email, self.user_info.get("phone", ""))
                if existing_appointment:
                    self.user_info.update({
                        "date": existing_appointment.get("date"),
                        "time": existing_appointment.get("time"),
                        "status": "confirmed"
                    })
                    self.current_field = None  # stop collecting since appointment exists
                    return (f"You already have a confirmed appointment for "
                            f"{existing_appointment['date']} at {existing_appointment['time']}. "
                            "If you'd like to book a new appointment, please cancel the previous booking first.")
                self.current_field = "date"
                return "Thanks! When would you like to schedule the appointment?"
            else:
                return "Please enter a valid email address."

        # Collect Date
        if self.current_field == "date":
            extracted_date = self.date_tool.extract_date(user_input)
            if extracted_date == "WEEKEND":
                return "Appointments cannot be scheduled on weekends. Please choose a weekday."
            elif extracted_date:
                self.user_info["date"] = extracted_date
                self.current_field = "time"
                return "What time would you prefer for the appointment?"
            else:
                return "Couldn't understand the date. Try formats like 'next Friday' or '2025-01-01'."

        # Collect Time and finalize booking
        if self.current_field == "time":
            formatted_time = self.validate_time(user_input)

            if formatted_time:
                # Check if appointment is at least 3 hours away from current time and not in the past
                try:
                    # Combine date and time for the full appointment datetime
                    appointment_datetime_str = f"{self.user_info['date']} {formatted_time}"
                    appointment_datetime = datetime.strptime(appointment_datetime_str, "%Y-%m-%d %H:%M")
                    current_datetime = datetime.now()

                    # Ensure the appointment is not in the past
                    if appointment_datetime < current_datetime:
                        return "You cannot schedule an appointment in the past. Please select a future date and time."

                    # Ensure at least 3 hours gap from current time
                    if appointment_datetime < current_datetime + timedelta(hours=3):
                        return "Please schedule the appointment at least 3 hours from now."

                except Exception as e:
                    print(f"Error validating appointment time: {e}")
                    return "Invalid date or time format. Please try again."

                # Check if time slot is available
                if self.is_time_slot_available(self.user_info["date"], formatted_time):
                    if formatted_time in self.get_available_times():
                        self.user_info["time"] = formatted_time
                        self.user_info["created_at"] = datetime.now()
                        self.user_info["status"] = "confirmed"
                        self.current_field = None

                        # Save to database
                        session_id = self._get_current_session_id()
                        if not session_id:
                            print("Warning: session_id is None when trying to save appointment!")
                            return "Sorry, session information is missing. Please try again."

                        try:
                            db.save_user_data(self.user_info, session_id)
                        except Exception as e:
                            return "Error saving your appointment. Please try again."

                        return (f"Thanks, {self.user_info['name']}! Your appointment is confirmed for:\n"
                                f"- Date: {self.user_info['date']}\n"
                                f"- Time: {formatted_time}\n"
                                f"Contact:\n"
                                f"- Email: {self.user_info['email']}\n"
                                f"- Phone: {self.user_info['phone'] or 'Not provided'}")
                    else:
                        return f"{formatted_time} is not available. Choose from: {', '.join(self.get_available_times())}"
                else:
                    return f"Sorry, {formatted_time} on {self.user_info['date']} is already booked. Please choose another time."
            else:
                return "Invalid time format. Try formats like '10 AM' or '14:30'."
        
    def start_collection(self):
        self.current_field = "name"
        return "Let's begin! What's your full name?"

    def is_collecting(self):
        return self.current_field is not None

    def get_user_info(self):
        return self.user_info
    
    def check_existing_booking(self):
        """Check if user has any confirmed booking"""
        if not self.user_info.get('email'):
            return False
            
        existing = db.get_confirmed_appointment(
            self.user_info['email'],
            self.user_info.get('phone', '')
        )
        
        if existing:
            self.user_info.update({
                'date': existing.get('date'),
                'time': existing.get('time'),
                'status': 'confirmed'
            })
            return True
        return False

    def cancel_booking(self):
        """Cancel a booking based on user_info data"""
        try:
            if not self.user_info.get('email'):
                return False, "No active booking found in current session."
                
            # First check if we have complete info in session
            if all([self.user_info.get('email'), self.user_info.get('date'), self.user_info.get('time')]):
                if db.cancel_booking(
                    email=self.user_info['email'],
                    date=self.user_info['date'],
                    time=self.user_info['time']
                ):
                    self.clear_info()
                    return True, "Your appointment has been cancelled successfully."
                    
            # If not found, try to cancel any booking for this email
            if db.cancel_any_booking(email=self.user_info['email']):
                self.clear_info()
                return True, "Your appointment has been cancelled successfully."
                
            return False, "I couldn't find your appointment in our records."
        except Exception as e:
            print(f"Error canceling booking: {e}")
            return False, "An error occurred while cancelling your appointment."

    def save_to_database(self):
        try:
            if not all([self.user_info.get("name"), self.user_info.get("phone"), self.user_info.get("email")]):
                print("Save failed: Missing required user fields.")
                return False

            with sqlite3.connect("user_info.db") as conn:
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS user_data (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL,
                        phone TEXT NOT NULL,
                        email TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        status TEXT
                    )
                ''')
                conn.execute('''
                    INSERT INTO user_data (name, phone, email, created_at)
                    VALUES (?, ?, ?, ?)
                ''', (
                    self.user_info["name"],
                    self.user_info["phone"],
                    self.user_info["email"],
                    self.user_info.get("created_at", datetime.now().isoformat())
                ))
            return True
        except Exception as e:
            print(f"Error saving user to DB: {e}")
            return False

