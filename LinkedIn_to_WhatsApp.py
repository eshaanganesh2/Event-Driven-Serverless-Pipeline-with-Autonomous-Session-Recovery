from linkedin_api import Linkedin, client, cookie_repository
import os
import shutil
from flask import Flask, request
import aws_lambda_wsgi
import boto3
import json
import time
import pickle
from boto3.dynamodb.types import Binary

app = Flask(__name__)
lambda_client = boto3.client('lambda')

# Global variable to hold the browser for cleanup
browser_instance = None
pw_instance = None

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(os.environ.get('PIN_TABLE_NAME', 'PinStoreTable'))

def getLinkedinInstance(username, password, TMP_DIR):
    return Linkedin(username = username, password = password, cookies_dir=TMP_DIR)

def clear_cookies_jr(TMP_DIR):
   for name in os.listdir(TMP_DIR):
    path = os.path.join(TMP_DIR, name)
    if os.path.isfile(path) or os.path.islink(path):
        os.unlink(path)          
    elif os.path.isdir(path):
        shutil.rmtree(path)

def move_bundled_cookies(username, TMP_DIR):
    # 1. Path where the file exists in your Docker image
    bundled_path = os.path.join(os.environ['LAMBDA_TASK_ROOT'], 'tmp', f"{username}.jr")
    print("The bundled path is",bundled_path)
    
    # 2. Path where the library wants to use it (/tmp/)
    runtime_path = os.path.join(TMP_DIR, f"{username}.jr")
    
    # 3. Only copy if it's not already there (prevents redundant work on warm starts)
    if not os.path.exists(runtime_path):
        if os.path.exists(bundled_path):
            shutil.copy(bundled_path, runtime_path)
            print(f"Successfully moved bundled cookies to {runtime_path}")
        else:
            print(f"CRITICAL: Bundled file not found at {bundled_path}")
    else:
        print(f"Cookies file already exists at {TMP_DIR}")
    
def sync_cookies_from_db(username, TMP_DIR):
    print("Checking DynamoDB for cookies and writing them to /tmp if found")
    cookie_path = os.path.join(TMP_DIR, f"{username}.jr")
    try:
        response = table.get_item(Key={'owner': os.environ.get('OWNER')})
        if 'Item' in response and 'linkedin_cookies' in response['Item']:
            # DynamoDB binary data is wrapped in a Binary object in Boto3
            cookie_bytes = response['Item']['linkedin_cookies'].value
            with open(cookie_path, "wb") as f:
                f.write(cookie_bytes)
            print(f"Restored cookies from DynamoDB to {cookie_path}")

            #####################################################################
            # Code block for printing how much longer cookies are valid for
            with open(cookie_path, "rb") as f:
                jar = pickle.load(f)
                
            now = int(time.time())
            for cookie in jar:
                if cookie.name == 'li_at':
                    # cookie.expires is a Unix timestamp
                    if cookie.expires and cookie.expires > now:
                        remaining = (cookie.expires - now) / 86400
                        print(f"Verified: {cookie.name} is valid for {remaining:.2f} more days.")
                        return True
                    else:
                        print(f"Warning: {cookie.name} has expired!")
                        print("cookie expired on ",cookie.expires)
            #####################################################################
            return True
    except Exception as e:
        print(f"No cookies in DB or error: {e}")
    return False

def clear_verification_pin_from_db():
    print("Clearing the PIN from DynamoDB to prevent reuse")
    try:
        table.update_item(
            Key={'owner': os.environ.get('OWNER')},
            UpdateExpression="REMOVE pin",
            # We add a condition to ensure we only try to remove it if it exists
            ConditionExpression="attribute_exists(pin)"
        )
        print("PIN successfully cleared.")
    except dynamodb.meta.client.exceptions.ConditionalCheckFailedException:
        print("PIN attribute did not exist; nothing to clear.")
    except Exception as e:
        print(f"Error clearing PIN: {e}")

def save_cookies_to_db(username, TMP_DIR):
    print("Reading the local .jr file and saving it to DynamoDB")
    cookie_path = os.path.join(TMP_DIR, f"{username}.jr")
    if os.path.exists(cookie_path):
        with open(cookie_path, "rb") as f:
            cookie_bytes = f.read()
            table.update_item(
                Key={'owner': os.environ.get('OWNER')},
                UpdateExpression="SET linkedin_cookies = :c",
                ExpressionAttributeValues={':c': Binary(cookie_bytes)}
            )
        print("Cookies synced to DynamoDB")

@app.route("/helloWorld")
def print_hello_world():
    print("Hello World")
    return "Hello World"

@app.route("/getLatestPost")
def get_latest_post():
    print("Retrieving latest linkedIn post")

    username = os.environ.get('LINKEDIN_EMAIL')
    password = os.environ.get('LINKEDIN_PASSWORD')
    urnId = os.environ.get('URN_ID')

    print("The username is",username)

    TMP_DIR = os.environ.get("COOKIES_TMP_DIR", "./tmp/")  # local fallback

    clear_verification_pin_from_db()

    os.makedirs(TMP_DIR, exist_ok=True)
    cookie_path = os.path.join(TMP_DIR, f"{username}.jr")
    if not sync_cookies_from_db(username, TMP_DIR) and not os.path.exists(cookie_path):
        move_bundled_cookies(username, TMP_DIR)
    else:
        print("Using existing cookies from DynamoDB/tmp dir")

    api={}
    try:
        api=getLinkedinInstance(username,password,TMP_DIR)
        print("api instance ",api)
    except client.ChallengeException as e:
        print("1. client.ChallengeException: Challenge Exception")
        return {
            "error": "challenge_required",
            "message": str(e)
        }, 403
    # Expired cookies
    except cookie_repository.LinkedinSessionExpired:
        print("cookie_repository.LinkedinSessionExpired: Session expired Exception")
        try:
            clear_cookies_jr(TMP_DIR)
            print("Cookies dir cleared")
            api=getLinkedinInstance(username,password,TMP_DIR)
        # Challenge to be solved
        except client.ChallengeException as e:
            try:
                print("2. client.ChallengeException: Challenge Exception")
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
    
    save_cookies_to_db(username, TMP_DIR)
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
        print("Webhook received")
        data = request.get_json()
        worker_function_name=os.environ.get('WORKER_FUNCTION_NAME')
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

        try:
            body_text = data['entry'][0]['changes'][0]['value']['messages'][0]['text']['body']
            if body_text.startswith("verification code="):
                pin = body_text.split("verification code=")[1].strip()
                # SAVE PIN TO DYNAMODB
                table.put_item(Item={
                    'owner': os.environ.get('OWNER'), # Use a constant or owner phone number
                    'pin': pin,
                    'timestamp': int(time.time())
                })
                print("PIN saved to DynamoDB")
                return "PIN Received", 200
        except:
            pass

        lambda_client.invoke(
            FunctionName= worker_function_name,
            InvocationType='Event', # Fire and forget
            Payload=json.dumps(data)
        )

        print("The sender phone number is ", display_phone_number)
        print("The recipient phone number is ",recipient_phone_number)
        print("The status is ",status)
        print("The timestamp is ",timestamp)

        return "Success", 200

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