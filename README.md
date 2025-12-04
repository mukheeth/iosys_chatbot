# RAG Chatbot with ChromaDB and Groq LLM

A Retrieval-Augmented Generation (RAG) chatbot that allows you to chat with your PDF documents using Groq's fast LLM API, embeddings, and ChromaDB vector database. Features contact forms and meeting scheduling capabilities.

## Project Structure

```
chatbots/
├── backend/
│   ├── app.py                 # Flask API server
│   ├── rag_system.py          # RAG implementation with ChromaDB
│   ├── requirements.txt       # Python dependencies
│   ├── .env                   # Environment variables (create this)
│   ├── chroma/                # ChromaDB vector database (auto-created)
│   └── documents/             # Place your PDF/text files here
│       ├── document1.pdf      # Your PDF documents
│       ├── document2.pdf      # Your PDF documents
│       └── iosys_services.txt # Your text documents
├── frontend/
│   ├── src/
│   │   ├── App.js            # Main React component
│   │   ├── index.js          # React entry point
│   │   └── index.css         # Tailwind CSS styles
│   ├── public/
│   │   └── index.html        # HTML template
│   ├── package.json          # Node.js dependencies
│   ├── tailwind.config.js    # Tailwind configuration
│   └── postcss.config.js     # PostCSS configuration
├── start_servers.bat         # Quick start script (Windows)
└── README.md                 # This file
```

## Features

- 📄 **PDF Document Processing**: Automatically extracts and chunks text from PDF files
- 🔍 **Semantic Search**: Uses sentence-transformers for creating embeddings
- 🗄️ **Vector Database**: ChromaDB for efficient similarity search
- 🤖 **Fast LLM Integration**: Uses Groq API for rapid response generation
- 💬 **Modern Chat UI**: Beautiful React frontend with Tailwind CSS
- 🔗 **Source Attribution**: Shows which documents were used to generate answers
- 📧 **Contact Forms**: Integrated contact request functionality
- 📅 **Meeting Scheduling**: Schedule meetings directly through the chatbot
- 🎯 **Smart Intent Recognition**: Automatically detects user intent (greetings, queries, contact requests, etc.)

## Prerequisites

1. **Python 3.8+** installed
2. **Node.js 16+** and npm installed
3. **Groq API Key** - Get your free API key from [https://console.groq.com/keys](https://console.groq.com/keys)

## Quick Start

For Windows users, you can use the provided batch script:

```bash
start_servers.bat
```

This will start both backend and frontend servers automatically.

## Setup Instructions

### 1. Backend Setup

1. Navigate to the backend directory:
   ```bash
   cd backend
   ```

2. Create a virtual environment:
   ```bash
   python -m venv venv
   ```

3. Activate the virtual environment:
   - Windows: `venv\Scripts\activate`
   - macOS/Linux: `source venv/bin/activate`

4. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

5. **Configure Environment Variables**:
   - Create a `.env` file in the `backend/` directory
   - Add the following configuration:
     ```env
     # Groq API Configuration
     GROQ_API_KEY=your_groq_api_key_here
     
     # Email Configuration (for contact & meeting forms)
     SENDER_EMAIL=your-email@example.com
     SENDER_PASSWORD=your-app-password
     COMPANY_EMAIL=recipient@example.com
     EMAIL_PROVIDER=gmail
     SMTP_SERVER=smtp.gmail.com
     SMTP_PORT=587
     ```

6. **Add your PDF documents**:
   - Place your PDF files in the `backend/documents/` folder
   - The system will automatically process them on first run
   - Supported formats: `.pdf` and `.txt`

7. Start the Flask server:
   ```bash
   python app.py
   ```

The backend will be available at `http://localhost:5000`

### Email Configuration Details

**Provider-aware defaults:**
- `gmail` / `google` → `smtp.gmail.com:587`
- `microsoft` / `outlook` → `smtp.office365.com:587`
- Custom servers → set `SMTP_SERVER` and `SMTP_PORT` manually

**Important Notes:**
- For Gmail: Use an [App Password](https://support.google.com/accounts/answer/185833) instead of your regular password
  1. Enable 2-factor authentication on your Google account
  2. Go to App Passwords in your Google account settings
  3. Generate a new app password for "Mail"
  4. Use this 16-character password in your `.env` file
- For Microsoft/Office 365: Use an app password or enable "Less secure app access"
- The `EMAIL_PROVIDER` setting automatically configures the correct SMTP server
- Ensure `SENDER_EMAIL` matches the account that generated the app password

### 2. Frontend Setup

1. Open a new terminal and navigate to the frontend directory:
   ```bash
   cd frontend
   ```

2. Install dependencies:
   ```bash
   npm install
   ```

3. Start the React development server:
   ```bash
   npm start
   ```

The frontend will be available at `http://localhost:3000`

## Usage

1. **Start both servers** (backend and frontend)
   - Backend: `cd backend && python app.py`
   - Frontend: `cd frontend && npm start`
   - Or use `start_servers.bat` on Windows
2. **Open your browser** and go to `http://localhost:3000`
3. **Documents are auto-initialized** on first run
4. **Start chatting** with your documents!
5. **Use contact forms** to submit inquiries or schedule meetings

### Updating Documents

If you add, remove, or modify documents in the `backend/documents/` folder:

1. **Stop the Flask server** (Ctrl+C)
2. **Delete the ChromaDB folder**:
   ```bash
   # PowerShell (Windows)
   Remove-Item -Recurse -Force backend/chroma
   
   # Bash (macOS/Linux)
   rm -rf backend/chroma
   ```
3. **Restart the Flask server** - it will automatically reinitialize with updated documents

Alternatively, you can call the API endpoint:
```bash
curl -X POST http://localhost:5000/api/initialize
```

## How It Works

1. **Document Processing**: PDF and text files are processed and split into chunks using LangChain
2. **Embedding Generation**: Each chunk is converted to embeddings using HuggingFace sentence-transformers
3. **Vector Storage**: Embeddings are stored in ChromaDB for fast similarity search
4. **Query Processing**: User questions are classified (greeting, query, contact request, etc.)
5. **Semantic Search**: Query embeddings are matched against stored document chunks
6. **Response Generation**: Relevant chunks are sent to Groq LLM (Llama 3.1 8B) for answer generation
7. **Email Integration**: Contact and meeting requests are sent via SMTP

## Customization

### Changing the LLM Model

Edit `backend/rag_system.py` and modify the model in the `__init__` method:

```python
self.llm = ChatGroq(
    api_key=groq_api_key,
    model="llama-3.1-8b-instant",  # Change to your preferred Groq model
    temperature=0.0,
    max_tokens=2048
)
```

Available Groq models: `llama-3.1-8b-instant`, `llama-3.1-70b-versatile`, `mixtral-8x7b-32768`, etc.

### Adjusting Chunk Size

Modify the `RecursiveCharacterTextSplitter` parameters in `rag_system.py`:

```python
self.text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=1000,  # Adjust chunk size
    chunk_overlap=200,  # Adjust overlap
    length_function=len,
)
```

### Changing Embedding Model

Update the embedding model in `rag_system.py`:

```python
self.embeddings = HuggingFaceEmbeddings(
    model_name="sentence-transformers/all-MiniLM-L6-v2",  # Change model here
    model_kwargs={'device': 'cpu'}
)
```

### Customizing Response Formatting

The prompt templates in `rag_system.py` control how responses are formatted. Look for the `_setup_qa_chain()` method and modify the `prompt_template` variable to customize:
- Section headers and styling
- Emoji usage
- Spacing and layout
- Call-to-action messages

## Troubleshooting

### Backend Issues

- **ChromaDB errors**: Delete the `backend/chroma/` folder and restart the server
  ```bash
  Remove-Item -Recurse -Force backend/chroma  # PowerShell
  rm -rf backend/chroma  # Bash
  ```
- **PDF processing errors**: Ensure your PDF files are not corrupted or password-protected
- **Groq API errors**: 
  - Verify your `GROQ_API_KEY` is set correctly in `.env` file
  - Check your API key at [https://console.groq.com/keys](https://console.groq.com/keys)
  - Ensure you have API credits/quota available
- **SMTP authentication errors**: 
  - For Gmail: Use an App Password, not your regular password
  - Ensure 2-factor authentication is enabled before generating app password
  - Check that `SENDER_EMAIL` matches the account used for the app password
  - Remove any spaces from the app password in `.env`
- **Module import errors**: Make sure all dependencies are installed: `pip install -r requirements.txt`
- **Port already in use**: 
  - Check if another Flask app is running on port 5000
  - Kill the process or use a different port in `app.py`
- **Documents not updating**: After modifying documents, delete `backend/chroma/` and restart

### Frontend Issues

- **CORS errors**: Ensure the backend is running on port 5000
- **Build errors**: Delete `node_modules/` and run `npm install` again
- **API connection errors**: Verify backend is running and accessible at `http://localhost:5000`

## API Endpoints

- `GET /api/health` - Check backend health status
- `POST /api/initialize` - Initialize document processing (processes PDFs and creates embeddings)
- `POST /api/chat` - Send chat messages and get AI responses
  ```json
  {
    "message": "What services does iOSYS offer?",
    "response": "...",
    "contact_form": false,
    "meeting_form": false,
    "quick_replies": [...]
  }
  ```
- `POST /api/contact_company` - Submit contact form
  ```json
  {
    "name": "John Doe",
    "email": "john@example.com",
    "phone": "+1234567890",
    "message": "I'm interested in your services"
  }
  ```
- `POST /api/schedule_meeting` - Schedule a meeting
  ```json
  {
    "name": "John Doe",
    "email": "john@example.com",
    "phone": "+1234567890",
    "preferred_date": "2024-12-01 10:00 AM",
    "meeting_purpose": "Discuss AI solutions"
  }
  ```

## Dependencies

### Backend (see `backend/requirements.txt`)

**Web Framework:**
- Flask (2.3.3) - Web framework
- flask-cors (4.0.0) - CORS support

**Environment:**
- python-dotenv (1.0.0) - Environment variable management

**LangChain Ecosystem:**
- langchain (0.2.16) - Core LangChain library
- langchain-community (0.2.16) - Community integrations
- langchain-chroma (0.1.2) - ChromaDB integration
- langchain-groq (0.1.9) - Groq LLM integration

**Vector Database:**
- chromadb (0.5.5) - Vector database for embeddings

**LLM API:**
- groq (0.8.0) - Groq API client

**Document Processing:**
- pypdf (3.17.4) - PDF text extraction

**Embeddings & ML:**
- sentence-transformers (2.2.2) - Embedding generation
- torch (2.0.1) - PyTorch (required by sentence-transformers)
- transformers (>=4.30.0) - Hugging Face transformers
- numpy (>=1.24.0) - Numerical computing
- scikit-learn (>=1.3.0) - Machine learning utilities

**Data Validation:**
- pydantic (2.8.2) - Data validation

**HTTP:**
- requests (2.31.0) - HTTP library

### Frontend
- React - UI framework
- Tailwind CSS - Styling
- Axios - HTTP client
- Lucide React - Icons
- React Markdown - Markdown rendering

## License

This project is open source and available under the MIT License.
