from linkedin_api import Linkedin, client, cookie_repository
import os
import time
import shutil
import requests
from flask import Flask, request
import aws_lambda_wsgi
from playwright.sync_api import sync_playwright
from refreshCookies import RefreshCookies

app = Flask(__name__)

# Global variable to hold the browser for cleanup
browser_instance = None
pw_instance = None

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

def getLinkedinInstance(username, password, TMP_DIR):
    return Linkedin(username = username, password = password, cookies_dir=TMP_DIR)

def clear_cookies_jr(TMP_DIR):
   for name in os.listdir(TMP_DIR):
    path = os.path.join(TMP_DIR, name)
    if os.path.isfile(path) or os.path.islink(path):
        os.unlink(path)          
    elif os.path.isdir(path):
        shutil.rmtree(path)

@app.route("/helloWorld")
def print_hello_world():
    print("Hello World")
    username = os.environ.get('LINKEDIN_EMAIL')
    password = os.environ.get('LINKEDIN_PASSWORD')
    owner = os.environ.get('OWNER')
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
    return "Hello World"

@app.route("/getLatestPost")
def get_latest_post():
    print("Retrieving latest linkedIn post")

    username = os.environ.get('LINKEDIN_EMAIL')
    password = os.environ.get('LINKEDIN_PASSWORD')
    urnId = os.environ.get('URN_ID')

    print("The username is",username)

    TMP_DIR = os.environ.get("COOKIES_TMP_DIR", "./tmp/")  # local fallback

    os.makedirs(TMP_DIR, exist_ok=True)

    api={}
    try:
        api=getLinkedinInstance(username,password,TMP_DIR)
        print("api instance ",api)
    except client.ChallengeException as e:
        print("Challenge Exception")
        return {
            "error": "challenge_required",
            "message": str(e)
        }, 403
    # Expired cookies
    except cookie_repository.LinkedinSessionExpired:
        print("Session expired Exception")
        try:
            clear_cookies_jr(TMP_DIR)
            api=getLinkedinInstance(username,password,TMP_DIR)
        # Challenge to be solved
        except client.ChallengeException as e:
            try:
                print("Challenge Exception")
                return {
                    "error": "challenge_required",
                    "message": str(e)
                }, 403
            except Exception as e:
                print("Exception encountered ",e)
                return {
                    "error": "Exception",
                    "message": str(e)
                }, 500      
        except Exception as e:
            print("Exception encountered ",e)
            return {
                "error": "Exception",
                "message": str(e)
            }, 500
    except Exception as e:
        print("Exception encountered ",e)
        return {
            "error": "Exception",
            "message": str(e)
        }, 500
    
    post = api.get_profile_posts(urn_id=urnId,post_count=1)[0]
    # Extracting post content
    post_content = post["commentary"]["text"]["text"]

    print(post_content)

    return {
        "content": post_content
    }, 200

@app.route("/webhook", methods=['GET', 'POST'])
def print_webhooks():
    if request.method == 'GET':
        print('webhook endpoint verification')
        webhookVerifyToken = os.environ.get('WEBHOOK_VERIFY_TOKEN')
        mode = request.args.get('hub.mode')
        token = request.args.get("hub.verify_token")
        challenge = request.args.get("hub.challenge")

        if mode == "subscribe" and token == webhookVerifyToken:
            print("Webhook verified successfully!")
            return challenge, 200
        else:
            print("Webhook verification failed!")
            return 'Forbidden', 403
    
    if request.method == 'POST':
        username = os.environ.get('LINKEDIN_EMAIL')
        password = os.environ.get('LINKEDIN_PASSWORD')
        owner = os.environ.get("OWNER")
        data = request.get_json()
        print("The webhook is ",data)
        display_phone_number=""
        recipient_phone_number=""
        status=""
        timestamp=""
        webhook_reply=""
        try:
            display_phone_number = data.get('entry')[0].get('changes')[0].get('value').get('metadata').get('display_phone_number')
            recipient_phone_number = data.get('entry')[0].get('changes')[0].get('value').get('statuses')[0].get('recipient_id')
            status = data.get('entry')[0].get('changes')[0].get('value').get('statuses')[0].get('status')
            timestamp = data.get('entry')[0].get('changes')[0].get('value').get('statuses')[0].get('timestamp')
        except:
            print("Error while extracting value from a webhook field")       
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
        except Exception as e:
            print("Not a cookie refresh button reply")

        # Check for PIN submission
        try:
            body_text = data['entry'][0]['changes'][0]['value']['messages'][0]['text']['body']
            if body_text.startswith("verification code="):
                print("Extracting the user's provided verification code")
                pin = body_text.split("verification code=")[1].strip()
                RefreshCookies().verify_pin(page_obj, pin)
        except Exception as e:
            print("No verification code found in message")
        
        print("The sender phone number is ", display_phone_number)
        print("The recipient phone number is ",recipient_phone_number)
        print("The status is ",status)
        print("The timestamp is ",timestamp)

        return "Success", 200

def send_to_whatsapp_api(payload):
    token = os.environ.get("WHATSAPP_BEARER_TOKEN")
    url = os.environ.get("WHATSAPP_API_URL")
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    requests.post(url, headers=headers, json=payload)

def handler(event, context):
    try:
        return aws_lambda_wsgi.response(app, event, context)
    finally:
        global browser_instance, pw_instance
        if browser_instance:
            browser_instance.close()
        if pw_instance:
            pw_instance.stop()

if __name__ == "__main__":
    app.run()