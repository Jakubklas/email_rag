# Email RAG Pipeline

A production-ready Retrieval-Augmented Generation (RAG) system for intelligent email search and querying, designed to handle large-scale email archives with advanced conversational memory capabilities.

## 🎯 Overview

This system was originally developed for **Redcoat Express**, a freight forwarding company, to enable efficient search and analysis of employee email histories stored in large MBOX files. The solution provides a chat-based interface for natural language querying of email content with contextual understanding and memory persistence.

<img width="2677" height="1271" alt="Email_RAG_Architecture" src="https://github.com/user-attachments/assets/d94fee4a-a33e-4543-a2ed-959bf8394f9b" />


## ✨ Key Features

### 📧 Email Processing Pipeline
- **Large-scale MBOX streaming**: Efficiently processes multi-gigabyte email archives
- **Intelligent text extraction**: Handles email content, attachments (PDF, DOC, XLS, images), and thread reconstruction
- **Content cleaning**: Removes signatures, boilerplate, and formats text for optimal LLM consumption
- **Thread reconstruction**: Maintains conversational context across email chains

### 🔍 Advanced Search & Retrieval
- **Vector similarity search**: Powered by AWS OpenSearch with optimized embeddings
- **Intelligent query rewriting**: Enhances user queries for better retrieval accuracy
- **Multi-modal content support**: Searches across email text, attachments, and extracted images

### 🧠 Three-Tier Memory System
- **Short-term memory**: Recent conversation context
- **Mid-term memory**: Session-based conversation summaries
- **Long-term memory**: Persistent knowledge extraction and storage

### 🖥️ User Interface
- **Streamlit-based chat interface**: Intuitive conversational experience
- **User authentication**: Secure access control with registration/login
- **Responsive design**: Modern UI with custom styling and avatars

## 🏗️ Architecture

```
├── src/
│   ├── pipeline.py              # Main ingestion orchestrator
│   ├── ingestion/               # Data processing pipeline
│   │   ├── data_extraction.py   # MBOX file streaming and parsing
│   │   ├── data_processing.py   # Email cleaning and thread reconstruction
│   │   ├── data_embedding.py    # Vector embedding generation
│   │   └── opensearch_indexing.py # Vector store indexing
│   ├── querying/                # Query processing system
│   │   ├── query_service.py     # Main orchestrator
│   │   ├── search/              # Search and optimization
│   │   ├── memory/              # Memory management
│   │   └── formatting/          # Response formatting
│   ├── ui/                      # Streamlit interface
│   │   ├── pages/               # UI pages (chat, login, register)
│   │   ├── assets/              # Images and avatars
│   │   └── css/                 # Custom styling
│   └── utils/                   # Shared utilities
│       ├── clients/             # OpenAI and OpenSearch clients
│       ├── email_parser.py      # Email content extraction
│       ├── attachment_processor.py # File processing
│       └── embeddings.py        # Vector operations
├── config/
│   └── config.py               # Configuration and constants
├── app.py                      # Streamlit application entry point
└── requirements.txt            # Python dependencies
```

## 🚀 Getting Started

### Prerequisites

- Python 3.8+
- AWS account with OpenSearch domain
- OpenAI API key
- Tesseract OCR (for image text extraction)
- Poppler (for PDF processing)

### Installation

**Clone the repository**
```bash
git clone https://github.com/yourusername/email-rag-pipeline.git
cd email-rag-pipeline
```

**Install Python dependencies**
```bash
pip install -r requirements.txt
```

**Set up environment variables**
Create a `.env` file in the root directory:
```bash
SECRET_KEY=your_openai_api_key
OPENSEARCH_ENDPOINT=your_opensearch_endpoint
MASTER_USER=your_opensearch_username
MASTER_PASSWORD=your_opensearch_password
```

**Install system dependencies**
   
   **For Windows:**
   - Download Tesseract OCR and place in `applications/tesseract/`
   - Download Poppler and place in `applications/poppler/`
   
   **For Linux/Mac:**
   ```bash
   # Ubuntu/Debian
   sudo apt-get install tesseract-ocr poppler-utils
   
   # macOS
   brew install tesseract poppler
   ```

### Usage

**Data Ingestion**
Place your MBOX files in the `mbox_files/` directory and run the ingestion pipeline:

```bash
python src/pipeline.py
```

This will:
- Extract emails from MBOX files
- Process and clean email content
- Generate embeddings
- Index data in OpenSearch

**Launch the Application**
```bash
streamlit run app.py
```

Access the application at `http://localhost:8501`

**Query Your Emails**
- Register/login through the web interface
- Start asking questions about your email content
- The system will provide contextual responses with source references

## 📊 Technical Specifications

### Performance
- **Scalability**: Handles email archives with 100k+ messages
- **Memory efficiency**: Streaming processing minimizes RAM usage
- **Search speed**: Sub-second query response times
- **Concurrent processing**: Async operations for embedding generation

### AI Models
- **Embeddings**: OpenAI `text-embedding-ada-002`
- **Chat completion**: Dynamic model selection (GPT-3.5 to GPT-4) based on context size
- **Memory summarization**: Optimized for conversation persistence

### Data Storage
- **Vector store**: AWS OpenSearch with cosine similarity
- **Index structure**: Separate indices for emails and thread documents
- **Embedding dimensions**: 1536-dimensional vectors

## 🛠️ Configuration

Key configuration options in `config/config.py`:

```python
# Model settings
SMALL_MODEL = "gpt-3.5-turbo"
LARGE_MODEL = "gpt-4-32k" 
EMB_MODEL = "text-embedding-ada-002"

# Processing limits
CHUNK_TOKENS = 400
MAX_CONCURRENT = 20
num_emails = 5000  # For testing

# OpenSearch indices
EMAILS_INDEX = "email_documents"
THREADS_INDEX = "thread_documents"
```

## 🔧 Development

### Project Structure
- **Ingestion Pipeline** (`src/ingestion/`): Handles email extraction, processing, and indexing
- **Query Service** (`src/querying/`): Manages search, memory, and response generation
- **UI Components** (`src/ui/`): Streamlit-based user interface
- **Utilities** (`src/utils/`): Shared functionality and client connections

### Adding New Features
- **Email processors**: Extend `src/utils/` for new file formats
- **Search algorithms**: Modify `src/querying/search/`
- **Memory systems**: Enhance `src/querying/memory/`
- **UI improvements**: Update `src/ui/pages/`

## 📈 Use Cases

- **Enterprise email search**: Find specific communications across large archives
- **Customer service**: Quick access to historical customer interactions
- **Legal discovery**: Efficient document retrieval for compliance
- **Knowledge management**: Extract insights from organizational communications
- **Personal productivity**: Intelligent search through personal email history

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Originally developed for **Redcoat Express** freight forwarding company
- Built with modern RAG architecture principles
- Optimized for production-scale email processing

**Built with:** Python, Streamlit, OpenAI, AWS OpenSearch, and modern RAG techniques
