# LinkedIn to WhatsApp Daily Notifier 📲

This project fetches the latest LinkedIn post from a specified profile and sends it as a WhatsApp message to one or more contacts **every day at 11:30 AM**. The backend is built using Python, Flask, and AWS Lambda with SAM for serverless deployment.

---

## 🚀 Features

- ✅ Flask-based API to retrieve latest LinkedIn post using `linkedin-api`
- ✅ Sends formatted WhatsApp message using Meta's WhatsApp Cloud API
- ✅ Scheduled execution every day at 11:30 AM Kuwait time via EventBridge
- ✅ Serverless deployment via AWS SAM
- ✅ Environment-driven configuration for credentials and contacts
- ✅ Modular structure with layered Lambda support for Python dependencies

---

## 📦 Tech Stack

- **Backend**: Python 3.12, Flask
- **Deployment**: AWS Lambda + API Gateway via AWS SAM
- **Scheduling**: EventBridge cron jobs
- **WhatsApp Messaging**: WhatsApp Cloud API (Meta Graph API)
- **Authentication**: OAuth Bearer Token for WhatsApp
- **Others**: AWS Lambda Layers, Requests, LinkedIn API (unofficial)

---

## 🧭 Architecture Overview

```

┌──────────────┐
│ LinkedIn API │
└──────┬───────┘
│
▼
┌─────────────────────┐    Scheduled (Daily @ 11:30 AM)
│ Orchestrator Lambda ├────────────────────────────────────┐
└──────┬──────────────┘                                    │
│ calls Flask API                                   │
▼                                                   ▼
┌──────────────────────┐                        ┌────────────────────────┐
│ Flask API (Lambda)   │   returns post text →  │ WhatsApp Cloud API     │
│ /getLatestPost       │                        │ Sends message to users │
└──────────────────────┘                        └────────────────────────┘

````

---

## ⚙️ Setup Instructions

### 1. Clone the repo and install AWS SAM CLI

```bash
git clone <repo-url>
cd linkedin-to-whatsapp
````

### 2. Install dependencies into a Lambda Layer

Create a `requirements.txt`:

```txt
linkedin-api
requests
flask
```

Install into a layer:

```bash
mkdir -p python
pip install -r requirements.txt -t python
zip -r dependencies-layer.zip python/
```

### 3. Define environment variables

Edit `template.yaml`:

```yaml
Environment:
  Variables:
    WHATSAPP_BEARER_TOKEN: <your-token>
    RECIPIENT_PHONE: "[<recipeient-list>]"
    LINKEDIN_EMAIL: <your-email>
    LINKEDIN_PASSWORD: <your-password>
    URN_ID: <linkedin-profile-urn>
```

> Replace with real values or use AWS Secrets Manager later.

---

## 🚀 Deployment (SAM)

```bash
sam build
sam deploy --guided
```

Follow prompts to set:

* Stack name
* AWS region
* IAM roles
* S3 bucket for deployment artifacts

---

## 📂 Folder Structure

```
├── LinkedIn_to_WhatsApp.py     # Flask-based API handler
├── orchestrator.py             # Scheduled Lambda logic
├── template.yaml               # AWS SAM template
├── cookies.jr                  # Pickled cookies for LinkedIn login
├── dependencies-layer.zip      # Layer with Flask/requests/etc.
```

---

## 🔁 How It Works

### /getLatestPost (Flask API)

* Uses saved cookies and credentials to fetch the most recent LinkedIn post
* Exposed via API Gateway using `{proxy+}` route

### Orchestrator Lambda

* Scheduled via EventBridge (`cron(30 8 * * ? *)` → 11:30 AM UTC+3)
* Calls `/getLatestPost`, parses response
* Sends WhatsApp message to defined recipient using Graph API

---

## 🙏 Acknowledgments

* [linkedin-api](https://github.com/tomquirk/linkedin-api)
* [Meta WhatsApp Cloud API Docs](https://developers.facebook.com/docs/whatsapp)
* [AWS SAM](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/what-is-sam.html)

---
