from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv
from rag_system import RAGSystem

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# Initialize RAG system (force reload)
rag_system = None

EMAIL_PROVIDER_DEFAULTS = {
    'gmail': {
        'server': 'smtp.gmail.com',
        'port': 587
    },
    'google': {
        'server': 'smtp.gmail.com',
        'port': 587
    },
    'microsoft': {
        'server': 'smtp.office365.com',
        'port': 587
    },
    'outlook': {
        'server': 'smtp.office365.com',
        'port': 587
    }
}

def get_rag_system():
    global rag_system
    if rag_system is None:
        rag_system = RAGSystem()
    return rag_system

def get_email_config():
    """Resolve SMTP configuration with provider-aware defaults."""
    provider = os.getenv('EMAIL_PROVIDER', '').strip().lower()
    smtp_server = os.getenv('SMTP_SERVER', '').strip()
    smtp_port = os.getenv('SMTP_PORT', '').strip()

    # Apply provider defaults if explicit values are missing
    if provider in EMAIL_PROVIDER_DEFAULTS:
        defaults = EMAIL_PROVIDER_DEFAULTS[provider]
        smtp_server = smtp_server or defaults['server']
        smtp_port = smtp_port or defaults['port']

    # Fallback to Gmail defaults if nothing else provided
    if not smtp_server:
        smtp_server = EMAIL_PROVIDER_DEFAULTS['gmail']['server']
    if not smtp_port:
        smtp_port = EMAIL_PROVIDER_DEFAULTS['gmail']['port']

    try:
        smtp_port = int(smtp_port)
    except ValueError:
        logger.warning(f"Invalid SMTP_PORT value '{smtp_port}'. Falling back to 587.")
        smtp_port = 587

    logger.info(f"Using email provider '{provider or 'custom'}' with server '{smtp_server}:{smtp_port}'")
    return smtp_server, smtp_port

@app.route('/api/chat', methods=['POST'])
def chat():
    try:
        data = request.get_json()
        query = data.get('message', '')
        
        if not query:
            return jsonify({'error': 'No message provided'}), 400
        
        # Get response from RAG system
        rag = get_rag_system()
        response = rag.query(query)
        
        return jsonify({
            'response': response['answer'],
            'contact_form': response.get('contact_form', False),
            'meeting_form': response.get('meeting_form', False),
            'quick_replies': response.get('quick_replies', [])
        })
    
    except Exception as e:
        logger.error(f"Error processing chat request: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({'status': 'healthy'})

@app.route('/api/initialize', methods=['POST'])
def initialize():
    try:
        rag = get_rag_system()
        rag.initialize_documents()
        return jsonify({'message': 'Documents initialized successfully'})
    except Exception as e:
        logger.error(f"Error initializing documents: {str(e)}")
        return jsonify({'error': 'Failed to initialize documents'}), 500

@app.route('/api/contact_company', methods=['POST'])
def contact_company():
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['name', 'email', 'phone', 'message']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        name = data['name']
        email = data['email']
        phone = data['phone']
        message = data['message']
        
        # Send email
        success = send_contact_email(name, email, phone, message)
        
        if success:
            logger.info(f"Contact request sent successfully for {name} ({email})")
            return jsonify({'message': 'Contact request sent successfully'})
        else:
            logger.error(f"Failed to send contact request for {name} ({email})")
            return jsonify({'error': 'Failed to send contact request'}), 500
            
    except Exception as e:
        logger.error(f"Error processing contact request: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/schedule_meeting', methods=['POST'])
def schedule_meeting():
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['name', 'email', 'phone', 'preferred_date', 'meeting_purpose']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        name = data['name']
        email = data['email']
        phone = data['phone']
        preferred_date = data['preferred_date']
        meeting_purpose = data['meeting_purpose']
        
        # Send meeting request email
        success = send_meeting_email(name, email, phone, preferred_date, meeting_purpose)
        
        if success:
            logger.info(f"Meeting request sent successfully for {name} ({email})")
            return jsonify({'message': 'Meeting request sent successfully'})
        else:
            logger.error(f"Failed to send meeting request for {name} ({email})")
            return jsonify({'error': 'Failed to send meeting request'}), 500
            
    except Exception as e:
        logger.error(f"Error processing meeting request: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

def send_contact_email(name, email, phone, message):
    """Send contact request email using configured SMTP (Gmail, Microsoft, etc.)"""
    try:
        # Get email configuration from environment variables
        smtp_server, smtp_port = get_email_config()
        sender_email = os.getenv('SENDER_EMAIL')
        sender_password = os.getenv('SENDER_PASSWORD')
        recipient_email = os.getenv('COMPANY_EMAIL')
        
        # Remove spaces from password (some email providers don't allow spaces in app passwords)
        if sender_password:
            sender_password = sender_password.replace(' ', '')
        
        logger.info(f"Email config - Server: {smtp_server}, Port: {smtp_port}")
        logger.info(f"Sender: {sender_email}, Recipient: {recipient_email}")
        
        if not all([sender_email, sender_password, recipient_email]):
            logger.error(f"Missing email configuration - Sender: {bool(sender_email)}, Password: {bool(sender_password)}, Recipient: {bool(recipient_email)}")
            return False
        
        # Create message
        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = recipient_email
        msg['Subject'] = f"New Contact Request from {name}"
        
        # Email body
        body = f"""
New Contact Request Received

Name: {name}
Email: {email}
Phone: {phone}

Message:
{message}

---
This email was sent automatically from the Iosys Chatbot contact form.
        """
        
        msg.attach(MIMEText(body, 'plain'))
        
        # Send email
        logger.info("Connecting to SMTP server...")
        server = smtplib.SMTP(smtp_server, smtp_port)
        logger.info("Starting TLS...")
        server.starttls()
        logger.info("Attempting login...")
        server.login(sender_email, sender_password)
        logger.info("Login successful, sending email...")
        text = msg.as_string()
        server.sendmail(sender_email, recipient_email, text)
        server.quit()
        
        logger.info(f"Email sent successfully to {recipient_email}")
        return True
        
    except smtplib.SMTPAuthenticationError as e:
        logger.error(f"SMTP Authentication failed: {str(e)} - Check your email and app password")
        return False
    except smtplib.SMTPException as e:
        logger.error(f"SMTP Error: {str(e)}")
        return False
    except Exception as e:
        logger.error(f"General error sending email: {str(e)}")
        return False

def send_meeting_email(name, email, phone, preferred_date, meeting_purpose):
    """Send meeting request email using configured SMTP (Gmail, Microsoft, etc.)"""
    try:
        # Get email configuration from environment variables
        smtp_server, smtp_port = get_email_config()
        sender_email = os.getenv('SENDER_EMAIL')
        sender_password = os.getenv('SENDER_PASSWORD')
        recipient_email = os.getenv('COMPANY_EMAIL')
        
        # Remove spaces from password (some email providers don't allow spaces in app passwords)
        if sender_password:
            sender_password = sender_password.replace(' ', '')
        
        logger.info(f"Email config - Server: {smtp_server}, Port: {smtp_port}")
        logger.info(f"Sender: {sender_email}, Recipient: {recipient_email}")
        
        if not all([sender_email, sender_password, recipient_email]):
            logger.error(f"Missing email configuration - Sender: {bool(sender_email)}, Password: {bool(sender_password)}, Recipient: {bool(recipient_email)}")
            return False
        
        # Create message
        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = recipient_email
        msg['Subject'] = f"New Meeting Request from {name}"
        
        # Email body
        body = f"""
New Meeting Request Received

Name: {name}
Email: {email}
Phone: {phone}
Preferred Date/Time: {preferred_date}

Meeting Purpose:
{meeting_purpose}

---
This email was sent automatically from the Iosys Chatbot meeting scheduler.
        """
        
        msg.attach(MIMEText(body, 'plain'))
        
        # Send email
        logger.info("Connecting to SMTP server...")
        server = smtplib.SMTP(smtp_server, smtp_port)
        logger.info("Starting TLS...")
        server.starttls()
        logger.info("Attempting login...")
        server.login(sender_email, sender_password)
        logger.info("Login successful, sending email...")
        text = msg.as_string()
        server.sendmail(sender_email, recipient_email, text)
        server.quit()
        
        logger.info(f"Meeting request email sent successfully to {recipient_email}")
        return True
        
    except smtplib.SMTPAuthenticationError as e:
        logger.error(f"SMTP Authentication failed: {str(e)} - Check your email and app password")
        return False
    except smtplib.SMTPException as e:
        logger.error(f"SMTP Error: {str(e)}")
        return False
    except Exception as e:
        logger.error(f"General error sending meeting email: {str(e)}")
        return False

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    app.run(debug=True, host='0.0.0.0', port=port)
