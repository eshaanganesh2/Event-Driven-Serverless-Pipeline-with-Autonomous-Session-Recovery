from linkedin_api import Linkedin
import os
from flask import Flask, request
import pickle
import aws_lambda_wsgi

app = Flask(__name__)

@app.route("/getLatestPost")
def get_latest_post():
    print("Retrieving latest linkedIn post")

    # Obtaining all .env variables
    username = os.environ.get('LINKEDIN_EMAIL')
    password = os.environ.get('LINKEDIN_PASSWORD')
    urnId = os.environ.get('URN_ID')

    print("The username is",username)

    cookies = getCookies()

    # Authenticate using Linkedin user account credentials
    api = Linkedin(username = username, password = password, cookies = cookies)

    # Obtaining the latest linkedIn post
    post = api.get_profile_posts(urn_id=urnId,post_count=1)[0]

    # Extracting post content
    post_content = post["commentary"]["text"]["text"]

    print(post_content)

    return post_content

@app.route("/helloWorld")
def print_hello_world():
    print("Hello World")
    return "Hello World"

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
        print("Logging events")
        data=request.get_json()
        if data:
            display_phone_number = data.get('entry')[0].get('changes')[0].get('value').get('metadata').get('display_phone_number')
            recipient_phone_number = data.get('entry')[0].get('changes')[0].get('value').get('statuses')[0].get('recipient_id')
            status = data.get('entry')[0].get('changes')[0].get('value').get('statuses')[0].get('status')
            timestamp = data.get('entry')[0].get('changes')[0].get('value').get('statuses')[0].get('timestamp')

            # from_number = data.get('entry')[0].get('changes')[0].get('value').get('messages')[0].get('from')
            # timestamp = data.get('entry')[0].get('changes')[0].get('value').get('messages')[0].get('timestamp')
            # type = data.get('entry')[0].get('changes')[0].get('value').get('messages')[0].get('type')
            # text = data.get('entry')[0].get('changes')[0].get('value').get('messages')[0].get('text').get('body')
        
            print("The sender phone number is ", display_phone_number)
            print("The recipient phone number is ",recipient_phone_number)
            print("The status is ",status)
            print("The timestamp is ",timestamp)
            # print("The from number is ",from_number)
            # print("The timestamp is ",timestamp)
            print("The webhook is ",data)
            # print("The type is ",type)
            # print("The text is ",text)

        return "Success", 200


def getCookies():
    with open("cookies.jr", "rb") as f:
        cookies = pickle.load(f)
        return cookies

def handler(event, context):
    print("LinkedIn_to_Whatsapp_handler")
    return aws_lambda_wsgi.response(app, event, context)

if __name__ == "__main__":
    app.run()
