from linkedin_api import Linkedin, client, cookie_repository
import os
import shutil
from flask import Flask, request
import aws_lambda_wsgi
import boto3
import json
import time

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

    os.makedirs(TMP_DIR, exist_ok=True)

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
        print("POST request made to webhook endpoint")
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