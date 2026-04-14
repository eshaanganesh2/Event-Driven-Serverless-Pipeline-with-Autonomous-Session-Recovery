# Event-Driven LinkedIn-to-WhatsApp Automation with Autonomous CAPTCHA Resolution

A serverless system engineered to operate within Meta's strict webhook constraints, featuring a decoupled worker architecture, autonomous multi-stage CAPTCHA resolution, and human-in-the-loop MFA via real-time DynamoDB polling

## Overview & Project Evolution
This project started with a simple observation: some of the most valuable content I encountered was on LinkedIn, but a few of my relatives, who primarily communicate on WhatsApp, had no visibility into it. I wanted to bridge that gap. <br><br>
My first attempt was deliberately minimal: a third-party library to extract LinkedIn posts, a cron job to trigger it daily, and Selenium to automate delivery via WhatsApp Web. Scrappy, but it worked (for a while). LinkedIn's bot detection eventually killed the extraction library entirely. The fix was manual: log in from a real device, extract the session cookies, and pass them to the library as an authentication workaround. It worked, but introduced a new fragility, as hardcoded cookies expired unpredictably, requiring manual extraction and redeployment each time. <br> <br>
That maintenance loop, along with the flaky selenium web automation, became the engineering problem I couldn't leave alone. Migrating to AWS gave me a stable webhook URL for the WhatsApp Business Cloud API to replace the Selenium-based delivery and created the foundation for automating the session refresh flow. But AWS IP addresses are heavily scrutinized by LinkedIn's bot detection. Even with valid credentials, every login attempt from Lambda triggered a CAPTCHA or security challenge. That's where the engineering got genuinely interesting. <br><br>
I switched to Playwright for its handling of shadow DOMs and iframe-nested security elements, containerized the runtime to clear Lambda's 250MB deployment limit, and automated the full multi-stage challenge flow: checkbox CAPTCHA via Playwright's auto-waiting, audio challenges via pydub normalization and SpeechRecognition transcription, and PIN-based verification via a human-in-the-loop WhatsApp polling bridge backed by DynamoDB. Meta's strict 2-second webhook SLA made a synchronous solution impossible, which drove the decoupled worker architecture at the core of this system. <br><br>
My family now receives daily LinkedIn posts every morning via WhatsApp, just with considerably more infrastructure than I initially anticipated.

## Key Features

* **Scheduled Execution via EventBridge CRON**: Triggers daily post retrieval and delivery via a managed EventBridge rule, ensuring consistent execution without manual intervention.
* **Multi-Stage CAPTCHA Resolution (reCAPTCHA, audio, PIN)**: Automatically detects and resolves LinkedIn security challenges, including reCAPTCHA checkbox interactions, audio challenge transcription via pydub and SpeechRecognition, and PIN-based verification flows.
* **Asynchronous Worker Handoff for Webhook SLA Compliance**: Decouples heavy browser automation from the webhook handler by immediately returning 200 OK to Meta and asynchronously invoking a dedicated Worker Lambda, preventing timeout violations and duplicate retry loops.
* **Human-in-the-Loop MFA via WhatsApp Polling Bridge**: Routes LinkedIn verification codes through WhatsApp and the Worker polls DynamoDB every 5 seconds until the owner replies with the code, then injects it directly into the live browser session.
* **Persistent Session State via DynamoDB Cookie Reconstruction**: Manually reconstructs and persists LinkedIn session cookies in DynamoDB, enabling stable re-authentication across cold starts and execution environments without re-login.

---

## System Architecture
The system is architected around Meta's strict <250ms webhook response requirement, which necessitates full decoupling of browser automation from the API handler. <br><br>
<img src="https://github.com/eshaanganesh2/Adversarial-LinkedIn-WhatsApp-Orchestrator/blob/main/architecture_diagram.png" width="1024"/>

The project utilizes a **Decoupled Worker Pattern** to stay within the strict timeout limits of the Meta WhatsApp Cloud API.

1. **Orchestrator Lambda (Zip)**: Lightweight trigger that invokes the fetcher.
2. **LinkedIn-to-WhatsApp Lambda (Image)**: The Flask-based API handler that manages the main logic.
3. **Worker Lambda (Image)**: A heavy-duty Playwright environment used for "Fire & Forget" cookie refreshes.
4. **DynamoDB**: Acts as the shared state for session cookies and real-time PIN polling.

---

## The Cookie Refresh Flow

When LinkedIn invalidates a session, the system initiates a **Self-Healing Flow**:

### 1. Detection & Prompt

If the main Lambda hits a `ChallengeException`, it sends a WhatsApp Template message to the owner. Clicking **"Refresh cookies now!"** triggers a Meta Webhook.

### 2. The Worker Hand-off

To prevent Webhook timeouts (Meta requires a `< 2s` response), the API returns a `200 OK` immediately and invokes the **Worker Lambda** asynchronously.

### 3. Automated Browser Session

The Worker launches a **Headless Playwright** instance:

* **Identity**: Auto-fills credentials and manages session state.
* **Recaptcha**: Automates checkbox interactions.
* **Bot Challenge**: Downloads audio challenges  converts to `.wav`  transcribes to text  submits.

### 4. Real-time PIN Polling

If LinkedIn asks for a verification code:

* The Worker sends a WhatsApp request to the owner.
* It enters a **Polling Loop**, checking DynamoDB every 5 seconds (up to 5 mins).
* The owner replies via WhatsApp: `verification code=<XXXXXX>`.
* A webhook inserts this code into DynamoDB, the Worker picks it up, and completes the login.

---

## Engineering Decisions & System Design

### 1. Advanced Browser Automation: Playwright vs. Selenium

The transition to **Playwright** was driven by the necessity to navigate LinkedIn’s **shadow DOMs** and **iframe-nested security elements**. Unlike Selenium, Playwright’s **Auto-waiting** mechanism and **Modern Selector Engine** (utilizing CSS and XPath engines) eliminated race conditions and "element not found" errors common in headless AWS environments. This choice provided the granular control required to intercept network requests and solve complex multi-stage bot challenges.

### 2. Containerization (Docker) & AWS ECR Integration

To overcome the 250MB size constraint of standard AWS Lambda Zip deployments, the system utilizes **Docker images** hosted on **Amazon ECR**. This was critical for three reasons:

* **Binary Packaging**: Consolidates heavy binaries (Chromium, FFmpeg, Playwright) that total ~1GB.
* **System-Level Control**: Allows for explicit `dnf` installations of Linux graphics and audio libraries required for browser rendering.
* **Immutable Environments**: Ensures the local development environment and the AWS Lambda runtime are bit-for-bit identical, eliminating "it works on my machine" errors.

### 3. Decoupled Worker Pattern for Webhook Reliability

A major architectural challenge was the **Meta Webhook 2-second timeout**. Because the cookie refresh flow involves heavy browser automation and human-in-the-loop MFA polling (taking 1–2 minutes), a synchronous response was impossible.

* **The Solution**: I implemented an **Asynchronous Hand-off** to a dedicated **Worker Lambda**.
* **The Impact**: The Main Lambda acknowledges the Meta webhook immediately (200 OK), while the Worker executes the "heavy lifting" in the background. This prevents Meta from triggering retry loops and protects the system from duplicate login attempts.

---

## Technical Stack

### 1. **Cloud Infrastructure & DevOps**

* **AWS Lambda**: Serverless compute utilizing both **Zip-based** (Orchestrator) and **Container Image-based** (Worker/API) deployments.
* **AWS SAM (Serverless Application Model)**: Infrastructure as Code (IaC) for reproducible deployments.
* **Amazon ECR**: Container registry for managing high-dependency Docker images (Playwright, Chrome, FFmpeg).
* **Amazon DynamoDB**: NoSQL state management for persistent session cookies and real-time MFA polling.
* **Amazon EventBridge**: Managed CRON scheduling for daily execution.
* **API Gateway**: RESTful interface for Meta Webhook integration.

### 2. **Automation & Browser Engineering**

* **Playwright (Python)**: Advanced browser automation for navigating complex single-page applications and solving multi-layered security challenges.
* **Headless Chrome**: Pinned "Chrome for Testing" version to ensure consistent automation behavior in headless environments.
* **FFmpeg**: Static binary integration for media processing during bot challenges.

### 3. **AI & Signal Processing**

* **SpeechRecognition**: Python-based speech-to-text conversion used to programmatically bypass audio-based bot detection.
* **Pydub**: Audio manipulation used to normalize and convert LinkedIn's audio challenges for the transcription engine.

### 4. **Backend & Integration**

* **Python 3.12**: Core logic and asynchronous worker management.
* **Flask**: Lightweight web framework for handling incoming WhatsApp webhooks.
* **WhatsApp Cloud API (Graph API)**: Real-time messaging interface for post delivery and user interaction.
* **Boto3**: AWS SDK for Python for seamless interaction with DynamoDB and Lambda invocation.

---

