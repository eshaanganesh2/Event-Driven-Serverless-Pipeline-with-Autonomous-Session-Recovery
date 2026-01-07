import os
import time
import random
import urllib.request
import pydub
import speech_recognition
import ssl
from DrissionPage import ChromiumPage
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

class RecaptchaSolver:
    """A stealthy reCAPTCHA solver with improved race-condition handling."""

    TEMP_DIR = os.getenv("TEMP") if os.name == "nt" else "/tmp"
    TIMEOUT_STANDARD = 15 

    def __init__(self, driver: ChromiumPage) -> None:
        self.driver = driver

    def solveCaptcha(self) -> None:
        print("refreshCookies.py -> Searching for LinkedIn Security Wrapper...")
        self.driver.wait.ele_displayed('#captcha-internal', timeout=self.TIMEOUT_STANDARD)
        wrapper = self.driver.get_frame('#captcha-internal')
        
        if not wrapper:
            raise Exception("Could not find the LinkedIn Security Wrapper.")

        print("refreshCookies.py -> Waiting for Google reCAPTCHA frame...")
        anchor_locator = 'xpath://iframe[contains(@src, "api2/anchor") or contains(@title, "reCAPTCHA")]'
        wrapper.wait.ele_displayed(anchor_locator, timeout=self.TIMEOUT_STANDARD)
        anchor_frame = wrapper.get_frame(anchor_locator)
        
        time.sleep(random.uniform(1.5, 3.0))
        print("refreshCookies.py -> Checkpoint: Clicking Checkbox")
        
        anchor_frame.actions.move_to('#recaptcha-anchor', 
                                    offset_x=random.randint(-10, 10), 
                                    offset_y=random.randint(-10, 10)).click()
        
        time.sleep(random.uniform(2, 3.5))

        if self.is_solved(anchor_frame):
            print("Solved by checkbox click!")
            return

        print("refreshCookies.py -> Locating Challenge Frame...")
        challenge_locator = 'xpath://iframe[contains(@src, "api2/bframe") or contains(@title, "challenge")]'
        wrapper.wait.ele_displayed(challenge_locator, timeout=10)
        challenge_frame = wrapper.get_frame(challenge_locator)

        if not challenge_frame:
            raise Exception("Challenge frame (bframe) not found.")

        print("refreshCookies.py -> Checkpoint: Clicking Audio Button")
        challenge_frame.wait.ele_displayed("#recaptcha-audio-button", timeout=5)
        time.sleep(random.uniform(0.8, 1.8))
        
        challenge_frame.actions.move_to("#recaptcha-audio-button").click()
        
        self.solve_audio_flow(challenge_frame, anchor_frame)

    def solve_audio_flow(self, challenge_frame, anchor_frame, attempts=0) -> None:
        if attempts > 3:
            raise Exception("Too many attempts. Blocked by Google.")

        if self.is_detected(challenge_frame):
            raise Exception("reCAPTCHA blocked us: 'Try again later' detected.")

        time.sleep(random.uniform(2.0, 4.0))
        print(f"refreshCookies.py -> Attempt {attempts + 1}: Extracting Audio URL")
        challenge_frame.wait.ele_displayed("#audio-source", timeout=self.TIMEOUT_STANDARD)
        audio_url = challenge_frame.ele("#audio-source").link
        
        try:
            text_response = self._process_audio_challenge(audio_url)
            print(f"refreshCookies.py -> Recognized Text: {text_response}")
            
            time.sleep(random.uniform(3.0, 6.0))
            
            response_input = challenge_frame.ele("#audio-response")
            response_input.click() 
            
            for char in text_response.lower():
                response_input.input(char)
                time.sleep(random.uniform(0.1, 0.3)) 
            
            time.sleep(random.uniform(1.5, 3.0))
            challenge_frame.actions.move_to("#recaptcha-verify-button").click()
            
            # --- Race condition fix start ---
            print("refreshCookies.py -> Verification submitted. Waiting for state change...")
            time.sleep(3)
            
            solved = False
            for i in range(3):  # Check 5 times over 5 seconds
                if self.is_solved(anchor_frame):
                    solved = True
                    break
                print(f"refreshCookies.py -> Checking solve status... attempt {i+1}")
                time.sleep(1)

            if solved:
                print("refreshCookies.py -> Captcha Solved Successfully!")
                return
            
            # If the audio button is still there, it failed. 
            if not challenge_frame.ele("#audio-source", timeout=1):
                print("Challenge UI disappeared. Assuming successful redirection.")
                return

            print("Response not accepted by Google. Reloading challenge...")
            reload_btn = challenge_frame.ele("#recaptcha-reload-button")
            if reload_btn:
                challenge_frame.actions.move_to("#recaptcha-reload-button").click()
                time.sleep(2)
            return self.solve_audio_flow(challenge_frame, anchor_frame, attempts + 1)

        except Exception as e:
            raise Exception(f"Audio flow error: {str(e)}")

    def _process_audio_challenge(self, audio_url: str) -> str:
        uid = random.randrange(1, 10000)
        mp3_path = os.path.join(self.TEMP_DIR, f"cap_{uid}.mp3")
        wav_path = os.path.join(self.TEMP_DIR, f"cap_{uid}.wav")
        context = ssl._create_unverified_context()

        try:
            with urllib.request.urlopen(audio_url, context=context) as response, open(mp3_path, 'wb') as out_file:
                out_file.write(response.read())
            
            sound = pydub.AudioSegment.from_mp3(mp3_path)
            sound.export(wav_path, format="wav")

            recognizer = speech_recognition.Recognizer()
            with speech_recognition.AudioFile(wav_path) as source:
                audio = recognizer.record(source)
            
            return recognizer.recognize_google(audio)
        finally:
            for path in (mp3_path, wav_path):
                if os.path.exists(path):
                    try: os.remove(path)
                    except: pass

    def is_solved(self, anchor_frame) -> bool:
        try:
            # Check the aria-checked attribute on the checkbox element
            return anchor_frame.ele('#recaptcha-anchor').attrs.get('aria-checked') == "true"
        except:
            return False

    def is_detected(self, challenge_frame) -> bool:
        try:
            return challenge_frame.ele("text:Try again later", timeout=0.5).states.is_displayed
        except:
            return False


page = ChromiumPage()
solver = RecaptchaSolver(driver=page)

# Set Stealth User Agent
page.set.user_agent('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
page.get('https://linkedin.com/uas/login')

username = os.environ.get('LINKEDIN_EMAIL')
password = os.environ.get('LINKEDIN_PASSWORD')

print("refreshCookies.py -> Filling credentials...")
page.ele('@id:username').input(username, clear=True)
time.sleep(random.uniform(1, 2))

page.actions.key_down('TAB').key_up('TAB')
time.sleep(random.uniform(0.5, 1.5))

for char in password:
    page.actions.type(char)
    time.sleep(random.uniform(0.1, 0.2))

time.sleep(random.uniform(1, 2))
page.actions.key_down('ENTER').key_up('ENTER')

# Wait for navigation away from login
try:
    page.wait.url_change('uas/login', timeout=10)
except:
    pass

time.sleep(5)

# If challenged, solve it
if 'checkpoint' in page.url:
    print("refreshCookies.py -> Challenge detected. Proceeding...")
    try:
        solver.solveCaptcha()
        
        # Give the page time to transition to feed after solving
        page.wait.url_change('checkpoint', timeout=15)
        
        if 'checkpoint' in page.url:
            submit = page.ele('text:Submit', timeout=3)
            if submit: 
                time.sleep(2)
                submit.click()
    except Exception as e:
        print(f"refreshCookies.py -> Solver Error: {e}")

# Verification of Success
if 'feed' in page.url or 'mynetwork' in page.url:
    print("refreshCookies.py -> Logged in successfully!")
else:
    print(f"refreshCookies.py -> Final URL: {page.url} - Check if login was successful.")