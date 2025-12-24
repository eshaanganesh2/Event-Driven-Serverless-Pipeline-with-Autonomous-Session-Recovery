import requests
import os
import json

# Obtaining latest LinkedIn post
def get_latest_post():
    url = os.environ.get("AWS_HOST")+"/Prod/getLatestPost"
    res = requests.get(url)
    print("Response from getLatestPost:", res.text)
    return res.text

# Sending whastapp notification
def send_to_whatsapp_contact(latest_post,recipient):
    # Prepare whatsapp graph api request body
    token = os.environ.get("WHATSAPP_BEARER_TOKEN")
    print("The token is ",token)
    print("The recipient is ",recipient)
    url = os.environ.get("WHATSAPP_API_URL")
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": recipient,
        "type": "text",
        "text": {
            "preview_url": True,
            "body": latest_post
        }
    }

    res = requests.post(url, headers=headers, json=payload)

    print("WhatsApp API response:", res.status_code, res.text)
    return {
        "statusCode": res.status_code,
        "body": res.text
    }

def lambda_handler(event, context):
    print("Starting scheduled orchestration...")
    recipients_str=os.environ.get("RECIPIENTS")
    print("The recipient list is ",recipients_str)
    recipients=json.loads(recipients_str)

    # Step 1: Call first endpoint
    latest_post = get_latest_post()

    # Step 3: Call second endpoint
    for recipient in recipients:
        send_to_whatsapp_contact(latest_post,recipient)

    return {"statusCode": 200, "body": "Workflow completed"}
