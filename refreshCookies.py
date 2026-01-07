import time
import random
from RecaptchaSolver import RecaptchaSolver

class RefreshCookies:
    def login(self, page, username, password):
        print("Playwright -> Filling credentials...")
        
        # Fill username
        page.locator("#username").fill(username)
        time.sleep(random.uniform(0.5, 1.0))
        
        # Fill password and press Enter
        page.locator("#password").fill(password)
        time.sleep(random.uniform(0.5, 1.0))
        page.keyboard.press("Enter")

        # Wait to see if we hit a challenge
        page.wait_for_timeout(5000)

        if "checkpoint" in page.url:
            print("Challenge detected. Solving...")
            try:
                solver = RecaptchaSolver(page)
                solver.solveCaptcha()
                print("Challenge solved")
                time.sleep(10)
                page.screenshot(path="/tmp/success_screen_capture.png")
                import base64
                with open("/tmp/success_screen_capture.png", "rb") as image_file:
                    print("SCREENSHOT_SUCCESS " + base64.b64encode(image_file.read()).decode('utf-8'))
            except Exception as e:
                print(f"Captcha error: {e}")

    def is_pin_verification_page(self, page):
        # Check if the PIN input is visible
        return page.locator("#input__email_verification_pin").is_visible(timeout=3000)

    def verify_pin(self, page, verification_code):
        try:
            print(f"[{time.strftime('%H:%M:%S')}] Entering PIN: {verification_code}")
            
            # Locate the input
            pin_input = page.locator("#input__email_verification_pin")
            pin_input.wait_for(state="visible", timeout=10000)
            
            # Human touch: Hover and Click to focus
            pin_input.hover()
            time.sleep(random.uniform(0.4, 0.8))
            pin_input.click()
            
            # Human touch: Realistic typing with variable delays
            for i, char in enumerate(str(verification_code)):
                pin_input.type(char, delay=random.randint(150, 450))
                
                # Simulate a brief pause halfway through for more human-like simulation
                if i == 2: 
                    time.sleep(random.uniform(0.6, 1.2))
            
            # Delay before clicking submit
            time.sleep(random.uniform(1.0, 2.2))
            
            submit_btn = page.locator("#email-pin-submit-button")
            submit_btn.hover()
            time.sleep(random.uniform(0.2, 0.5))
            submit_btn.click()
            
            print("PIN submitted.")
            
            # Wait for navigation or success state
            page.wait_for_load_state("networkidle")
            
        except Exception as e:
            print(f"PIN error: {e}")
            page.screenshot(path="pin_entry_error.png")