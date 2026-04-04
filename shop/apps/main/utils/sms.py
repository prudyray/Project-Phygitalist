import requests
import base64
from django.conf import settings
import json
import logging

logger = logging.getLogger("shop.apps.main.utils")

def get_auth_token():
    authkey = settings.SMS_AUTH_KEY
    authtoken = settings.SMS_AUTH_TOKEN

    authheader = f'{authkey}:{authtoken}'
    authheader_bytes = base64.b64encode(authheader.encode())
    authheader_str = authheader_bytes.decode()

    token = f'Basic {authheader_str}'

    return token

def send_phone_otp(phone, otp, sms_template=None):
    token = get_auth_token()
    authkey = settings.SMS_AUTH_KEY

    if sms_template is None:
        sms_template = settings.SMS_LOGIN_OTP_TEMPLATE
    sms_text = eval('f' + repr(sms_template))

    destination_number = f"{phone.country_code}{phone.national_number}"

    data = {
        "Text": sms_text,
        "Number": destination_number,
        "SenderId": settings.SMS_SENDER_ID,
        "Tool": "API"
    }
    
    logger.debug(f"Sending {sms_text} to {destination_number}")

    headers = {
        "Authorization": token,
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    SMS_PRODUCTION_URL = f'https://restapi.smscountry.com/v0.1/Accounts/{authkey}/SMSes/'
    #SMS_MOCK_URL = f'https://private-anon-ccec9b3d62-smscountryapi.apiary-mock.com/v0.1/Accounts/{authkey}/SMSes/'
    SMS_MOCK_URL = f"https://private-anon-ed72d6af06-smscountryapi.apiary-mock.com/v0.1/Accounts/{authkey}/SMSes/"

    sms_live = getattr(settings, "SMS_LIVE", False)
    if sms_live:
        url = SMS_PRODUCTION_URL
        logger.debug(f"send_phone_otp: SMS_LIVE=True, using PRODUCTION URL")
    else:
        url = SMS_MOCK_URL
        logger.debug(f"send_phone_otp: SMS_LIVE=False, using MOCK URL")

    logger.debug(f"send_phone_otp: posting to {url} with data={data}")

    resp = requests.post(url, data=json.dumps(data), headers=headers)
    logger.debug(f"send_phone_otp: response status={resp.status_code}")
    try:
        json_resp = resp.json()
    except requests.exceptions.JSONDecodeError:
        json_resp = resp.text

    logger.debug(f"send_phone_otp: response body={json_resp}")

    return json_resp
