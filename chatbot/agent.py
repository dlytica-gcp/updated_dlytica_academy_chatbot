from langchain.agents import Tool, initialize_agent
from langchain.agents import AgentType
from langchain.tools import BaseTool
from typing import Optional, Dict, Any, List, Union, Type
from pydantic import BaseModel, Field
import re
from datetime import datetime

# Define input schemas for each tool
class DateExtractionInput(BaseModel):
    query: str = Field(..., description="The text to extract dates from")

class BookingInput(BaseModel):
    action: str = Field(..., description="'book' or 'cancel'")
    date: str = Field(..., description="Appointment date")
    time: str = Field(..., description="Appointment time")
    user_info: Dict[str, str] = Field(..., description="User details")

class UserInfoInput(BaseModel):
    name: Optional[str] = Field(None, description="User's name")
    email: Optional[str] = Field(None, description="User's email")
    phone: Optional[str] = Field(None, description="User's phone number")

class DateExtractionTool(BaseTool):
    name: str = "DateExtraction"  # Explicit type annotation
    description: str = """Extracts date from user query. Handles:
    - Specific dates ('March 15th', '2025-04-20')
    - Relative dates ('next Monday', 'tomorrow')
    - Time references ('2 PM', 'morning slot')"""
    args_schema: Type[BaseModel] = DateExtractionInput  # Add args schema
    
    def _run(self, query: str, run_manager=None) -> str:
        """Main execution method"""
        return self.extract_date(query)
    
    def extract_date(self, query: str) -> str:
        """Extract date from user input"""
        date_patterns = [
            (r'\b(today|now)\b', 'today'),
            (r'\b(tomorrow)\b', 'tomorrow'),
            (r'\b(next week|in 7 days)\b', 'next week'),
            # Add more patterns as needed
        ]
        
        for pattern, replacement in date_patterns:
            if re.search(pattern, query, re.IGNORECASE):
                return replacement
        
        return "unknown date"

class AppointmentBookingTool(BaseTool):
    name: str = "AppointmentBooking"  # Explicit type annotation
    description: str = """Books or cancels appointments. 
    Input should be a dictionary with:
    - 'action': 'book' or 'cancel'
    - 'date': appointment date
    - 'time': appointment time
    - 'user_info': user details"""
    args_schema: Type[BaseModel] = BookingInput  # Add args schema
    
    def _run(self, booking_info: Dict[str, Any], run_manager=None) -> str:
        if booking_info.get('action') == 'book':
            return self.book_appointment(booking_info)
        return self.cancel_appointment(booking_info)
    
    def book_appointment(self, booking_info: Dict[str, Any]) -> str:
        """Book an appointment"""
        return f"Appointment booked for {booking_info.get('date')} at {booking_info.get('time')}"
    
    def cancel_appointment(self, booking_info: Dict[str, Any]) -> str:
        """Cancel an appointment"""
        return f"Appointment cancelled for {booking_info.get('date')}"

class UserInfoTool(BaseTool):
    name: str = "UserInfoCollection"
    description: str = """Collects user information including:
    - name
    - email
    - phone number
    Returns a dictionary with collected info"""
    args_schema: Type[BaseModel] = UserInfoInput
    
    def _run(self, info_request: Dict[str, Any], run_manager=None) -> Dict[str, str]:
        return self.collect_info(info_request)
    
    def collect_info(self, info_request: Dict[str, Any]) -> Dict[str, str]:
        """Collect user information"""
        return {
            "name": info_request.get("name", "unknown"),
            "email": info_request.get("email", "unknown"),
            "phone": info_request.get("phone", "unknown")
        }


def setup_agent(llm: Any, 
               user_info_collector: Any,  # Change type hint since it's your main class now
               date_tool: DateExtractionTool, 
               booking_tool: AppointmentBookingTool) -> Any:
    """Set up an agent with tools for various tasks"""
    tools = [
        Tool(
            name=date_tool.name,
            func=date_tool._run,
            description=date_tool.description
        ),
        Tool(
            name=booking_tool.name,
            func=booking_tool._run,
            description=booking_tool.description
        ),
        # Remove the UserInfoCollector tool since we're using the main class directly
    ]
    
    return initialize_agent(
        tools=tools,
        llm=llm,
        agent=AgentType.STRUCTURED_CHAT_ZERO_SHOT_REACT_DESCRIPTION,
        verbose=True,
        handle_parsing_errors=True,
        max_iterations=5,
        early_stopping_method="generate"
    )