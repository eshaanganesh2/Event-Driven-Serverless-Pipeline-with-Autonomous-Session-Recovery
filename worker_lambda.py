import os
from refreshCookies import RefreshCookies
import time
from playwright.sync_api import sync_playwright
from refreshCookies import RefreshCookies
import requests
import os
import boto3

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(os.environ.get('PIN_TABLE_NAME', 'PinStoreTable'))

def get_linkedin_page():
    global browser_instance, pw_instance
    print("Launching Playwright Browser...")
    
    pw_instance = sync_playwright().start()
    browser_instance = pw_instance.chromium.launch(
        executable_path="/opt/chrome-linux64/chrome",
        args=[
            "--disable-blink-features=AutomationControlled",
            "--lang=en-US",
            "--headless=new",
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--single-process",
            "--disable-gpu"
        ]
    )
    
    context = browser_instance.new_context(
        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    page = context.new_page()
    page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    page.mouse.wheel(0, 400)
    time.sleep(2)
    print("Playwright launched successfully!")
    page.goto("https://www.linkedin.com/uas/login", wait_until="networkidle")
    return page

def poll_for_pin():
    print("Waiting for PIN to appear in DynamoDB...")
    timeout = 300  # 5 minutes
    start = time.time()
    owner = os.environ.get('OWNER')
    while time.time() - start < timeout:
        response = table.get_item(Key={'owner': owner})
        if 'Item' in response:
            pin = response['Item']['pin']
            # Delete it immediately so it's not reused
            table.delete_item(Key={'owner': owner})
            return pin
        time.sleep(5) # Check every 5 seconds
    return None

def send_to_whatsapp_api(payload):
    token = os.environ.get("WHATSAPP_BEARER_TOKEN")
    url = os.environ.get("WHATSAPP_API_URL")
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    requests.post(url, headers=headers, json=payload)

def lambda_handler(event, context):
    username = os.environ.get('LINKEDIN_EMAIL')
    password = os.environ.get('LINKEDIN_PASSWORD')
    owner = os.environ.get("OWNER")
    data = event    
    # Check for manual refresh request
    try:
        msg_value = data['entry'][0]['changes'][0]['value']
        webhook_reply = msg_value['messages'][0]['interactive']['button_reply']['title']
        
        if webhook_reply == "Refresh cookies now!":
            print("Owner chose to refresh cookies now")
            global page_obj
            page_obj = get_linkedin_page()
            refresh_service = RefreshCookies()
            refresh_service.login(page_obj, username, password)
            
            if refresh_service.is_pin_verification_page(page_obj):
                print("PIN verification page has come up")
                payload = {
                    "messaging_product": "whatsapp",
                    "to": owner,
                    "type": "text",
                    "text": {"body": "Please share LinkedIn login verification code in the specified format:\n\n verification code=<verification_code>"}
                }
                print("Sending message for verification code")
                send_to_whatsapp_api(payload)
                # 2. WAIT HERE (Keep browser open)
                pin = poll_for_pin()
                
                if pin:
                    print(f"PIN {pin} found! Injecting...")
                    refresh_service.verify_pin(page_obj, pin)
                else:
                    print("Timed out waiting for PIN.")
            
            # Cleanup browser before Lambda ends
            page_obj.context.browser.close()
    except Exception as e:
        print("Not a cookie refresh button reply")

    return "Success", 200
