# 🤖 Dlytica Academy Chatbot

An AI-powered assistant built using **FastAPI**, **LangChain**, **LLMs**, and **PostgreSQL**, designed to answer user queries intelligently, manage user sessions, and assist with appointment bookings. It features a modern floating chat interface with voice input and is fully Dockerized and production-ready.

---

## 🧰 Features

-  FastAPI backend with modular architecture
-  Retrieval-Augmented Generation (RAG) using ChromaDB
-  LangChain agents and tools for user info and booking
-  PostgreSQL for session and metadata storage
-  Voice input support (SpeechRecognition API)
-  Secure, responsive frontend (HTML, CSS, JS)
-  Containerized via Docker and deployed to Kubernetes

---

## 🗂️ Project Structure

```bash
dlytica-chatbot/
├── app.py                   # FastAPI main entrypoint
├── chatbot/
│   ├── agent.py             # LangChain agents & tools
│   ├── database.py          # PostgreSQL DB connection
│   ├── document_loader.py   # Document loader and parser
│   ├── rag_system.py        # RAG + ChromaDB logic
│   ├── user_info.py         # User info collection system
│   └── tools/
│       ├── booking_tool.py  # Appointment booking logic
│       └── date_tool.py     # Natural language date parser
├── static/
│   ├── chat.html            # Frontend interface
│   ├── style.css            # Styling for the chatbot
│   └── script.js            # Frontend behavior
├── requirements.txt         # Python dependencies
├── Dockerfile               # Containerization script
├── README.md                # Project documentation
└── .env                     # Sample environment variables
```

---

## 🚀 Getting Started

### 1. Clone the Repository

```bash
git clone https://github.com/dlytica-gcp/updated_dlytica_academy_chatbot.git
cd dlytica-chatbot
```

### 2. Creating a virutal environment

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

```
### 3. Install Dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

###  Environment Variables

```bash
Create a .env file (or use Kubernetes secrets in production). 

OPENAI_BASE_URL=https://your-openai-base-url/
OPENAI_API_KEY=your-openai-key
DB_ENGINE=django.db.backends.postgresql
DB_NAME=chatbot_db
DB_USER=academy-chatbot-postgres
DB_PASSWORD=postgres_bot
DB_HOST=postgres-service.dn-academy-chatbot.svc.cluster.local 
DB_HOST=dlytica-kube-vm.eastus.cloudapp.azure.com
DB_PORT=30148
```

### Running the Application Locally

```bash
uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

###  Docker Build & Push

```bash
docker build -t quay.io/datanature_dev/jupyternotebook:dlytica-chatbot-v50 .
docker push quay.io/datanature_dev/jupyternotebook:dlytica-chatbot-v50
```
