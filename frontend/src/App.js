import React, { useState, useRef, useEffect } from 'react';
import axios from 'axios';
import { Send, User, AlertCircle, CheckCircle } from 'lucide-react';
import ReactMarkdown from 'react-markdown';

// Add custom CSS for blinking animation
const blinkingStyle = `
  @keyframes blink {
    0%, 50% { opacity: 1; }
    51%, 100% { opacity: 0.6; }
  }
  .blink-animation {
    animation: blink 1.2s infinite;
  }
`;

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:5000/api';

function App() {
  const [messages, setMessages] = useState([]);
  const [inputMessage, setInputMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isInitialized, setIsInitialized] = useState(false);
  const [initError, setInitError] = useState('');
  const [contactForm, setContactForm] = useState({
    isActive: false,
    name: '',
    email: '',
    phone: '',
    message: ''
  });
  const [isSubmittingContact, setIsSubmittingContact] = useState(false);
  const [contactFormSubmitted, setContactFormSubmitted] = useState(false);
  const [isCalModalOpen, setIsCalModalOpen] = useState(false);
  const [calInitialized, setCalInitialized] = useState(false);
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  // Helper function to remove duplicate "What would you like to explore" text
  const cleanResponseContent = (content) => {
    if (!content) return content;
    let cleaned = content;
    cleaned = cleaned.replace(/\*\*What would you like to explore\?\*\*/g, '');
    cleaned = cleaned.replace(/What would you like to explore\?/g, '');
    cleaned = cleaned.replace(/\*\*What would you like to explore next\?\*\*/g, '');
    cleaned = cleaned.replace(/What would you like to explore next\?/g, '');
    cleaned = cleaned.replace(/\n\n\n+/g, '\n\n'); // Remove extra line breaks
    return cleaned.trim();
  };

  useEffect(() => {
    console.log('📜 Messages updated, scrolling to bottom. Total messages:', messages.length);
    scrollToBottom();
  }, [messages]);

  useEffect(() => {
    // Check backend health on component mount
    console.log('🚀 App component mounted, checking backend health...');
    checkBackendHealth();
    
    // Initialize Cal.com loader (with error handling)
    try {
      if (typeof window !== 'undefined' && !window.Cal) {
        (function (C, A, L) {
          try {
            let p = function (a, ar) { 
              try {
                a.q.push(ar); 
              } catch (e) {
                console.error('Cal.com queue error:', e);
              }
            };
            let d = C.document;
            C.Cal = C.Cal || function () {
              try {
                let cal = C.Cal;
                let ar = arguments;
                if (!cal.loaded) {
                  cal.ns = {};
                  cal.q = cal.q || [];
                  const script = d.createElement("script");
                  script.src = A;
                  script.async = true;
                  script.onerror = () => console.error('Failed to load Cal.com script');
                  d.head.appendChild(script);
                  cal.loaded = true;
                }
                if (ar[0] === L) {
                  const api = function () { p(api, arguments); };
                  const namespace = ar[1];
                  api.q = api.q || [];
                  if(typeof namespace === "string") {
                    cal.ns[namespace] = cal.ns[namespace] || api;
                    p(cal.ns[namespace], ar);
                    p(cal, ["initNamespace", namespace]);
                  } else p(cal, ar);
                  return;
                }
                p(cal, ar);
              } catch (e) {
                console.error('Cal.com function error:', e);
              }
            };
          } catch (e) {
            console.error('Cal.com loader initialization error:', e);
          }
        })(window, "https://app.cal.com/embed/embed.js", "init");
      }
    } catch (error) {
      console.error('Failed to initialize Cal.com loader:', error);
    }
  }, []);

  // Initialize Cal.com when modal opens
  useEffect(() => {
    if (isCalModalOpen && !calInitialized) {
      let retryCount = 0;
      const maxRetries = 10;
      let timeoutId = null;
      let isMounted = true;
      
      const initCal = () => {
        if (!isMounted) return;
        
        const calElement = document.getElementById('my-cal-inline-30-min-meeting');
        
        if (!calElement) {
          if (retryCount < maxRetries) {
            retryCount++;
            timeoutId = setTimeout(initCal, 200);
          }
          return;
        }
        
        if (!window.Cal) {
          if (retryCount < maxRetries) {
            retryCount++;
            timeoutId = setTimeout(initCal, 300);
          } else {
            console.error('❌ Cal.com script failed to load');
          }
          return;
        }
        
        try {
          // Clear any existing content
          calElement.innerHTML = '';
          
          // Initialize Cal.com namespace first
          window.Cal("init", "30-min-meeting", {origin:"https://app.cal.com"});
          
          // Wait a bit for namespace to be ready
          timeoutId = setTimeout(() => {
            if (!isMounted) return;
            
            try {
              if (window.Cal && window.Cal.ns && window.Cal.ns["30-min-meeting"]) {
                window.Cal.ns["30-min-meeting"]("inline", {
                  elementOrSelector: "#my-cal-inline-30-min-meeting",
                  config: {"layout":"month_view"},
                  calLink: "shreyash.iosys/30-min-meeting",
                });
                window.Cal.ns["30-min-meeting"]("ui", {
                  "hideEventTypeDetails": false,
                  "layout": "month_view"
                });
                
                setCalInitialized(true);
                console.log('✅ Cal.com initialized successfully');
              } else {
                console.warn('⚠️ Cal.com namespace not ready, retrying...');
                if (retryCount < maxRetries) {
                  retryCount++;
                  timeoutId = setTimeout(initCal, 500);
                }
              }
            } catch (error) {
              console.error('❌ Cal.com inline initialization error:', error);
              if (retryCount < maxRetries && isMounted) {
                retryCount++;
                timeoutId = setTimeout(initCal, 500);
              }
            }
          }, 500);
        } catch (error) {
          console.error('❌ Cal.com initialization error:', error);
          if (retryCount < maxRetries && isMounted) {
            retryCount++;
            timeoutId = setTimeout(initCal, 500);
          }
        }
      };

      // Wait for modal to render
      timeoutId = setTimeout(initCal, 300);
      
      // Cleanup function
      return () => {
        isMounted = false;
        if (timeoutId) {
          clearTimeout(timeoutId);
        }
      };
    }
  }, [isCalModalOpen, calInitialized]);

  const checkBackendHealth = async () => {
    console.log('🔍 Checking backend health at:', `${API_BASE_URL}/health`);
    try {
      const response = await axios.get(`${API_BASE_URL}/health`);
      console.log('✅ Backend health check successful:', response.data);
      setIsInitialized(true);
    } catch (error) {
      console.error('❌ Backend health check failed:', error.message);
      console.error('Error details:', error.response?.data || error);
      setInitError('Backend server is not running. Please start the Flask server.');
    }
  };

  const initializeDocuments = async () => {
    console.log('📚 Starting document initialization...');
    try {
      setIsLoading(true);
      const response = await axios.post(`${API_BASE_URL}/initialize`);
      console.log('✅ Documents initialized successfully:', response.data);
      setIsInitialized(true);
      setInitError('');
      setMessages([{
        id: Date.now(),
        type: 'bot',
        content: 'Documents have been successfully initialized! You can now ask questions about the content.',
        timestamp: new Date()
      }]);
    } catch (error) {
      console.error('❌ Document initialization failed:', error.message);
      console.error('Error details:', error.response?.data || error);
      setInitError('Failed to initialize documents. Please check if PDF files are in the documents folder.');
    } finally {
      setIsLoading(false);
      console.log('📚 Document initialization process completed');
    }
  };

  const sendMessage = async () => {
    if (!inputMessage.trim() || isLoading) {
      console.log('⚠️ Message send blocked - empty message or loading in progress');
      return;
    }

    console.log('💬 Sending user message:', inputMessage);
    
    const userMessage = {
      id: Date.now(),
      type: 'user',
      content: inputMessage,
      timestamp: new Date()
    };

    console.log('📝 User message object created:', userMessage);
    setMessages(prev => {
      const newMessages = [...prev, userMessage];
      console.log('📋 Updated messages array length:', newMessages.length);
      return newMessages;
    });
    
    const messageToSend = inputMessage;
    setInputMessage('');
    setIsLoading(true);

    try {
      console.log('🚀 Making API request to:', `${API_BASE_URL}/chat`);
      console.log('📤 Request payload:', { message: messageToSend });
      
      const response = await axios.post(`${API_BASE_URL}/chat`, {
        message: messageToSend
      });

      console.log('📥 API response received:', response.data);
      console.log('🤖 Bot response content:', response.data.response);

      const botMessage = {
        id: Date.now() + 1,
        type: 'bot',
        content: cleanResponseContent(response.data.response),
        timestamp: new Date(),
        showContactForm: response.data.contact_form || false,
        quickReplies: response.data.quick_replies || []
      };

      console.log('🤖 Bot message object created:', botMessage);
      setMessages(prev => {
        const newMessages = [...prev, botMessage];
        console.log('📋 Final messages array length:', newMessages.length);
        return newMessages;
      });
      
      // Activate contact form if needed (only if not already submitted)
      if (response.data.contact_form && !contactFormSubmitted) {
        console.log('📋 Activating contact form');
        setContactForm(prev => ({ ...prev, isActive: true }));
      }
      
      // Open Cal.com modal if meeting form is requested
      if (response.data.meeting_form) {
        console.log('📅 Opening Cal.com booking modal');
        setTimeout(() => openCalModal(), 500);
      }
    } catch (error) {
      console.error('❌ Chat API request failed:', error.message);
      console.error('Error response:', error.response?.data);
      console.error('Error status:', error.response?.status);
      console.error('Full error object:', error);
      
      const errorMessage = {
        id: Date.now() + 1,
        type: 'bot',
        content: 'Sorry, I encountered an error while processing your request. Please try again.',
        timestamp: new Date(),
        quickReplies: [
          {"text": "Services", "value": "our_services"},
          {"text": "Products", "value": "products"},
          {"text": "Contact Us", "value": "contact_us"}
        ]
      };
      
      console.log('⚠️ Error message object created:', errorMessage);
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
      console.log('✅ Message send process completed');
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      console.log('⌨️ Enter key pressed, sending message');
      e.preventDefault();
      sendMessage();
    }
  };



  const handleContactSubmit = async () => {
    console.log('📧 Submitting contact form:', contactForm);
    
    // Validate form
    if (!contactForm.name || !contactForm.email || !contactForm.phone || !contactForm.message) {
      alert('Please fill in all required fields.');
      return;
    }
    
    setIsSubmittingContact(true);
    
    try {
      const response = await axios.post(`${API_BASE_URL}/contact_company`, {
        name: contactForm.name,
        email: contactForm.email,
        phone: contactForm.phone,
        message: contactForm.message
      });
      
      console.log('✅ Contact request sent successfully:', response.data);
      
      // Add success message
      const successMessage = {
        id: Date.now(),
        type: 'bot',
        content: '✅ Thank you for contacting us! Your message has been sent successfully. Our team will get back to you soon.',
        timestamp: new Date()
      };
      
      setMessages(prev => [...prev, successMessage]);
      
      // Mark contact form as submitted and reset
      setContactFormSubmitted(true);
      setContactForm({
        isActive: false,
        name: '',
        email: '',
        phone: '',
        message: ''
      });
      
    } catch (error) {
      console.error('❌ Contact request failed:', error);
      
      // Add error message
      const errorMessage = {
        id: Date.now(),
        type: 'bot',
        content: '⚠️ Sorry, something went wrong while sending your message. Please try again later.',
        timestamp: new Date()
      };
      
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsSubmittingContact(false);
    }
  };

  const updateContactField = (field, value) => {
    setContactForm(prev => ({ ...prev, [field]: value }));
  };

  const openCalModal = () => {
    setIsCalModalOpen(true);
    document.body.style.overflow = 'hidden';
  };

  const closeCalModal = () => {
    setIsCalModalOpen(false);
    document.body.style.overflow = '';
    // Reset initialization when closing to allow re-initialization on next open
    setCalInitialized(false);
  };

  const handleQuickReply = (replyValue) => {
    console.log('🔘 Quick reply clicked:', replyValue);
    
    // If it's a schedule demo request, open Cal.com modal
    if (replyValue === 'schedule_demo') {
      openCalModal();
      return;
    }
    
    // Add user message to show what button was clicked
    const userMessage = {
      id: Date.now(),
      type: 'user',
      content: replyValue.replace('_', ' '),
      timestamp: new Date()
    };
    
    setMessages(prev => [...prev, userMessage]);
    
    // Send the actual value to backend
    sendMessageWithValue(replyValue);
  };

  const sendMessageWithValue = async (messageValue) => {
    setIsLoading(true);

    try {
      console.log('🚀 Making API request to:', `${API_BASE_URL}/chat`);
      console.log('📤 Request payload:', { message: messageValue });
      
      const response = await axios.post(`${API_BASE_URL}/chat`, {
        message: messageValue
      });

      console.log('📥 API response received:', response.data);
      console.log('🤖 Bot response content:', response.data.response);

      const botMessage = {
        id: Date.now() + 1,
        type: 'bot',
        content: cleanResponseContent(response.data.response),
        timestamp: new Date(),
        showContactForm: response.data.contact_form || false,
        quickReplies: response.data.quick_replies || []
      };

      console.log('🤖 Bot message object created:', botMessage);
      setMessages(prev => {
        const newMessages = [...prev, botMessage];
        console.log('📋 Final messages array length:', newMessages.length);
        return newMessages;
      });
      
      // Activate contact form if needed (only if not already submitted)
      if (response.data.contact_form && !contactFormSubmitted) {
        console.log('📋 Activating contact form');
        setContactForm(prev => ({ ...prev, isActive: true }));
      }
      
      // Open Cal.com modal if meeting form is requested
      if (response.data.meeting_form) {
        console.log('📅 Opening Cal.com booking modal');
        setTimeout(() => openCalModal(), 500);
      }
    } catch (error) {
      console.error('❌ Chat API request failed:', error.message);
      console.error('Error response:', error.response?.data);
      console.error('Error status:', error.response?.status);
      console.error('Full error object:', error);
      
      const errorMessage = {
        id: Date.now() + 1,
        type: 'bot',
        content: 'Sorry, I encountered an error while processing your request. Please try again.',
        timestamp: new Date(),
        quickReplies: [
          {"text": "Services", "value": "our_services"},
          {"text": "Products", "value": "products"},
          {"text": "Contact Us", "value": "contact_us"}
        ]
      };
      
      console.log('⚠️ Error message object created:', errorMessage);
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
      console.log('✅ Message send process completed');
    }
  };

  return (
    <div className="flex flex-col h-screen bg-gray-50">
      <style>{blinkingStyle}</style>
      {/* Header */}
      <div className="bg-white shadow-sm border-b px-6 py-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <img src="/iosys.jpeg" alt="Iosys" className="w-8 h-8 rounded" />
            <div>
              <h1 className="text-xl font-semibold text-gray-900">Help Assistant</h1>
              <p className="text-sm text-gray-500"> </p>
            </div>
          </div>
          <div className="flex items-center space-x-2">
            {isInitialized ? (
              <div className="flex items-center text-teal-700">
                <CheckCircle className="w-4 h-4 mr-1" />
                <span className="text-sm"> </span>
              </div>
            ) : (
              <button
                onClick={initializeDocuments}
                disabled={isLoading}
                className="bg-teal-700 text-white px-4 py-2 rounded-lg hover:bg-teal-800 disabled:opacity-50 text-sm"
              >
                {isLoading ? 'Initializing...' : 'Initialize Documents'}
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Error Message */}
      {initError && (
        <div className="bg-red-50 border-l-4 border-red-400 p-4 mx-6 mt-4">
          <div className="flex">
            <AlertCircle className="w-5 h-5 text-red-400" />
            <div className="ml-3">
              <p className="text-sm text-red-700">{initError}</p>
            </div>
          </div>
        </div>
      )}

      {/* Messages Container */}
      <div className="flex-1 overflow-y-auto px-6 py-4">
        {messages.length === 0 && isInitialized && (
          <div className="text-center text-gray-500 mt-20">
            <img src="/iosys.jpeg" alt="Iosys" className="w-16 h-16 mx-auto mb-4 opacity-30 rounded" />
            <div className="bg-white text-gray-900 shadow-sm border rounded-lg p-4 max-w-md mx-auto">
              <p className="mb-4">Hi! I am an Assistant. Welcome to iOSYS <br />How can I assist you today?</p>
              <div className="flex flex-wrap gap-2 justify-center">
                <button
                  onClick={() => handleQuickReply('schedule_demo')}
                  className="bg-blue-100 text-blue-800 px-4 py-2 rounded-full text-sm font-medium hover:bg-blue-200 transition-colors border border-blue-300"
                >
                  📅 Schedule a Meeting
                </button>
                <button
                  onClick={() => handleQuickReply('know_more')}
                  className="bg-teal-100 text-teal-800 px-4 py-2 rounded-full text-sm font-medium hover:bg-teal-200 transition-colors border border-teal-300"
                >
                  Know more about us
                </button>
                {/* <button
                  onClick={() => handleQuickReply('read_article')}
                  className="bg-teal-100 text-teal-800 px-4 py-2 rounded-full text-sm font-medium hover:bg-teal-200 transition-colors border border-teal-300"
                >
                  Read an article
                </button> */}
                <button
                  onClick={() => handleQuickReply('our_services')}
                  className="bg-teal-100 text-teal-800 px-4 py-2 rounded-full text-sm font-medium hover:bg-teal-200 transition-colors border border-teal-300"
                >
                  Our services
                </button>
                <button
                  onClick={() => handleQuickReply('contact_us')}
                  className="bg-teal-100 text-teal-800 px-4 py-2 rounded-full text-sm font-medium hover:bg-teal-200 transition-colors border border-teal-300"
                >
                  Contact us
                </button>
              </div>
            </div>
          </div>
        )}

        {messages.map((message) => (
          <div key={message.id} className={`mb-6 flex ${message.type === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div className={`flex max-w-3xl ${message.type === 'user' ? 'flex-row-reverse' : 'flex-row'}`}>
              <div className={`flex-shrink-0 ${message.type === 'user' ? 'ml-3' : 'mr-3'}`}>
                <div className={`w-8 h-8 rounded-full flex items-center justify-center ${
                  message.type === 'user' ? 'bg-teal-800' : 'bg-gray-600'
                }`}>
                  {message.type === 'user' ? (
                    <User className="w-4 h-4 text-white" />
                  ) : (
                    <img src="/iosys.jpeg" alt="Iosys" className="w-6 h-6 rounded" />
                  )}
                </div>
              </div>
              <div className={`flex-1 ${message.type === 'user' ? 'text-right' : 'text-left'}`}>
                <div className={`inline-block p-4 rounded-lg ${
                  message.type === 'user' 
                    ? 'bg-teal-800 text-white' 
                    : 'bg-white text-gray-900 shadow-sm border'
                }`}>
                  {message.type === 'user' ? (
                    <p className="whitespace-pre-wrap">{message.content}</p>
                  ) : (
                    <ReactMarkdown 
                      className="prose prose-sm max-w-none"
                      components={{
                        ul: ({node, ...props}) => <ul style={{display: 'block', listStylePosition: 'outside'}} {...props} />,
                        li: ({node, ...props}) => <li style={{display: 'list-item'}} {...props} />
                      }}
                    >
                      {message.content}
                    </ReactMarkdown>
                  )}
                  
                  {/* Quick Reply Buttons */}
                  {message.quickReplies && message.quickReplies.length > 0 && (
                    <div className="mt-4 pt-3 border-t border-gray-200">
                      <p className="text-sm font-medium text-gray-700 mb-3">What would you like to explore next?</p>
                      <div className="flex flex-wrap gap-2">
                        {message.quickReplies.map((reply, index) => (
                          <button
                            key={index}
                            onClick={() => handleQuickReply(reply.value)}
                            className="bg-teal-100 text-teal-800 px-4 py-2 rounded-full text-sm font-medium hover:bg-teal-200 transition-colors border border-teal-300 shadow-sm"
                          >
                            {reply.text}
                          </button>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Contact Form */}
                  {message.showContactForm && contactForm.isActive && !contactFormSubmitted && (
                    <div className="mt-4 p-4 bg-gray-50 rounded-lg border">
                      <p className="text-sm text-gray-700 mb-3 font-medium">To get more information, fill this form.</p>
                      <h4 className="font-semibold mb-3 text-gray-800">Contact Information</h4>
                      <div className="space-y-3">
                        <div>
                          <label className="block text-sm font-medium text-gray-700 mb-1">Full Name *</label>
                          <input
                            type="text"
                            value={contactForm.name}
                            onChange={(e) => updateContactField('name', e.target.value)}
                            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-teal-600 focus:border-transparent"
                            placeholder="Enter your full name"
                          />
                        </div>
                        <div>
                          <label className="block text-sm font-medium text-gray-700 mb-1">Email Address *</label>
                          <input
                            type="email"
                            value={contactForm.email}
                            onChange={(e) => updateContactField('email', e.target.value)}
                            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-teal-600 focus:border-transparent"
                            placeholder="Enter your email address"
                          />
                        </div>
                        <div>
                          <label className="block text-sm font-medium text-gray-700 mb-1">Phone Number *</label>
                          <input
                            type="tel"
                            value={contactForm.phone}
                            onChange={(e) => updateContactField('phone', e.target.value)}
                            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-teal-600 focus:border-transparent"
                            placeholder="Enter your phone number"
                          />
                        </div>
                        <div>
                          <label className="block text-sm font-medium text-gray-700 mb-1">Message / Reason for Contacting *</label>
                          <textarea
                            value={contactForm.message}
                            onChange={(e) => updateContactField('message', e.target.value)}
                            rows="3"
                            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-teal-600 focus:border-transparent"
                            placeholder="Please describe your inquiry or reason for contacting us"
                          />
                        </div>
                        <button
                          onClick={handleContactSubmit}
                          disabled={isSubmittingContact || !contactForm.name || !contactForm.email || !contactForm.phone || !contactForm.message}
                          className="w-full bg-teal-700 text-white py-2 px-4 rounded-md hover:bg-teal-800 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                        >
                          {isSubmittingContact ? 'Sending Request...' : 'Send Request'}
                        </button>
                      </div>
                    </div>
                  )}


                </div>
                
                
                <p className="text-xs text-gray-400 mt-1">
                  {message.timestamp.toLocaleTimeString()}
                </p>
              </div>
            </div>
          </div>
        ))}

        {isLoading && (
          <div className="flex justify-start mb-6">
            <div className="flex mr-3">
              <div className="w-8 h-8 rounded-full bg-gray-600 flex items-center justify-center">
                <img src="/iosys.jpeg" alt="Iosys" className="w-6 h-6 rounded" />
              </div>
            </div>
            <div className="bg-white border rounded-lg p-4 shadow-sm">
              <div className="flex space-x-1">
                <div className="w-2 h-2 bg-teal-600 rounded-full animate-bounce"></div>
                <div className="w-2 h-2 bg-teal-600 rounded-full animate-bounce" style={{animationDelay: '0.1s'}}></div>
                <div className="w-2 h-2 bg-teal-600 rounded-full animate-bounce" style={{animationDelay: '0.2s'}}></div>
              </div>
            </div>
          </div>
        )}
        
        <div ref={messagesEndRef} />
      </div>

      {/* Cal.com Booking Modal */}
      {isCalModalOpen && (
        <div 
          className="cal-modal-overlay"
          style={{
            display: 'flex',
            position: 'fixed',
            top: 0,
            left: 0,
            width: '100%',
            height: '100%',
            background: 'rgba(0,0,0,0.8)',
            zIndex: 9999,
            padding: '20px',
            boxSizing: 'border-box',
            alignItems: 'center',
            justifyContent: 'center',
            overflow: 'auto'
          }}
          onClick={(e) => {
            if (e.target === e.currentTarget) {
              closeCalModal();
            }
          }}
        >
          <div 
            className="cal-modal-container"
            style={{
              position: 'relative',
              width: '100%',
              maxWidth: '1050px',
              height: '90%',
              maxHeight: '800px',
              background: 'white',
              borderRadius: '12px',
              overflow: 'hidden',
              boxShadow: '0 10px 50px rgba(0,0,0,0.3)',
              display: 'flex',
              flexDirection: 'column'
            }}
          >
            <button
              onClick={closeCalModal}
              style={{
                position: 'absolute',
                top: '15px',
                right: '15px',
                background: 'rgba(0,0,0,0.1)',
                border: 'none',
                fontSize: '28px',
                cursor: 'pointer',
                zIndex: 10000,
                color: '#666',
                width: '40px',
                height: '40px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                borderRadius: '50%',
                transition: 'all 0.3s ease'
              }}
              onMouseOver={(e) => e.target.style.background = 'rgba(0,0,0,0.2)'}
              onMouseOut={(e) => e.target.style.background = 'rgba(0,0,0,0.1)'}
            >
              &times;
            </button>
            <div 
              style={{
                width: '100%',
                height: '100%',
                overflow: 'auto',
                minHeight: '600px',
                paddingBottom: '20px',
                WebkitOverflowScrolling: 'touch'
              }}
              id="my-cal-inline-30-min-meeting"
            ></div>
          </div>
        </div>
      )}

      {/* Input Area */}
      <div className="bg-white border-t px-6 py-4">
        <div className="flex space-x-4">
          <div className="flex-1">
            <textarea
              value={inputMessage}
              onChange={(e) => setInputMessage(e.target.value)}
              onKeyPress={handleKeyPress}
              placeholder={isInitialized ? "Ask a question ..." : "Please initialize documents first"}
              disabled={!isInitialized || isLoading}
              className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-teal-600 focus:border-transparent resize-none disabled:bg-gray-100 disabled:cursor-not-allowed"
              rows="1"
              style={{ minHeight: '48px', maxHeight: '120px' }}
            />
          </div>
          <button
            onClick={sendMessage}
            disabled={!inputMessage.trim() || !isInitialized || isLoading}
            className="bg-teal-700 text-white p-3 rounded-lg hover:bg-teal-800 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            <Send className="w-5 h-5" />
          </button>
        </div>
      </div>
    </div>
  );
}

export default App;
