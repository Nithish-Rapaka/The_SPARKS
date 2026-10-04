# Quick Start

LinkedIn Post Studio generates a draft, lets you edit it, and publishes only after you confirm.

## Demo Login

- Username: `linkedin`
- Password: `LinkedIn#2026!`

These credentials are hardcoded for local demonstration only. Do not deploy this authentication setup to a public environment.

## Requirements

- Python 3.10 or newer
- Node.js and npm
- An OpenAI API key or OpenRouter API key
- A LinkedIn app configured for OAuth with the `w_member_social` scope

## Configure

Create a root `.env` file with:

```dotenv
OPENAI_API_KEY=your_openai_or_openrouter_key
LINKEDIN_CLIENT_ID=your_linkedin_client_id
LINKEDIN_CLIENT_SECRET=your_linkedin_client_secret
LINKEDIN_REDIRECT_URI=http://127.0.0.1:8000/link/linkedin/callback/
FRONTEND_URL=http://localhost:3000
MONGODB_URI=mongodb+srv://your-user:your-password@your-cluster/
MONGODB_DATABASE=your-database
```

For the LinkedIn app, add the exact redirect URI above to its OAuth settings. The callback saves its access token in `automation/linkedin_tokens.json`.
Allow the machine running Django in your MongoDB provider's network access settings. After each successful publication, the app saves the prompt, post text, optional image URL, and publication time to the `linkedin_posts` collection in `MONGODB_DATABASE`. The dashboard displays the latest 50 saved posts.

## Run

In the repository root:

```powershell
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver 127.0.0.1:8000
```

In another terminal:

```powershell
cd frontend
npm install
npm run dev
```

Open the Vite URL printed in the terminal, sign in with the demo credentials, connect LinkedIn, generate a draft, review it, and publish.

The login uses an eight-hour Django server session. Sign out clears that session. The dashboard and its LinkedIn API endpoints require the session.
