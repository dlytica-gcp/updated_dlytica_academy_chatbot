from datetime import datetime, timedelta
import re
import calendar
from langchain.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Dict, Any, Type, Optional

class DateExtractionInput(BaseModel):
    query: str = Field(..., description="The text to extract dates from")

class DateExtractionTool(BaseTool):
    name: str = "date_extractor"
    description: str = """Extracts dates from user query. Handles:
    - Specific dates ('March 15th', '2025-04-20')
    - Relative dates ('next Monday', 'tomorrow')
    - Time references ('2 PM', 'morning slot')"""
    args_schema: Type[BaseModel] = DateExtractionInput
    
    # Declare these as class attributes with type hints
    day_indices: Dict[str, int] = {
        "monday": 0, "mon": 0,
        "tuesday": 1, "tue": 1, "tues": 1,
        "wednesday": 2, "wed": 2,
        "thursday": 3, "thu": 3, "thurs": 3,
        "friday": 4, "fri": 4,
        "saturday": 5, "sat": 5,
        "sunday": 6, "sun": 6
    }
    
    month_names: Dict[str, int] = {
        "january": 1, "jan": 1,
        "february": 2, "feb": 2,
        "march": 3, "mar": 3,
        "april": 4, "apr": 4,
        "may": 5,
        "june": 6, "jun": 6,
        "july": 7, "jul": 7,
        "august": 8, "aug": 8,
        "september": 9, "sep": 9, "sept": 9,
        "october": 10, "oct": 10,
        "november": 11, "nov": 11,
        "december": 12, "dec": 12
    }

    def _run(self, query: str, run_manager=None) -> str:
        """Main execution method for the tool"""
        return self.extract_date(query)
    
    def _next_day_of_week(self, day_index):
        """
        Calculate the date of the next occurrence of a day of the week
        
        Args:
            day_index (int): Index of the day (0 = Monday, 6 = Sunday)
            
        Returns:
            datetime: Date of the next occurrence
        """
        today = datetime.now()
        days_ahead = day_index - today.weekday()
        if days_ahead <= 0:  # Target day already happened this week
            days_ahead += 7
        return today + timedelta(days=days_ahead)
        
    def extract_date(self, query):
        query = query.lower()

        def is_closed_day(date_obj):
            return date_obj.weekday() in (5, 6)  # 5 = Saturday, 6 = Sunday
            # return date_obj.weekday() in (5)  # 5 = Saturday, 6 = Sunday

        def return_if_valid(date_obj):
            if is_closed_day(date_obj):
                return "WEEKEND"  # Special marker to signal weekend
            return date_obj.date().isoformat()

        # Check for exact YYYY-MM-DD
        date_pattern = r"\b(\d{4}-\d{2}-\d{2})\b"
        date_match = re.search(date_pattern, query)
        if date_match:
            try:
                return return_if_valid(datetime.strptime(date_match.group(1), "%Y-%m-%d"))
            except ValueError:
                pass

        # Check common formats
        for pattern, fmt in [
            (r"\b(\d{1,2}/\d{1,2}/\d{4})\b", "%m/%d/%Y"),
            (r"\b(\d{1,2}-\d{1,2}-\d{4})\b", "%m-%d-%Y"),
            (r"\b(\d{1,2}\.\d{1,2}\.\d{4})\b", "%m.%d.%Y")
        ]:
            date_match = re.search(pattern, query)
            if date_match:
                try:
                    return return_if_valid(datetime.strptime(date_match.group(1), fmt))
                except ValueError:
                    continue

        if "today" in query:
            return return_if_valid(datetime.now())
        elif "tomorrow" or "tomoroww" or "toomorrow" in query:
            return return_if_valid(datetime.now() + timedelta(days=1))
        elif "day after tomorrow" in query:
            return return_if_valid(datetime.now() + timedelta(days=2))

        # next/this/only day of week
        for day_name, day_index in self.day_indices.items():
            if f"next {day_name}" in query or f"this {day_name}" in query or re.search(rf"\b{day_name}\b", query):
                date_obj = self._next_day_of_week(day_index)
                return return_if_valid(date_obj)

        # Check "January 15"
        month_day_pattern = r"(?:(?:on|for)\s+)?([a-z]+)\s+(\d{1,2})(?:st|nd|rd|th)?"
        match = re.search(month_day_pattern, query)
        if match:
            month_name = match.group(1).lower()
            day = int(match.group(2))
            if month_name in self.month_names:
                try:
                    year = datetime.now().year
                    date_obj = datetime(year, self.month_names[month_name], day)
                    if date_obj.date() < datetime.now().date():
                        date_obj = datetime(year + 1, self.month_names[month_name], day)
                    return return_if_valid(date_obj)
                except ValueError:
                    pass

        # "in X days/weeks/months"
        match = re.search(r"in\s+(\d+)\s+(day|days|week|weeks|month|months)", query)
        if match:
            amount = int(match.group(1))
            unit = match.group(2)
            if unit.startswith("day"):
                return return_if_valid(datetime.now() + timedelta(days=amount))
            elif unit.startswith("week"):
                return return_if_valid(datetime.now() + timedelta(weeks=amount))
            elif unit.startswith("month"):
                return return_if_valid(datetime.now() + timedelta(days=30 * amount))

        return None