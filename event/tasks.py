# event/tasks.py

from background_task import background
from django.core.mail import EmailMultiAlternatives
from django.conf import settings
from datetime import datetime

@background(schedule=10)
def send_email_task(subject, html_content, from_email, recipient_list):
    print("=" * 50)
    print(f"send_email_task started at {datetime.now()}")
    print(f"Attempting to send email: subject='{subject}', from='{from_email}', to={recipient_list}")
    
    email = EmailMultiAlternatives(
        subject=subject, 
        body=html_content,  
        from_email=from_email, 
        to=recipient_list
    )
    email.attach_alternative(html_content, "text/html")  
    try:
        print(f"Email content: {html_content[:100]}...")  # Print first 100 chars of content
        email.send()
        print("Email sent successfully")
    except Exception as e:
        print(f"Error sending email: {str(e)}")
        import traceback
        print(traceback.format_exc())

    print(f"send_email_task completed at {datetime.now()}")
    print("=" * 50)