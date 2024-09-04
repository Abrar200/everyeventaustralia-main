from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from users.models import CustomUser
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import PasswordResetView, PasswordResetDoneView, PasswordResetConfirmView, PasswordResetCompleteView
from django.urls import reverse_lazy
from django.shortcuts import render
from django.contrib.auth.models import User
from django.utils.http import urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.contrib.auth.tokens import default_token_generator
from django.contrib.auth import get_user_model
from django.contrib.sites.shortcuts import get_current_site
from django.template.loader import render_to_string
from django.core.mail import send_mail, get_connection
from django.conf import settings
from django.utils.http import urlsafe_base64_encode
import logging
import smtplib
from django.utils.html import strip_tags
from django.contrib.auth.tokens import default_token_generator as token_generator
from django.urls import reverse
from django.views import View


# Initialize the logger
logger = logging.getLogger(__name__)

class UserRegistrationView(View):
    def get(self, request):
        return render(request, 'users/user_registration.html')

    def post(self, request):
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        username = request.POST.get('email')
        email = request.POST.get('email')
        password = request.POST.get('password')
        confirm_password = request.POST.get('confirmPassword')

        if password == confirm_password:
            # Check if the email already exists
            if CustomUser.objects.filter(email=email).exists():
                messages.error(request, 'An account with this email address already exists. Please log in instead.')
            else:
                user = CustomUser.objects.create_user(
                    username=username,
                    first_name=first_name,
                    last_name=last_name,
                    email=email,
                    password=password,
                    is_active=False
                )

                self.send_verification_email(user, request)
                messages.success(request, 'Registration successful. Please check your email to verify your account.')
                return redirect('login')
        else:
            messages.error(request, 'Passwords do not match.')

        return render(request, 'users/user_registration.html')

    def send_verification_email(self, user, request):
        current_site = settings.SITE_URL
        mail_subject = 'Activate your account.'
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = token_generator.make_token(user)
        verification_link = reverse('verify_email', kwargs={'uidb64': uid, 'token': token})
        verification_url = f"{current_site}{verification_link}"
        
        html_message = render_to_string('event/email_verification.html', {
            'user': user,
            'verification_url': verification_url,
            'domain': current_site,
        })
        plain_message = strip_tags(html_message)
        from_email = settings.DEFAULT_FROM_EMAIL
        to_email = user.email

        send_mail(
            mail_subject,
            plain_message,
            from_email,
            [to_email],
            html_message=html_message,
        )

def user_login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')

        user = authenticate(request, username=username, password=password)

        if user is not None:
            if user.is_active:
                login(request, user)
                messages.success(request, 'Login successful.')
                return redirect('home')  # Replace 'home' with the URL name of your desired destination
            else:
                messages.error(request, 'Your account is inactive. Please verify your email to activate your account.')
        else:
            messages.error(request, 'Invalid username or password.')

    return render(request, 'users/user_login.html')

def logout_view(request):
    logout(request)
    messages.success(request, 'Logout successful.')
    return redirect('login')

def profile(request, username):
    username = request.user.username
    return render(request, "users/profile.html")


@login_required
def profile(request, username):
    if request.method == 'POST':
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        email = request.POST.get('email')

        # Update the user's information
        user = request.user
        user.first_name = first_name
        user.last_name = last_name
        user.email = email
        user.save()

        messages.success(request, 'Your profile has been updated successfully.')
        return redirect('profile', username=user.username)

    # Retrieve the user's current information
    user = request.user
    context = {
        'first_name': user.first_name,
        'last_name': user.last_name,
        'email': user.email,
        'username': user.username,
    }

    return render(request, 'users/profile.html', context)



def password_reset_request_view(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        if email:
            try:
                user = CustomUser.objects.get(email=email)
                subject = "Password Reset Requested"
                email_template_name = "users/password_reset_email.html"
                c = {
                    "email": user.email,
                    "domain": request.get_host(),
                    "site_name": "Your Site",
                    "uid": urlsafe_base64_encode(force_bytes(user.pk)),
                    "user": user,
                    "token": default_token_generator.make_token(user),
                    "protocol": 'http',
                }
                email_content = render_to_string(email_template_name, c)

                logger.debug(f"Sending email to {user.email}")
                logger.debug(f"Email content: {email_content}")

                # Create an SMTP connection with debug level set to 1
                connection = get_connection()
                connection.open()
                connection.connection.set_debuglevel(1)

                send_mail(
                    subject,
                    email_content,
                    settings.DEFAULT_FROM_EMAIL,
                    [user.email],
                    fail_silently=False,
                    connection=connection
                )

                messages.success(request, 'A message with reset password instructions has been sent to your inbox.')
                logger.debug("Email sent successfully")
                return redirect('password_reset_done')

            except CustomUser.DoesNotExist:
                messages.error(request, 'No account found with this email address.')
                logger.error("No account found with this email address")
                return redirect('reset_password')


    return render(request, 'users/password_reset.html')


def password_reset_done_view(request):
    return render(request, 'users/password_reset_done.html')


def password_reset_confirm_view(request, uidb64, token):
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = CustomUser.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, CustomUser.DoesNotExist):
        user = None

    if user is not None and default_token_generator.check_token(user, token):
        if request.method == 'POST':
            new_password1 = request.POST.get('new_password1')
            new_password2 = request.POST.get('new_password2')
            if new_password1 == new_password2:
                user.set_password(new_password1)
                user.save()
                messages.success(request, 'Password has been reset.')
                return redirect('password_reset_complete')
            else:
                messages.error(request, 'Passwords do not match.')
        return render(request, 'users/password_reset_confirm.html')
    else:
        messages.error(request, 'The reset link is no longer valid.')
        return redirect('reset_password')


def password_reset_complete_view(request):
    return render(request, 'users/password_reset_complete.html')