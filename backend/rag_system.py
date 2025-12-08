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
        elif text_clean in ["products", "product", "our products"]:
            return "products"
        elif text_clean in ["read an article", "read_article", "article", "blog", "case studies", "case_studies"]:
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
                'answer': "**Welcome to iOSYS! 👋**\n\nI'm here to help you discover how AI can transform your business. Ask me anything about our services, products, or book a meeting with our experts.",
                'sources': [],
                'quick_replies': [
                    {"text": "Services", "value": "our_services"},
                    {"text": "Products", "value": "products"},
                    {"text": "Book a Meeting", "value": "schedule_demo"},
                    {"text": "Contact Us", "value": "contact_us"}
                ]
            }
        
        elif input_type == "end_chat":
            return {
                'answer': "**Thanks for connecting! 😊**\n\nBefore you go - our team would love to show you how iOSYS AI solutions can transform your business.\n\n**Ready to take the next step?**",
                'sources': [],
                'quick_replies': [
                    {"text": "Book a Meeting", "value": "schedule_demo"},
                    {"text": "Services", "value": "our_services"},
                    {"text": "Contact Us", "value": "contact_us"}
                ]
            }
        elif input_type == "simple":
            question_lower = question.lower()
            if "who are you" in question_lower or "what is your name" in question_lower:
                return {
                    'answer': "I'm your AI assistant for iOSYS. I can help you learn about our AI solutions, products, and services.\n\n**What can I help you with?**",
                    'sources': [],
                    'quick_replies': [
                        {"text": "Services", "value": "our_services"},
                        {"text": "Products", "value": "products"},
                        {"text": "Contact Us", "value": "contact_us"}
                    ]
                }
            elif "help" in question_lower:
                return {
                    'answer': "I'm here to help! Ask me about our AI services, products, case studies, or book a meeting with our team.\n\n**Where should we start?**",
                    'sources': [],
                    'quick_replies': [
                        {"text": "Services", "value": "our_services"},
                        {"text": "Products", "value": "products"},
                        {"text": "Book a Meeting", "value": "schedule_demo"}
                    ]
                }
            elif "thank" in question_lower:
                return {
                    'answer': "You're welcome! Happy to help anytime. 😊\n\n**Anything else you'd like to know?**",
                    'sources': [],
                    'quick_replies': [
                        {"text": "Services", "value": "our_services"},
                        {"text": "Book a Meeting", "value": "schedule_demo"},
                        {"text": "Contact Us", "value": "contact_us"}
                    ]
                }
        
        return None
    
    def _get_contact_response(self) -> Dict[str, Any]:
        """Generate response for contact requests"""
        return {
            'answer': "**Let's Connect! 📧**\n\nI'll help you get in touch with our team. Share a few quick details and we'll reach out to you shortly.\n\n• Full name\n• Email address\n• Phone number\n• Brief message\n\nOnce you provide the details, click 'Send Request' to submit.",
            'sources': [],
            'contact_form': True,
            'quick_replies': [
                {"text": "Services", "value": "our_services"},
                {"text": "Products", "value": "products"},
                {"text": "Book a Meeting", "value": "schedule_demo"}
            ]
        }
    
    def _get_meeting_response(self) -> Dict[str, Any]:
        """Generate response for meeting requests"""
        return {
            'answer': "**Book Your Meeting! 🗓️**\n\nLet's schedule a personalized session with our AI experts. Just provide a few details:\n\n• Full name\n• Email address\n• Phone number\n• Preferred date & time\n• Topics to discuss\n\nClick 'Schedule Meeting' when ready!",
            'sources': [],
            'meeting_form': True,
            'quick_replies': [
                {"text": "Services", "value": "our_services"},
                {"text": "Products", "value": "products"},
                {"text": "Contact Us", "value": "contact_us"}
            ]
        }
    
    def _get_quick_reply_response(self, reply_type: str) -> Dict[str, Any]:
        """Generate responses for quick reply buttons"""
        if reply_type == "schedule_demo":
            return {
                'answer': "**Book Your Meeting! 🗓️**\n\nLet's connect you with our team. Share your details and we'll schedule a personalized demo.\n\n• Date & time preference\n• Topics you want to explore\n• Best way to reach you\n\n**Ready to schedule?**",
                'sources': [],
                'contact_form': True,
                'quick_replies': [
                    {"text": "Services", "value": "our_services"},
                    {"text": "Products", "value": "products"},
                    {"text": "Contact Us", "value": "contact_us"}
                ]
            }
        elif reply_type == "know_more":
            # Use RAG system to get company information from vector database
            if self.vectorstore and self.qa_chain:
                try:
                    result = self.qa_chain.invoke({"query": "Tell me about iOSYS company - what they do, their expertise, services, and achievements. Do NOT include why choose iOSYS or benefits sections."})
                    
                    # Add contextual quick replies
                    quick_replies = self._get_contextual_buttons(result['result'], "know_more")
                    
                    return {
                        'answer': result['result'],
                        'sources': [],
                        'quick_replies': quick_replies,
                        'contact_form': True
                    }
                except Exception as e:
                    logger.warning(f"Failed to get company info from vector database: {e}")
            
            # Fallback to basic search if vector database fails
            fallback_result = self._basic_search("Tell me about iOSYS company - what they do, their expertise, services, and achievements. Do NOT include why choose iOSYS or benefits sections.")
            fallback_result['contact_form'] = True
            return fallback_result
        elif reply_type == "products":
            # Use RAG system to get products information from vector database
            if self.vectorstore and self.qa_chain:
                try:
                    result = self.qa_chain.invoke({"query": "What are ALL iOSYS products? List every product available including aippoint.ai, AI Support Chatbot, Social Media Automation, and any other products or solutions."})
                    
                    # Add contextual quick replies
                    quick_replies = self._get_contextual_buttons(result['result'], "products")
                    
                    return {
                        'answer': result['result'],
                        'sources': [],
                        'quick_replies': quick_replies,
                        'contact_form': True
                    }
                except Exception as e:
                    logger.warning(f"Failed to get products from vector database: {e}")
            
            # Fallback to basic search if vector database fails
            fallback_result = self._basic_search("What are ALL iOSYS products? List every product available including aippoint.ai, AI Support Chatbot, Social Media Automation, and any other products or solutions.")
            fallback_result['contact_form'] = True
            return fallback_result
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
                        'quick_replies': quick_replies,
                        'contact_form': True
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
                        'quick_replies': quick_replies,
                        'contact_form': True
                    }
                except Exception as e:
                    logger.warning(f"Failed to get services from vector database: {e}")
            
            # Fallback to basic search if vector database fails
            fallback_result = self._basic_search("What are iOSYS services and offerings? List all services with details.")
            fallback_result['contact_form'] = True
            return fallback_result
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
            'answer': "I'm here to help! Try one of these options to get started.",
            'sources': [],
            'quick_replies': [
                {"text": "Services", "value": "our_services"},
                {"text": "Products", "value": "products"},
                {"text": "Book a Meeting", "value": "schedule_demo"},
                {"text": "Contact Us", "value": "contact_us"}
            ]
        }
    
    def _get_contextual_buttons(self, response_text: str, input_type: str) -> list:
        """Generate contextual quick reply buttons based on response content and input type"""
        response_lower = response_text.lower()
        buttons = []
        
        # Service-related responses
        if any(keyword in response_lower for keyword in ['service', 'ai', 'development', 'solution', 'automation']):
            if input_type != "our_services":
                buttons.append({"text": "Services", "value": "our_services"})
            if input_type != "products":
                buttons.append({"text": "Products", "value": "products"})
            buttons.append({"text": "Book a Meeting", "value": "schedule_demo"})
        
        # Demo/meeting related responses
        elif any(keyword in response_lower for keyword in ['demo', 'meeting', 'consultation', 'discuss']):
            if {"text": "Book a Meeting", "value": "schedule_demo"} not in buttons:
                buttons.append({"text": "Book a Meeting", "value": "schedule_demo"})
            buttons.append({"text": "Contact Us", "value": "contact_us"})
            buttons.append({"text": "Services", "value": "our_services"})
        
        # Contact/support related responses
        elif any(keyword in response_lower for keyword in ['contact', 'support', 'help', 'team']):
            if {"text": "Contact Us", "value": "contact_us"} not in buttons:
                buttons.append({"text": "Contact Us", "value": "contact_us"})
            buttons.append({"text": "Services", "value": "our_services"})
        
        # Information/learning related responses
        elif any(keyword in response_lower for keyword in ['learn', 'information', 'about', 'company', 'product']):
            if input_type != "know_more":
                buttons.append({"text": "Know More", "value": "know_more"})
            buttons.append({"text": "Case Studies", "value": "read_article"})
            buttons.append({"text": "Contact Us", "value": "contact_us"})
        
        # Default buttons if no specific context found
        else:
            buttons = [
                {"text": "Services", "value": "our_services"},
                {"text": "Products", "value": "products"},
                {"text": "Case Studies", "value": "read_article"},
                {"text": "Book a Meeting", "value": "schedule_demo"},
                {"text": "Contact Us", "value": "contact_us"}
            ]
        
        # Return 3-5 buttons for interactive options
        return buttons[:5]
    
    def _setup_qa_chain(self):
        """Setup the QA chain with custom prompt optimized for Groq"""
        # Enhanced prompt template optimized for short, chat-friendly responses
        prompt_template = """You are an iOSYS AI assistant. Answer questions using ONLY information from the provided context. Never make up information.

        Context: {context}

        Question: {question}

        STRICT RESPONSE RULES (MANDATORY):
        1. MAXIMUM LENGTH:
           • Summary: EXACTLY 2-3 lines only (no more)
           • Bullet points: EXACTLY 4-6 bullets (provide comprehensive list)
           • Each bullet: MAXIMUM 3-5 words (just the name/title, NO descriptions)
           • No long sentences, no paragraphs, no full explanations in bullets
        
        2. FORMAT (ALWAYS FOLLOW THIS):
           Title
           2-3 line summary
           4-6 concise bullet points (names only, no descriptions)
           "Next options" section
        
        3. FORBIDDEN:
           ✗ No long marketing content
           ✗ No repeating the same text
           ✗ No 7+ bullet points (MAXIMUM 6)
           ✗ No full page explanations
           ✗ No paragraphs longer than 3 lines
           ✗ No "Why choose iOSYS" sections for "know more" queries
           ✗ NO descriptions in bullet points (just names/titles)
           ✗ NO sentences in bullet points (just 3-5 words max)
        
        4. DO NOT include "What would you like to explore next?" text in your response
           The buttons will be displayed automatically - just provide the content
        
        5. TONE: Friendly, simple, clear, business-focused (like Cal.com, Intercom, Notion AI)
        
        6. Use ONLY information from the context - never invent details
        7. Answer STRICTLY to what is asked - do NOT add extra sections
        8. Break down complex information into condensed versions only

        RESPONSE FORMAT (MANDATORY):

        **[Topic Title]**

        [EXACTLY 1-2 lines summary - keep it simple and clear]

        • [Bullet point 1 - 3-5 words max, just the name/title]
        • [Bullet point 2 - 3-5 words max, just the name/title]
        • [Bullet point 3 - 3-5 words max, just the name/title, only if needed]

        EXAMPLES:

        Question: "What services does iOSYS offer?"
        **iOSYS Services**

        We help businesses build and scale with AI-powered solutions.

        • AI Product Roadmap
        • Build & Modernize with AI
        • Autonomous Agents

        ---

        Question: "Tell me about iOSYS" or "Know more about iOSYS"
        **About iOSYS**

        iOSYS builds AI and automation solutions for modern businesses.

        • AI product development
        • Autonomous AI agents
        • Digital transformation

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

        STRICT RESPONSE RULES (MANDATORY):
        1. MAXIMUM LENGTH:
           • Summary: EXACTLY 2-3 lines only (no more)
           • Bullet points: EXACTLY 4-6 bullets (provide comprehensive list)
           • Each bullet: MAXIMUM 3-5 words (just the name/title, NO descriptions)
           • No long sentences, no paragraphs, no full explanations in bullets
        
        2. FORMAT (ALWAYS FOLLOW THIS):
           Title
           2-3 line summary
           4-6 concise bullet points (names only, no descriptions)
           "Next options" section
        
        3. FORBIDDEN:
           ✗ No long marketing content
           ✗ No repeating the same text
           ✗ No 7+ bullet points (MAXIMUM 6)
           ✗ No full page explanations
           ✗ No paragraphs longer than 3 lines
           ✗ No "Why choose iOSYS" sections for "know more" queries
           ✗ NO descriptions in bullet points (just names/titles)
           ✗ NO sentences in bullet points (just 3-5 words max)
        
        4. DO NOT include "What would you like to explore next?" text in your response
           The buttons will be displayed automatically - just provide the content
        
        5. TONE: Friendly, simple, clear, business-focused (like Cal.com, Intercom, Notion AI)
        
        6. Use ONLY information from the context - never invent details
        7. Answer STRICTLY to what is asked - do NOT add extra sections
        8. Break down complex information into condensed versions only

        RESPONSE FORMAT (MANDATORY):

        **[Topic Title]**

        [EXACTLY 2-3 lines summary - keep it simple and clear]

        • [Bullet point 1 - 3-5 words max, just the name/title]
        • [Bullet point 2 - 3-5 words max, just the name/title]
        • [Bullet point 3 - 3-5 words max, just the name/title]
        • [Bullet point 4 - 3-5 words max, just the name/title]
        • [Bullet point 5 - 3-5 words max, just the name/title, if available]
        • [Bullet point 6 - 3-5 words max, just the name/title, if available]

        EXAMPLES:

        Question: "What services does iOSYS offer?"
        **iOSYS Services**

        We help businesses build and scale with AI-powered solutions tailored to your needs.

        • AI Product Roadmap
        • Build & Modernize with AI
        • Autonomous Agents
        • AutoFlow AI
        • Ready To Go AI
        • AmplifyAI Marketing

        ---

        Question: "Tell me about iOSYS" or "Know more about iOSYS"
        **About iOSYS**

        iOSYS is a global technology company specializing in AI-driven solutions and business automation.

        • AI product development
        • Autonomous AI agents
        • Digital transformation
        • Business automation

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
            if input_type in ["schedule_demo", "know_more", "products", "read_article", "our_services", "contact_us", "end_chat"]:
                return self._get_quick_reply_response(input_type)
            
            # Check if documents are initialized for complex queries
            if not self.is_initialized:
                return {
                    'answer': "Please initialize the system first before asking questions.",
                    'sources': [],
                    'quick_replies': [
                        {"text": "Services", "value": "our_services"},
                        {"text": "Products", "value": "products"},
                        {"text": "Contact Us", "value": "contact_us"}
                    ]
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
                'sources': [],
                'quick_replies': [
                    {"text": "Services", "value": "our_services"},
                    {"text": "Products", "value": "products"},
                    {"text": "Contact Us", "value": "contact_us"}
                ]
            }
