from fastapi import FastAPI, HTTPException, Request, Cookie, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from langchain_openai import ChatOpenAI 
from langchain.memory import ConversationBufferMemory
from langchain_community.embeddings import HuggingFaceEmbeddings
from chatbot.document_loader import load_documents
from chatbot.rag_system import create_vector_store, setup_rag_chain
from chatbot.user_info import UserInfoCollector
from chatbot.tools.date_tool import DateExtractionTool
from chatbot.tools.booking_tool import AppointmentBookingTool
from chatbot.agent import setup_agent
import os
from dotenv import load_dotenv
from uuid import uuid4
from datetime import datetime
from fastapi.middleware.cors import CORSMiddleware
from chatbot.database import db
from tenacity import retry, stop_after_attempt, wait_exponential
import asyncio
import re
from tenacity import retry, stop_after_attempt, wait_exponential

# Load environment variables
load_dotenv()

# Initialize FastAPI
app = FastAPI(title="AI Chatbot API", version="1.0.0")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)

# Mount static directory
app.mount("/static", StaticFiles(directory="static"), name="static")

# Document path
document_path = "./docs/Frequently Asked Questions.pdf"

# Models
class UserInput(BaseModel):
    message: str
    session_id: str = None

class HealthCheckResponse(BaseModel):
    status: str
    details: dict = None
    errors: list = None

class DocumentChatbot:
    def __init__(self, document_path):
        self.llm = self._initialize_llm()
        self.embeddings = self._initialize_embeddings()
        self.documents = load_documents(document_path)
        self.vector_store = create_vector_store(self.documents)
        self.qa_chain = setup_rag_chain(self.vector_store, self.llm)
        self.sessions = {}
        self.date_tool = DateExtractionTool()
    
    def _initialize_llm(self):
        return ChatOpenAI(
            model="gpt-3.5-turbo",
            temperature=0.7,
            openai_api_key=os.getenv("OPENAI_API_KEY"),
            max_tokens=512,
            streaming=False,
            request_timeout=30
        )
    
    def _initialize_embeddings(self):
        return HuggingFaceEmbeddings(
            model_name="sentence-transformers/all-MiniLM-L6-v2",
            model_kwargs={'device': 'cpu'}
        )
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    def verify_llm_connection(self):
        try:
            test_prompt = "Hello, world!"
            response = self.llm.invoke(test_prompt)
            return True
        except Exception as e:
            print(f"LLM connection failed: {str(e)}")
            return False
        
    def get_or_create_session(self, session_id, request: Request = None):
        now = datetime.now()
        
        if session_id not in self.sessions or self.is_session_expired(session_id):
            if session_id in self.sessions:
                self._log_session_end(session_id)
            
            if request and request.headers.get('Referer'):
                session_id = str(uuid4())
            
            # Create new collector
            collector = UserInfoCollector(self.llm, session_id=session_id)

            
            # Attempt to prefill user_info from DB if email/phone are in request (optional: get from cookies or headers if available)
            # For now, this assumes user just started so user_info is empty
            
            self.sessions[session_id] = {
                'collector': collector,
                'booking_tool': None,
                'tools': None,
                'memory': ConversationBufferMemory(return_messages=True),
                'created_at': now,
                'last_activity': now,
                'user_agent': request.headers.get('User-Agent') if request else None,
                'ip_address': request.client.host if request else None
            }
            self._initialize_session_components(session_id)
            self._log_session_start(session_id, request)
        
        session = self.sessions[session_id]
        
        # **Load confirmed appointment if user info has email+phone but date/time is not yet set**
        collector = session['collector']
        if (collector.user_info.get('email') and collector.user_info.get('phone') and
            not collector.user_info.get('date') and not collector.user_info.get('time')):
            
            appointment = db.get_confirmed_appointment(
                collector.user_info['email'], 
                collector.user_info['phone']
            )
            if appointment:
                collector.user_info['date'] = appointment.get('date')
                collector.user_info['time'] = appointment.get('time')
                collector.user_info['status'] = 'confirmed'
        
        session['last_activity'] = now
        return session


    
    def _initialize_session_components(self, session_id):
        self.sessions[session_id]['booking_tool'] = AppointmentBookingTool(
            self.sessions[session_id]['collector'], 
            self.date_tool
        )
        self.sessions[session_id]['tools'] = setup_agent(
            self.llm,
            self.sessions[session_id]['collector'],
            self.date_tool,
            self.sessions[session_id]['booking_tool']
        )

    def _log_session_start(self, session_id, request):
        try:
            db.log_session_start(
                session_id=session_id,
                user_agent=request.headers.get('User-Agent') if request else None,
                ip_address=request.client.host if request else None
            )
        except Exception as e:
            print(f"Error logging session start: {e}")

    def _log_session_end(self, session_id):
        try:
            db.log_session_end(session_id)
        except Exception as e:
            print(f"Error logging session end: {e}")

    def is_session_expired(self, session_id, max_inactive_seconds=1800):
        if session_id not in self.sessions:
            return True
            
        last_activity = self.sessions[session_id]['last_activity']
        return (datetime.now() - last_activity).total_seconds() > max_inactive_seconds

    def clean_old_sessions(self, max_age_seconds=3600):
        now = datetime.now()
        for sid in list(self.sessions.keys()):
            session = self.sessions[sid]
            inactive_time = (now - session['last_activity']).total_seconds()
            
            if inactive_time > max_age_seconds:
                self._log_session_end(sid)
                del self.sessions[sid]
                
    def summarize_response(self, response: str) -> str:
        """
        Summarize the response to provide only the most relevant information.
        """
        # Using GPT to summarize if the response is too long
        if len(response) > 300:
            prompt = f"Summarize the following text in a few sentences:\n\n{response}"
            summary = self.llm.invoke(prompt)  # Use the same LLM to get a concise summary
            return summary
        return response
    
    def format_urls_in_response(self, response: str) -> str:
        """
        Converts any URLs in the response into clickable links.
        """
        url_pattern = re.compile(r'(https?://\S+)')
        return re.sub(url_pattern, r'<a href="\1" target="_blank">\1</a>', response)

        

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    def process_message(self, user_message, session_id):
        try:
            session = self.get_or_create_session(session_id)
            collector = session['collector']
            self.clean_old_sessions()

            user_message_lower = user_message.lower()

            # Reset session triggers
            if any(kw in user_message_lower for kw in ["reset", "start over", "begin again", "new session"]):
                response = self.reset_session(session_id)
                self._safe_log_conversation(session_id, user_message, response)
                return response

            # Cancel booking triggers
            if any(kw in user_message_lower for kw in ["cancel", "cancel appointment", "cancel booking", "cancel schedule"]):
                success, message = self.cancel_booking_in_progress(session_id)
                self._safe_log_conversation(session_id, user_message, message)
                return message

            # If user is currently providing booking info (stepwise collection)
            if collector.is_collecting():
                response = collector.process_input(user_message)
                # Save user info after booking info collection is complete
                if not collector.is_collecting() and collector.has_booking():
                    self._safe_save_user_data(collector.user_info, session_id)
                self._safe_log_conversation(session_id, user_message, response)
                return response

            # Block new bookings if user already has one in session
            if (collector.has_booking() and
                any(kw in user_message_lower for kw in ["book", "schedule", "appointment", "meeting"])):
                response = (
                    f"You already have a confirmed appointment for {collector.user_info['date']} at {collector.user_info['time']}. "
                    "If you'd like to book a new appointment, please cancel the previous booking first."
                )
                self._safe_log_conversation(session_id, user_message, response)
                return response

            # Booking initiation triggers
            if any(kw in user_message_lower for kw in ["book", "schedule", "appointment", "meeting"]):
                date_str = self.date_tool.extract_date(user_message)
                time_str = None  # You can implement time extraction similarly if needed
                booking_info = {
                    "query": user_message,
                    "date": date_str,
                    "time": time_str,
                    "user_info": collector.get_user_info()
                }
                try:
                    response = session['booking_tool'].book_appointment(booking_info)
                except Exception as e:
                    response = f"Error during appointment booking: {str(e)}"
                self._safe_log_conversation(session_id, user_message, response)
                return response

            # Fallback: Normal RAG query
            try:
                response = self.qa_chain({"query": user_message})
                final_response = response["result"]
            except Exception as e:
                final_response = f"I'm sorry, I encountered an error while answering: {str(e)}"

            self._safe_log_conversation(session_id, user_message, final_response)
            return final_response
        
            print(f"Collector is_collecting: {collector.is_collecting()}, current_field: {collector.current_field}")

        except Exception as e:
            print(f"Critical error in process_message: {str(e)}")
            raise


    
    def _safe_log_conversation(self, session_id, user_message, bot_response):
        try:
            db.log_conversation(session_id, user_message, bot_response)
        except Exception as e:
            print(f"Non-critical error logging conversation: {e}")

    def _safe_save_user_data(self, user_info, session_id):
        try:
            db.save_user_data(user_info, session_id)
        except Exception as e:
            print(f"Non-critical error saving user data: {e}")

    def reset_session(self, session_id):
        if session_id in self.sessions:
            collector = self.sessions[session_id]['collector']
            if all([collector.user_info.get('email'), 
                    collector.user_info.get('date'), 
                    collector.user_info.get('time')]):
                collector.cancel_booking()
            
            self._reset_session_components(session_id)
            
        return "Your session has been reset. How can I help you today?"

    def _reset_session_components(self, session_id):
        if session_id in self.sessions:
            self.sessions[session_id]['collector'] = UserInfoCollector(self.llm)
            self.sessions[session_id]['memory'] = ConversationBufferMemory(return_messages=True)
            self._initialize_session_components(session_id)

    def cancel_booking_in_progress(self, session_id):
        if session_id not in self.sessions:
            return False, "No active session found."

        session = self.sessions[session_id]
        collector = session['collector']

        if collector.is_collecting():
            collector.clear_info()
            self._reset_session_components(session_id)
            return True, "Your booking process has been cancelled. How can I help you today?"

        user_info = collector.user_info
        if user_info.get("email") and user_info.get("date") and user_info.get("time"):
            if collector.cancel_booking():
                collector.clear_info()
                self._reset_session_components(session_id)
                return True, "Your appointment has been cancelled. How can I help you today?"
            else:
                return False, "I couldn't find your appointment in our records."

        self._reset_session_components(session_id)
        return False, "Your session has been reset. How can I help you today?"

# Initialize chatbot
chatbot = DocumentChatbot(document_path)
if not chatbot.verify_llm_connection():
    raise RuntimeError("Failed to initialize LLM connection")

# Background tasks
async def cleanup_sessions_periodically():
    while True:
        try:
            chatbot.clean_old_sessions()
            await asyncio.sleep(1800)  # Run every 30 minutes
        except Exception as e:
            print(f"Error in cleanup task: {e}")

@app.on_event("startup")
async def startup_event():
    
    db._ensure_tables_exist()

    asyncio.create_task(cleanup_sessions_periodically())

# API Endpoints
@app.post("/get_response", response_model=dict)
@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
async def get_response(input_data: UserInput, request: Request, session_id: str = Cookie(default=None)):
    try:
        if not session_id or chatbot.is_session_expired(session_id):
            session_id = str(uuid4())
        
        session = chatbot.get_or_create_session(session_id, request)
        response = chatbot.process_message(input_data.message, session_id)
        
        json_response = JSONResponse(content={"response": response})
        json_response.set_cookie(
            key="session_id", 
            value=session_id,
            httponly=True,
            max_age=1800,
            secure=True,
            samesite='Lax'
        )
        return json_response
    except Exception as e:
        print(f"Error in get_response: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error. Please try again.")

@app.post("/reset_session", response_model=dict)
async def reset_session(request: Request, session_id: str = Cookie(default=None)):
    try:
        new_session_id = str(uuid4())
        if session_id:
            chatbot._log_session_end(session_id)
        
        response_text = "Your session has been reset. How can I help you today?"
        response = JSONResponse(content={"response": response_text})
        response.set_cookie(
            key="session_id", 
            value=new_session_id,
            httponly=True,
            max_age=1800,
            secure=True,
            samesite='Lax'
        )
        return response
    except Exception as e:
        print(f"Error in reset_session: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error. Please try again.")

@app.get("/", response_class=HTMLResponse)
async def get_chat_ui():
    try:
        with open("static/home.html", "r", encoding="utf-8") as file:
            return file.read()
    except Exception as e:
        raise HTTPException(status_code=500, detail="Could not load chat interface")
    
@app.post("/check_session", response_model=dict)
async def check_session(session_id: str = Cookie(default=None)):
    try:
        if not session_id or session_id not in chatbot.sessions:
            return JSONResponse(content={
                "active": False,
                "collecting": False
            })
        
        session = chatbot.sessions[session_id]
        return JSONResponse(content={
            "active": True,
            "collecting": session['collector'].is_collecting() if session['collector'] else False
        })
    except Exception as e:
        print(f"Error in check_session: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")
    
@app.get("/get_conversation_history", response_model=dict)
async def get_conversation_history(session_id: str = Cookie(default=None)):
    try:
        if not session_id:
            raise HTTPException(status_code=400, detail="Session ID required")
        
        history = db.get_user_history(session_id)
        return JSONResponse(content={"history": [
            {"user": item['user_message'], "bot": item['bot_response'], "time": item['created_at'].isoformat()}
            for item in history
        ]})
    except Exception as e:
        print(f"Error getting conversation history: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")
    
@app.get("/session_info", response_model=dict)
async def get_session_info(session_id: str = Cookie(default=None)):
    try:
        if not session_id:
            raise HTTPException(status_code=400, detail="No active session")
        
        with db.get_cursor() as cursor:
            cursor.execute("""
                SELECT created_at, last_activity, expired_at 
                FROM session_metadata 
                WHERE session_id = %s
            """, (session_id,))
            session_data = cursor.fetchone()
            
            if not session_data:
                raise HTTPException(status_code=404, detail="Session not found")
                
            return {
                "created_at": session_data[0].isoformat(),
                "last_activity": session_data[1].isoformat(),
                "expired_at": session_data[2].isoformat() if session_data[2] else None,
                "active": session_data[2] is None
            }
    except Exception as e:
        print(f"Error getting session info: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/health", response_model=HealthCheckResponse)
async def health_check():
    errors = []
    
    # Check database connection
    try:
        with db.get_cursor() as cursor:
            cursor.execute("SELECT 1")
    except Exception as e:
        errors.append(f"Database connection failed: {str(e)}")
    
    # Check LLM connection
    llm_ok = False
    try:
        llm_ok = chatbot.verify_llm_connection()
    except Exception as e:
        errors.append(f"LLM connection failed: {str(e)}")
    
    if not llm_ok:
        errors.append("LLM not available")
    
    status = "healthy" if not errors else "unhealthy"
    
    return {
        "status": status,
        "details": {
            "database": "ok" if "database" not in " ".join(errors) else "error",
            "llm": "ok" if llm_ok else "error"
        },
        "errors": errors if errors else None
    }
