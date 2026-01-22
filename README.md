# Self-Healing Serverless Automation for Adversarial Web Platforms: A LinkedIn–WhatsApp Pipeline

A production-grade serverless system that automatically fetches LinkedIn posts and delivers them to WhatsApp, designed to survive captchas, MFA, session invalidation, and strict webhook timeouts through a self-healing, event-driven architecture.

## Key Features

* **Automated Daily Fetch**: Delivers the latest post every day via EventBridge CRON.
* **Intelligent Challenge Solving**: Automatically detects LinkedIn security hurdles (Recaptcha, Bot Challenges, PINs).
* **Audio Captcha Solver**: Uses `pydub` and Speech-to-Text (`SpeechRecognition`) to bypass bot detection.
* **WhatsApp-to-Browser Bridge**: Submit LinkedIn verification codes directly via a WhatsApp chat.
* **Serverless Persistence**: Session cookies are manually reconstructed and stored in **DynamoDB** to ensure long-term stability across different execution environments.

---

## System Architecture

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

## Engineering Rationale & System Design

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

