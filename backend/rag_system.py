import os
import logging
import re
from typing import List, Dict, Any
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# LangChain imports
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_groq import ChatGroq
from langchain_classic.chains import RetrievalQA
from langchain_core.prompts import PromptTemplate
from langchain_core.documents import Document

# HuggingFace API embeddings (required for production)
from langchain_huggingface import HuggingFaceEndpointEmbeddings

logger = logging.getLogger(__name__)

class RAGSystem:
    def __init__(self):
        self.chroma_path = os.path.join(os.path.dirname(__file__), "chroma")
        self.documents_path = os.path.join(os.path.dirname(__file__), "documents")
        
        # Define greeting patterns
        self.greeting_patterns = [
            r'^(hi|hello|hey|hii|hai|helo)\s*$',
            r'^(good\s+(morning|afternoon|evening))\s*$',
            r'^(how\s+are\s+you)\s*\??\s*$',
            r'^(what\s*s\s*up)\s*\??\s*$',
            r'^(greetings?)\s*$'
        ]
        
        # Define simple question patterns that don't need RAG
        self.simple_patterns = [
            r'^(who\s+are\s+you)\s*\??\s*$',
            r'^(what\s+is\s+your\s+name)\s*\??\s*$',
            r'^(help)\s*$',
            r'^(thanks?|thank\s+you)\s*$'
        ]
        
        # Define contact request patterns
        self.contact_patterns = [
            r'.*(contact|connect|reach|get\s+in\s+touch|speak\s+with|talk\s+to).*(company|team|someone|you)',
            r'.*(want|need|would\s+like)\s+to.*(contact|connect|speak)',
            r'.*how\s+(can|do)\s+i.*(contact|reach|connect)',
            r'.*(email|phone|call).*company',
            r'.*business\s+(inquiry|enquiry)',
            r'.*sales\s+(team|contact|inquiry)',
            r'.*partnership.*opportunity'
        ]
        
        # Define meeting request patterns
        self.meeting_patterns = [
            r'.*(book|schedule|arrange).*(meeting|appointment|call|demo)',
            r'.*(want|need|would\s+like)\s+to.*(meet|schedule|book)',
            r'.*schedule\s+(a|an)\s+(meeting|demo|call)',
            r'.*meeting\s+(request|booking)',
            r'.*demo\s+(request|booking)',
            r'.*consultation\s+(request|booking)',
            r'.*appointment\s+(request|booking)'
        ]
        
        # Initialize embeddings using HuggingFace API (Production Mode)
        try:
            huggingface_api_key = os.getenv("HUGGINGFACE_API_KEY")
            
            if not huggingface_api_key:
                raise ValueError("HUGGINGFACE_API_KEY not found in environment variables. Please set it in Render environment.")
            
            # Use HuggingFace Endpoint API (lightweight, no local models)
            self.embeddings = HuggingFaceEndpointEmbeddings(
                model="sentence-transformers/all-MiniLM-L6-v2",
                huggingfacehub_api_token=huggingface_api_key
            )
            logger.info("✅ Initialized HuggingFace API embeddings (Production Mode - No local models)")
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize HuggingFace API embeddings: {e}")
            logger.error("Please ensure HUGGINGFACE_API_KEY is set in environment variables")
            self.embeddings = None
        
        # Initialize text splitter
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            length_function=len,
        )
        
        # Initialize Groq LLM
        groq_api_key = os.getenv("GROQ_API_KEY")
        if not groq_api_key:
            raise ValueError("GROQ_API_KEY not found in environment variables. Please set it in the .env file.")
        
        self.llm = ChatGroq(
            api_key=groq_api_key,
            model="llama-3.1-8b-instant",  # Working Groq model
            temperature=0.0,  # Zero temperature for exact, consistent responses
            max_tokens=2048
        )
        
        # Initialize vector store and QA chain
        self.vectorstore = None
        self.qa_chain = None
        
        # Store documents in memory for basic text search fallback
        self.documents_text = []
        self.is_initialized = False
        
        # Auto-initialize if ChromaDB exists
        self._auto_initialize()
        
        logger.info("RAG System initialized")
    
    def _auto_initialize(self):
        """Automatically initialize if ChromaDB exists"""
        try:
            if self.embeddings:
                if os.path.exists(self.chroma_path) and os.listdir(self.chroma_path):
                    logger.info(f"Auto-initializing from existing ChromaDB at {self.chroma_path}...")
                    # Directly load existing ChromaDB
                    self.vectorstore = Chroma(
                        persist_directory=self.chroma_path,
                        embedding_function=self.embeddings
                    )
                    
                    # Test if vector store has documents
                    test_results = self.vectorstore.similarity_search("test", k=1)
                    if test_results:
                        logger.info(f"Successfully loaded existing ChromaDB with documents")
                        self._setup_qa_chain()
                        self.is_initialized = True
                        logger.info("RAG system auto-initialized successfully!")
                        return
                
                # ChromaDB doesn't exist or is empty, initialize with documents
                logger.info("ChromaDB not found or empty - initializing with documents...")
                self.initialize_documents()
        except Exception as e:
            logger.warning(f"Auto-initialization failed: {e} - will try manual initialization")
    
    def _classify_input(self, text: str) -> str:
        """Classify the input to determine response type"""
        text_clean = text.strip().lower()
        
        # Check for greetings
        for pattern in self.greeting_patterns:
            if re.match(pattern, text_clean, re.IGNORECASE):
                return "greeting"
        
        # Check for simple questions
        for pattern in self.simple_patterns:
            if re.match(pattern, text_clean, re.IGNORECASE):
                return "simple"
        
        # Check for quick reply options
        if text_clean in ["schedule a meeting", "schedule a demo", "schedule_demo", "demo", "meeting"]:
            return "schedule_demo"
        elif text_clean in ["know more about us", "know_more", "about us", "about"]:
            return "know_more"
        elif text_clean in ["read an article", "read_article", "article", "blog"]:
            return "read_article"
        elif text_clean in ["our services", "our_services", "services"]:
            return "our_services"
        elif text_clean in ["contact us", "contact_us", "contact"]:
            return "contact_us"
        
        # Check for end-of-chat indicators
        end_chat_patterns = [
            r'.*\b(bye|goodbye|thanks?|thank you|that\'?s all|done|finished|exit|quit)\b.*',
            r'.*\b(no more|nothing else|i\'?m good|all set)\b.*'
        ]
        for pattern in end_chat_patterns:
            if re.match(pattern, text_clean, re.IGNORECASE):
                return "end_chat"
        
        # Check for meeting requests first (more specific)
        for pattern in self.meeting_patterns:
            if re.search(pattern, text_clean, re.IGNORECASE):
                return "meeting_request"
        
        # Check for contact requests
        for pattern in self.contact_patterns:
            if re.search(pattern, text_clean, re.IGNORECASE):
                return "contact_request"
        
        # Check if it's a service-related query
        service_keywords = ['service', 'services', 'iosys', 'ai', 'development', 'generation', 'chatbot', 'automation', 'offer', 'provide', 'capabilities', 'solutions']
        if any(keyword in text_clean for keyword in service_keywords):
            return "service_query"
        
        # Default to general query
        return "general_query"
    
    def _get_simple_response(self, input_type: str, question: str) -> Dict[str, Any]:
        """Generate simple responses for greetings and basic questions"""
        if input_type == "greeting":
            return {
                'answer': "Hi! I am an Assistant. Welcome to iOSYS 🙂\nHow can I help you today?",
                'sources': [],
                'quick_replies': [
                    {"text": "Schedule a Meeting", "value": "schedule_demo"},
                    {"text": "Know more about us", "value": "know_more"},
                    {"text": "Read an article", "value": "read_article"},
                    {"text": "Our services", "value": "our_services"},
                    {"text": "Contact us", "value": "contact_us"}
                ]
            }
        
        elif input_type == "end_chat":
            return {
                'answer': "Thank you for chatting with me! 😊\n\nBefore you go, would you like to schedule a demo to see how iOSYS can transform your business? Our team would love to show you our AI solutions in action!\n\n🚀 **Ready to get started?**",
                'sources': [],
                'quick_replies': [
                    {"text": "Schedule a Meeting", "value": "schedule_demo"},
                    {"text": "Contact us", "value": "contact_us"},
                    {"text": "Our services", "value": "our_services"}
                ]
            }
        elif input_type == "simple":
            question_lower = question.lower()
            if "who are you" in question_lower or "what is your name" in question_lower:
                return {
                    'answer': "I'm an AI assistant here to help answer your questions.",
                    'sources': [],
                    'quick_replies': [
                        {"text": "Know more about us", "value": "know_more"},
                        {"text": "Our services", "value": "our_services"}
                    ]
                }
            elif "help" in question_lower:
                return {
                    'answer': "I can help answer your questions. Just ask me anything you'd like to know.",
                    'sources': [],
                    'quick_replies': [
                        {"text": "Our services", "value": "our_services"},
                        {"text": "Schedule a Meeting", "value": "schedule_demo"},
                        {"text": "Contact us", "value": "contact_us"}
                    ]
                }
            elif "thank" in question_lower:
                return {
                    'answer': "You're welcome! Feel free to ask if you have any other questions.",
                    'sources': [],
                    'quick_replies': [
                        {"text": "Schedule a Meeting", "value": "schedule_demo"},
                        {"text": "Our services", "value": "our_services"}
                    ]
                }
        
        return None
    
    def _get_contact_response(self) -> Dict[str, Any]:
        """Generate response for contact requests"""
        return {
            'answer': "I'd be happy to help you connect with our team! To proceed, I'll need to collect some information from you. Please provide the following details:\n\n📝 **Required Information:**\n• Your full name\n• Email address\n• Phone number\n• Message or reason for contacting\n\nOnce you provide all the details, I'll show you a 'Send Request' button to submit your contact request.",
            'sources': [],
            'contact_form': True
        }
    
    def _get_meeting_response(self) -> Dict[str, Any]:
        """Generate response for meeting requests"""
        return {
            'answer': "Great! I'd love to schedule a meeting for you. 🗓️\n\nTo book your personalized meeting with our experts, please provide the following details:\n\n📅 **Meeting Information Required:**\n• Your full name\n• Email address\n• Phone number\n• Preferred date and time\n• Meeting purpose/topics to discuss\n\nOnce you provide all the details, I'll show you a 'Schedule Meeting' button to book your appointment.",
            'sources': [],
            'meeting_form': True
        }
    
    def _get_quick_reply_response(self, reply_type: str) -> Dict[str, Any]:
        """Generate responses for quick reply buttons"""
        if reply_type == "schedule_demo":
            return {
                'answer': "Great! I'd love to schedule a meeting for you. 🗓️\n\nTo book your personalized meeting, please let me know your preferred:\n• Date\n• Time\n• Any specific areas you'd like to focus on\n\nOr would you prefer me to connect you directly with our team?",
                'sources': [],
                'contact_form': True
            }
        elif reply_type == "know_more":
            # Use RAG system to get company information from vector database
            if self.vectorstore and self.qa_chain:
                try:
                    result = self.qa_chain.invoke({"query": "Tell me about iOSYS company, what they do, why choose them, their expertise and achievements."})
                    
                    # Add contextual quick replies
                    quick_replies = self._get_contextual_buttons(result['result'], "know_more")
                    
                    return {
                        'answer': result['result'],
                        'sources': [],
                        'quick_replies': quick_replies
                    }
                except Exception as e:
                    logger.warning(f"Failed to get company info from vector database: {e}")
            
            # Fallback to basic search if vector database fails
            return self._basic_search("Tell me about iOSYS company, what they do, why choose them, their expertise and achievements.")
        elif reply_type == "read_article":
            # Use RAG system to get article/blog information from vector database
            if self.vectorstore and self.qa_chain:
                try:
                    result = self.qa_chain.invoke({"query": "What articles, blogs, or resources does iOSYS provide? List available content and resources."})
                    
                    # Add contextual quick replies
                    quick_replies = self._get_contextual_buttons(result['result'], "read_article")
                    
                    return {
                        'answer': result['result'],
                        'sources': [],
                        'quick_replies': quick_replies
                    }
                except Exception as e:
                    logger.warning(f"Failed to get articles from vector database: {e}")
            
            # Fallback to basic search if vector database fails
            return self._basic_search("What articles, blogs, or resources does iOSYS provide? List available content and resources.")
        elif reply_type == "our_services":
            # Use RAG system to get services information from vector database
            if self.vectorstore and self.qa_chain:
                try:
                    result = self.qa_chain.invoke({"query": "What are iOSYS services and offerings? List all services with details."})
                    
                    # Add contextual quick replies
                    quick_replies = self._get_contextual_buttons(result['result'], "our_services")
                    
                    return {
                        'answer': result['result'],
                        'sources': [],
                        'quick_replies': quick_replies
                    }
                except Exception as e:
                    logger.warning(f"Failed to get services from vector database: {e}")
            
            # Fallback to basic search if vector database fails
            return self._basic_search("What are iOSYS services and offerings? List all services with details.")
        elif reply_type == "contact_us":
            # Use RAG system to get contact information from vector database
            if self.vectorstore and self.qa_chain:
                try:
                    result = self.qa_chain.invoke({"query": "How to contact iOSYS? What are the contact details, email, website, and ways to reach the company?"})
                    
                    return {
                        'answer': result['result'],
                        'sources': [],
                        'contact_form': True
                    }
                except Exception as e:
                    logger.warning(f"Failed to get contact info from vector database: {e}")
            
            # Fallback to basic search if vector database fails
            contact_result = self._basic_search("How to contact iOSYS? What are the contact details, email, website, and ways to reach the company?")
            contact_result['contact_form'] = True
            return contact_result
        
        return {
            'answer': "I'm not sure how to help with that. Please try one of the options from the menu!",
            'sources': [],
            'quick_replies': [
                {"text": "Our services", "value": "our_services"},
                {"text": "Schedule a demo", "value": "schedule_demo"},
                {"text": "Contact us", "value": "contact_us"}
            ]
        }
    
    def _get_contextual_buttons(self, response_text: str, input_type: str) -> list:
        """Generate contextual quick reply buttons based on response content and input type"""
        response_lower = response_text.lower()
        buttons = []
        
        # Service-related responses
        if any(keyword in response_lower for keyword in ['service', 'ai', 'development', 'solution', 'automation']):
            if input_type != "our_services":
                buttons.append({"text": "Our services", "value": "our_services"})
            buttons.append({"text": "Schedule a Meeting", "value": "schedule_demo"})
        
        # Demo/meeting related responses
        if any(keyword in response_lower for keyword in ['demo', 'meeting', 'consultation', 'discuss']):
            if {"text": "Schedule a Meeting", "value": "schedule_demo"} not in buttons:
                buttons.append({"text": "Schedule a Meeting", "value": "schedule_demo"})
            buttons.append({"text": "Contact us", "value": "contact_us"})
        
        # Contact/support related responses
        if any(keyword in response_lower for keyword in ['contact', 'support', 'help', 'team']):
            if {"text": "Contact us", "value": "contact_us"} not in buttons:
                buttons.append({"text": "Contact us", "value": "contact_us"})
        
        # Information/learning related responses
        if any(keyword in response_lower for keyword in ['learn', 'information', 'about', 'company']):
            if input_type != "know_more":
                buttons.append({"text": "Know more about us", "value": "know_more"})
            if input_type != "read_article":
                buttons.append({"text": "Read an article", "value": "read_article"})
        
        # Default buttons if no specific context found
        if not buttons:
            buttons = [
                {"text": "Our services", "value": "our_services"},
                {"text": "Schedule a Meeting", "value": "schedule_demo"},
                {"text": "Contact us", "value": "contact_us"}
            ]
        
        # Limit to 3 buttons max for better UX
        return buttons[:3]
    
    def _setup_qa_chain(self):
        """Setup the QA chain with custom prompt optimized for Groq"""
        # Enhanced prompt template optimized for clean, structured responses
        prompt_template = """You are an iOSYS AI assistant. Answer questions using ONLY information from the provided context. Never make up information.

        Context: {context}

        Question: {question}

        CRITICAL FORMATTING RULES:
        1. Use ONLY information from the context - never invent details
        2. Add TWO blank lines between major sections
        3. Add ONE blank line between individual items in lists
        4. Use appropriate emojis for visual appeal
        5. Keep service descriptions brief (one line max)
        6. Format benefits as a clear bulleted list
        7. Case studies should be concise (one line per case study)
        8. Always end with a call-to-action

        FORMAT TEMPLATES:

        For Services Section:
        ## iOSYS Services and Offerings

        🚀 **AI Product Roadmap**

        💡 **Build & Modernize with AI**

        🤖 **Autonomous Agents**

        ⚙️ **AutoFlow AI**

        ✨ **Ready To Go AI**

        📈 **AmplifyAI Marketing**


        For Benefits Section:
        ## Benefits of iOSYS Services

        • 📊 Increased efficiency and productivity
        • 💰 Lower operational and marketing costs
        • 🎯 Smarter, data-driven decision-making
        • 🔄 Seamless automation across departments
        • 🚀 Scalable AI solutions for growing businesses


        For Products Section:
        ## Products

        📊 **aippoint.ai - Smart Hiring Platform**

        🤖 **AI Support Chatbot - Intelligent customer support**

        📱 **Social Media Automation System - Automates content creation and scheduling**


        For Case Studies:
        ## Case Studies & Success Stories

        • **AI-Driven Credit Scoring System**: Accelerated credit processing for a global bank
        • **Predicting Consumer Switching Behaviour**: Reduced churn for a telecom provider
        • **AI-Driven Chatbot for Banking Onboarding**: Streamlined onboarding process


        ALWAYS end with:

        🎯 **Ready to transform your business? Schedule a meeting with our experts today!**

        Answer:"""
        
        PROMPT = PromptTemplate(
            template=prompt_template, 
            input_variables=["context", "question"]
        )
        
        # Create retrieval QA chain with optimized settings for Groq
        self.qa_chain = RetrievalQA.from_chain_type(
            llm=self.llm,
            chain_type="stuff",
            retriever=self.vectorstore.as_retriever(
                search_type="similarity",
                search_kwargs={"k": 8}  # Increased to get more comprehensive context
            ),
            chain_type_kwargs={"prompt": PROMPT},
            return_source_documents=True
        )
    
    def initialize_documents(self):
        """Load documents from existing ChromaDB or process PDFs if needed"""
        try:
            # Always process documents fresh to ensure they're loaded
            documents = []
            
            # Process each document in documents folder
            for filename in os.listdir(self.documents_path):
                file_path = os.path.join(self.documents_path, filename)
                logger.info(f"Processing {filename}")
                
                if filename.endswith('.pdf'):
                    # Load PDF using LangChain
                    loader = PyPDFLoader(file_path)
                    pages = loader.load()
                    
                    # Add source metadata
                    for page in pages:
                        page.metadata['source'] = filename
                    
                    documents.extend(pages)
                    
                elif filename.endswith('.txt'):
                    # Load text file
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    # Create document object
                    doc = Document(page_content=content, metadata={'source': filename})
                    documents.append(doc)
            
            if documents:
                # Split documents into chunks
                texts = self.text_splitter.split_documents(documents)
                logger.info(f"Split documents into {len(texts)} chunks")
                
                # Store in ChromaDB if embeddings are available
                if self.embeddings:
                    try:
                        # Create ChromaDB vector store
                        self.vectorstore = Chroma.from_documents(
                            documents=texts,
                            embedding=self.embeddings,
                            persist_directory=self.chroma_path
                        )
                        
                        # Setup QA chain with vector store
                        self._setup_qa_chain()
                        
                        logger.info(f"Successfully stored {len(texts)} chunks in ChromaDB")
                        self.is_initialized = True
                        
                    except Exception as e:
                        logger.warning(f"Failed to store in ChromaDB: {e}. Using fallback text search.")
                        self.embeddings = None
                        self._fallback_to_text_search(texts)
                else:
                    self._fallback_to_text_search(texts)
            else:
                logger.warning("No documents found to process")
                
        except Exception as e:
            logger.error(f"Error initializing documents: {str(e)}")
            raise
    
    def _fallback_to_text_search(self, texts):
        """Fallback to basic text search when ChromaDB is not available"""
        self.documents_text = [{"content": doc.page_content, "source": doc.metadata.get('source', 'Unknown')} for doc in texts]
        logger.info(f"Stored {len(self.documents_text)} chunks in memory for basic search")
        self.is_initialized = True
    
    def _basic_search(self, question: str) -> Dict[str, Any]:
        """Basic text search when embeddings are not available"""
        if not self.documents_text:
            return {
                'answer': "I don't have information about that topic.",
                'sources': []
            }
        
        # Simple keyword matching
        question_lower = question.lower()
        relevant_docs = []
        
        for doc in self.documents_text:
            if any(word in doc['content'].lower() for word in question_lower.split()):
                relevant_docs.append(doc)
        
        if not relevant_docs:
            return {
                'answer': "I don't have relevant information to answer your question.",
                'sources': []
            }
        
        # Use top 3 most relevant documents as context
        context = "\n\n".join([doc['content'][:500] for doc in relevant_docs[:3]])
        
        # Create a simple prompt for the LLM with improved formatting
        prompt = f"""Answer the question using ONLY information from the provided context. Never make up information.

Information:
{context}

Question: {question}

CRITICAL FORMATTING RULES:
1. Use ONLY information from the context - never invent details
2. Add TWO blank lines between major sections
3. Add ONE blank line between individual items in lists
4. Use appropriate emojis for visual appeal
5. Keep service descriptions brief (one line max)
6. Format benefits as a clear bulleted list
7. Case studies should be concise (one line per case study)
8. Always end with a call-to-action

FORMAT TEMPLATES:

For Services Section:
## iOSYS Services and Offerings

🚀 **AI Product Roadmap**

💡 **Build & Modernize with AI**

🤖 **Autonomous Agents**


For Benefits Section:
## Benefits of iOSYS Services

• 📊 Increased efficiency and productivity
• 💰 Lower operational and marketing costs
• 🎯 Smarter, data-driven decision-making


For Products Section:
## Products

📊 **aippoint.ai - Smart Hiring Platform**

🤖 **AI Support Chatbot**


For Case Studies:
## Case Studies & Success Stories

• **AI-Driven Credit Scoring System**: Accelerated credit processing
• **Predicting Consumer Switching Behaviour**: Reduced churn


ALWAYS end with:

🎯 **Ready to transform your business? Schedule a meeting with our experts today!**

Answer:"""
        
        # Get response from Groq
        response = self.llm.invoke(prompt)
        
        # Prepare sources
        sources = []
        for i, doc in enumerate(relevant_docs[:3]):
            sources.append({
                'document': doc['source'],
                'chunk_id': i,
                'content_preview': doc['content'][:200] + "..." if len(doc['content']) > 200 else doc['content']
            })
        
        # Add contextual quick replies for basic search results
        quick_replies = self._get_contextual_buttons(response.content, "general_query")
        
        return {
            'answer': response.content,
            'sources': sources,
            'quick_replies': quick_replies
        }

    def query(self, question: str) -> Dict[str, Any]:
        """Main query method with input classification and appropriate responses"""
        try:
            # Classify the input type
            input_type = self._classify_input(question)
            
            # Handle simple inputs without RAG
            if input_type in ["greeting", "simple"]:
                simple_response = self._get_simple_response(input_type, question)
                if simple_response:
                    return simple_response
            
            # Handle contact requests
            if input_type == "contact_request":
                return self._get_contact_response()
            
            # Handle meeting requests
            if input_type == "meeting_request":
                return self._get_meeting_response()
            
            # Handle quick reply options
            if input_type in ["schedule_demo", "know_more", "read_article", "our_services", "contact_us", "end_chat"]:
                return self._get_quick_reply_response(input_type)
            
            # Check if documents are initialized for complex queries
            if not self.is_initialized:
                return {
                    'answer': "Please initialize the system first before asking questions.",
                    'sources': []
                }
            
            # Use ChromaDB vector search if available
            if self.vectorstore and self.qa_chain:
                try:
                    # Adjust retrieval parameters based on query type
                    if input_type == "service_query":
                        # Use more documents for service queries
                        self.qa_chain.retriever.search_kwargs = {"k": 8}
                    else:
                        # Use fewer documents for general queries
                        self.qa_chain.retriever.search_kwargs = {"k": 4}
                    
                    result = self.qa_chain.invoke({"query": question})
                    
                    # Format sources from ChromaDB
                    sources = []
                    if 'source_documents' in result:
                        for i, doc in enumerate(result['source_documents']):
                            sources.append({
                                'document': doc.metadata.get('source', 'Unknown'),
                                'chunk_id': i,
                                'content_preview': doc.page_content[:200] + "..." if len(doc.page_content) > 200 else doc.page_content
                            })
                    
                    # Add contextual quick replies based on response content
                    quick_replies = self._get_contextual_buttons(result['result'], input_type)
                    
                    return {
                        'answer': result['result'],
                        'sources': sources,
                        'quick_replies': quick_replies
                    }
                except Exception as e:
                    logger.warning(f"ChromaDB query failed: {e}. Falling back to basic search.")
                    return self._basic_search(question)
            else:
                # Use basic text search as fallback
                return self._basic_search(question)
            
        except Exception as e:
            logger.error(f"Error processing query: {str(e)}")
            return {
                'answer': "I apologize, but I encountered an error while processing your question. Please make sure your Groq API key is set correctly in the .env file.",
                'sources': []
            }
