import jwt
import hashlib
import secrets
import random
from datetime import timedelta
from django.utils import timezone
from django.conf import settings

def generate_otp(phone_number=None):
    if phone_number in ['+8801700000000', '01700000000']:
        return '123456'
    return str(random.randint(100000, 999999))

import requests

def send_otp_sms(phone_number, otp_code):
    print(f"\n[OTP DISPATCH] >>> Phone: {phone_number} | OTP: {otp_code} <<<\n")
    if phone_number in ['+8801700000000', '01700000000']:
        print(f"Mock demo account login. Skipping actual SMS for {phone_number}.")
        return True

    api_key = getattr(settings, 'AUTOMAS_SMS_API_KEY', '')
    if not api_key:
        return True

    clean_phone = phone_number.replace('+', '').replace('-', '').replace(' ', '')
    sender_id = getattr(settings, 'AUTOMAS_SMS_SENDER_ID', '') or 'ACCS'
    sms_text = f"[ACCS] Your OTP verification code is {otp_code}"

    params = {
        'apikey': api_key,
        'sender': sender_id,
        'msisdn': clean_phone,
        'smstext': sms_text,
    }

    url = getattr(settings, 'AUTOMAS_SMS_URL', 'https://api.automas.com.bd/smsapiv3')

    try:
        response = requests.post(url, data=params, timeout=10)
        response.raise_for_status()
        print(f"Automas API response for {phone_number}: {response.text}")
        return True
    except requests.exceptions.RequestException as e:
        print(f"Failed to send Automas SMS to {phone_number}: {e}")
        return False

def send_password_sms(phone_number, password):
    print(f"\n[PASSWORD DISPATCH] >>> Phone: {phone_number} | Password: {password} <<<\n")
    if phone_number in ['+8801700000000', '01700000000']:
        print(f"Mock demo account. Skipping actual SMS for {phone_number}.")
        return True

    api_key = getattr(settings, 'AUTOMAS_SMS_API_KEY', '')
    if not api_key:
        return True

    clean_phone = phone_number.replace('+', '').replace('-', '').replace(' ', '')
    sender_id = getattr(settings, 'AUTOMAS_SMS_SENDER_ID', '') or 'ACCS'
    sms_text = f"[ACCS] Welcome! Your registration is complete. Your password is: {password}. Login at ACCS."

    params = {
        'apikey': api_key,
        'sender': sender_id,
        'msisdn': clean_phone,
        'smstext': sms_text,
    }

    url = getattr(settings, 'AUTOMAS_SMS_URL', 'https://api.automas.com.bd/smsapiv3')

    try:
        response = requests.post(url, data=params, timeout=10)
        response.raise_for_status()
        print(f"Automas Password SMS response for {phone_number}: {response.text}")
        return True
    except requests.exceptions.RequestException as e:
        print(f"Failed to send Automas Password SMS to {phone_number}: {e}")
        return False

def generate_access_token(user):
    payload = {
        'user_id': user.id,
        'phone_number': user.phone_number,
        'exp': timezone.now() + timedelta(minutes=settings.JWT_ACCESS_EXPIRATION_MINUTES),
        'iat': timezone.now(),
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm='HS256')

def generate_refresh_token():
    return secrets.token_urlsafe(64)

def hash_token(token):
    return hashlib.sha256(token.encode('utf-8')).hexdigest()
