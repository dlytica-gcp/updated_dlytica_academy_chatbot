# 🤖 Dlytica Academy Chatbot

An AI-powered assistant built using **FastAPI**, **LangChain**, **LLMs**, and **PostgreSQL**, designed to answer user queries intelligently, manage user sessions, and assist with appointment bookings. It features a modern floating chat interface with voice input and is fully Dockerized and production-ready.

---

## 🧰 Features

- ✅ FastAPI backend with modular architecture
- ✅ Retrieval-Augmented Generation (RAG) using ChromaDB
- ✅ LangChain agents and tools for user info and booking
- ✅ PostgreSQL for session and metadata storage
- ✅ Voice input support (SpeechRecognition API)
- ✅ Secure, responsive frontend (HTML, CSS, JS)
- ✅ Containerized via Docker and deployed to Kubernetes

---

## 🗂️ Project Structure

dlytica-chatbot/
├── app.py # FastAPI main entrypoint
├── chatbot/
│ ├── agent.py # LangChain agents & tools
│ ├── database.py # PostgreSQL DB connection
│ ├── document_loader.py # Document loader and parser
│ ├── rag_system.py # RAG + ChromaDB logic
│ ├── user_info.py # User info collection system
│ └── tools/
│ ├── booking_tool.py # Appointment booking logic
│ └── date_tool.py # Natural language date parser
├── static/
│ ├── chat.html # Frontend interface
│ ├── style.css # Styling for the chatbot
│ └── script.js # Frontend behavior
├── requirements.txt # Python dependencies
├── Dockerfile # Containerization script
├── README.md # Project documentation
└── .env.example # Sample environment variables


---

## 🚀 Getting Started

### 1. Clone the Repository

```bash
git clone https://github.com/<your-org>/dlytica-chatbot.git
cd dlytica-chatbot

### 2. Creating a virutal environment

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate


### 3. Install Dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt

