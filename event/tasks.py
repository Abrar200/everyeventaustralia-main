# tasks.py

from celery import shared_task
from django.core.mail import EmailMultiAlternatives
from django.conf import settings

@shared_task
def send_email_task(subject, html_content, from_email, recipient_list):

    # Create the email message with the HTML content
    email = EmailMultiAlternatives(
        subject=subject, 
        body=html_content,  # Set the body to the HTML content
        from_email=from_email, 
        to=recipient_list
    )
    email.attach_alternative(html_content, "text/html")  # Attach the HTML version
    
    # Send the email
    try:
        email.send()
    except Exception as e:
        print(f"Error sending email: {str(e)}")
