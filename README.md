# strength_training_log
This guide explains how to run and deploy your new modular FastAPI app.

Your new project structure is:

main.py (The app runner)

app/ (A folder with all your backend logic)

frontend/ (Your PWA)

requirements.txt

schema.sql

How to Run Locally

Create a Virtual Environment:

python -m venv venv


Activate It:

macOS/Linux: source venv/bin/activate

Windows: venv\Scripts\activate

Install Libraries:

pip install -r requirements.txt


Set Your Gemini API Key:

macOS/Linux:

export GEMINI_API_KEY='YOUR_KEY_HERE'


Windows (PowerShell):

$env:GEMINI_API_KEY='YOUR_KEY_HERE'


Run the App (One Command):

python main.py


Open Your Browser:

Go to https://www.google.com/search?q=http://127.0.0.1:5000

You can also see your auto-generated API docs at https://www.google.com/search?q=http://127.0.0.1:5000/docs

How to Deploy to Render

This structure is even better for Render.

Push to GitHub: Make sure your new structure (main.py, app/ folder, etc.) is on GitHub.

Create Database: Create a PostgreSQL database on Render and copy the "Internal Database URL".

Create Web Service:

Select your GitHub repo.

Build Command:

pip install -r requirements.txt


Start Command:

uvicorn main:app --host 0.0.0.0 --port $PORT


(Note: We use uvicorn here, not gunicorn or flask)

Add Environment Variables:

Key: DATABASE_URL

Value: Paste the "Internal Database URL".

Key: GEMINI_API_KEY

Value: Paste your Google AI Studio API key.

Deploy!

Click "Create Web Service".

Initialize the Database (First-Time Only):

After the first build, go to the "Shell" tab for your service.

Run this command to create your tables:

python -c "from app.db import init_db; init_db()"


Go to "Events" and trigger a new deploy to restart your app with the initialized database.

This is a much cleaner and more professional way to organize your code!