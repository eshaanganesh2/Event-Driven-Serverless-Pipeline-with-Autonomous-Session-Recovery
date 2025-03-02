from linkedin_api import Linkedin
import os
from dotenv import load_dotenv
from flask import Flask

load_dotenv()

app = Flask(__name__)

@app.route("/getLatestPost")
def get_latest_post():
    # Obtaining all .env variables
    username = os.getenv('LINKEDIN_EMAIL')
    password = os.getenv('LINKEDIN_PASSWORD')
    urnId = os.getenv('URN_ID')

    # Authenticate using Linkedin user account credentials
    api = Linkedin(username, password)

    # Obtaining the latest linkedIn post
    post = api.get_profile_posts(urn_id=urnId,post_count=1)[0]

    # Extracting post content
    post_content = post["commentary"]["text"]["text"]

    print(post_content)

    return post_content
