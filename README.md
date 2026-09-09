# Skills Utilization - AI Course Recommendation Platform

## Description
**Skills Utilization** is a web-based educational platform designed to help users track their professional skills and discover relevant courses. 
The application has recently been upgraded with an advanced **AI Recommendation Engine**. It uses machine learning vector embeddings (Semantic Search) to deeply understand the meaning of course descriptions, and Google's Gemini Large Language Model (LLM) to intelligently extract skills from user input and provide highly personalized course advice.

## Key Features
- **User Authentication:** Secure JWT-based registration and login system with encrypted passwords.
- **AI Skill Extraction:** Users can describe their career goals in natural language, and an LLM Agent will automatically extract structured skills to build their profile.
- **Semantic Course Recommendations:** Instead of simple keyword matching, the engine converts user profiles and courses into Vector Embeddings, using Cosine Similarity to find perfect semantic matches.
- **Personalized AI Explanations:** The system uses Generative AI to dynamically write a personalized explanation of *why* a recommended course fits the user's specific skill set.
- **Course Management:** Users can search the catalog, filter by category, enroll/unenroll in specific classes, and bookmark favorites.

## Technologies Used
- **Backend:** Python 3, Flask REST API
- **AI & Machine Learning:** `sentence-transformers` (all-MiniLM-L6-v2) for embeddings, `scikit-learn` for vector math, `google-generativeai` (Gemini API) for LLM agents.
- **Database:** PostgreSQL
- **ORM & Migrations:** SQLAlchemy Core, Alembic
- **Frontend:** HTML, CSS, JavaScript (served via Flask templates/static folders)

## Project Structure
- `app.py`: The entry point script to run the Flask application.
- `app/ai_services.py`: Core AI logic for vector generation, semantic math, and Gemini LLM interactions.
- `app/models.py`: SQLAlchemy Core table definitions, including the `course_vectors` table for storing AI embeddings.
- `app/routes_auth.py` & `app/routes_courses.py`: API endpoints for auth, profile management, semantic search recommendations, and AI endpoints.
- `seed_courses.py` & `courses.json`: Script and dataset for seeding initial courses and skills.
- `generate_embeddings.py`: AI utility script that reads course descriptions and mathematically encodes them into vector embeddings in the database.
- `config.py`: Environment variable configurations and secret keys.

## Setup Instructions

### Prerequisites
- Python 3.8+
- PostgreSQL installed and running locally
- Google Gemini API Key (Get one for free at [Google AI Studio](https://aistudio.google.com/app/apikey))

### 1. Database Configuration
Ensure PostgreSQL is running and create the necessary database (default is `course_recommendation_db`):
```sql
CREATE DATABASE course_recommendation_db;
```

### 2. Environment & AI Setup
Navigate to the root directory and set up a Python virtual environment:
```bash
# Clone or navigate to the project directory
cd Skills_Utilization

# Create a virtual environment
python -m venv venv

# Activate the virtual environment
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# Install the required Python packages
pip install -r requirements.txt
```

Create a **`.env`** file in the root directory and add your AI key:
```env
GEMINI_API_KEY=your_google_gemini_api_key_here
```

### 3. Run Database Migrations
Use Alembic to create the database schema:
```bash
alembic upgrade head
```

### 4. Seed Data & Generate AI Embeddings
First, populate the database with the initial catalog of courses:
```bash
python seed_courses.py
```
Next, run the AI embeddings script to generate vector representations of every course so semantic search works:
```bash
python generate_embeddings.py
```

### 5. Start the Application
Run the Flask server:
```bash
python app.py
```
The application will start locally and be available at `http://127.0.0.1:5000`.