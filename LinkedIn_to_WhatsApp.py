from linkedin_api import Linkedin
import schedule
import os
import time
import requests
from dotenv import load_dotenv
import webbrowser
from pyautogui import press
from urllib.parse import quote

load_dotenv()

# Obtaining all .env variables
username = os.getenv('LINKEDIN_EMAIL')
password = os.getenv('LINKEDIN_PASSWORD')
phone_number = os.getenv("PHONE_NUMBER")
urnId = os.getenv('URN_ID')

# Authenticate using Linkedin user account credentials
api = Linkedin(username, password)

# GET a profile
#posts = api.get_profile_posts(urn_id="",post_count=3)
# posts = api.get_profile_posts(public_id='')

# Obtaining the latest linkedIn post
post = api.get_profile_posts(urn_id=urnId,post_count=1)[0]

# Reading content stored in txt file to compare with latest post 
f = open("prev_post.txt","r")

# Extracting post content
post_content = post["commentary"]["text"]["text"]

# Formatting the content
#formatted_post_content = post_content.replace("\n","%0a")
formatted_post_content = quote(post_content)

# If the latest post is different from the previously shared post
if f.read()!=formatted_post_content:
    print(formatted_post_content)
    # Write the content to the txt file
    with open("prev_post.txt", "w") as f:
        f.write(formatted_post_content)

    # Calling the WhatsApp SEND message API
    webbrowser.open("https://api.whatsapp.com/send?phone="+phone_number+"&text="+formatted_post_content)
    time.sleep(10)
    press("enter")
    time.sleep(10)
    press("enter")


# schedule.every().day.at("17:15").do(job)

# while True:
 
#     # Checks whether a scheduled task 
#     # is pending to run or not
#     schedule.run_pending()
#     time.sleep(1)


    
