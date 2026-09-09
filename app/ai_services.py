import os
import json
from sentence_transformers import SentenceTransformer
import google.generativeai as genai
from config import Config
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

# Load embedding model
# We use all-MiniLM-L6-v2 as it is small and fast
embedding_model = SentenceTransformer('all-MiniLM-L6-v2')

if Config.GEMINI_API_KEY:
    genai.configure(api_key=Config.GEMINI_API_KEY)

def generate_embedding(text):
    """Generate a vector embedding for a given text."""
    if not text:
        return np.zeros(384).tolist()  # all-MiniLM-L6-v2 dimension is 384
    
    # model.encode returns a numpy array, we convert to list for database storage (JSON/Text)
    vector = embedding_model.encode(text)
    return vector.tolist()

def generate_user_profile_vector(skills):
    """
    Given a list of skill names, generate embeddings for each,
    and return the average pooling of all skill embeddings.
    """
    if not skills:
        return np.zeros(384).tolist()
    
    vectors = [embedding_model.encode(skill) for skill in skills]
    # Average pooling
    avg_vector = np.mean(vectors, axis=0)
    return avg_vector.tolist()

def compute_similarity(user_vector, course_vector):
    """Compute cosine similarity between two vectors."""
    # scikit-learn expects 2D arrays: [ [v1], [v2], ... ]
    u_vec = np.array(user_vector).reshape(1, -1)
    c_vec = np.array(course_vector).reshape(1, -1)
    return float(cosine_similarity(u_vec, c_vec)[0][0])

def extract_skills_with_llm(user_text):
    """
    Use LLM to extract a list of structured skills from free-form text.
    """
    if not Config.GEMINI_API_KEY:
        return []
    
    try:
        model = genai.GenerativeModel("gemini-flash-latest")
        prompt = f"""
        Extract professional skills from the following user input.
        Return ONLY a JSON array of strings, where each string is a skill (e.g. ["Python", "Backend Development", "Machine Learning"]).
        Do not return any markdown formatting or explanation, just the raw JSON array.
        
        User input: "{user_text}"
        """
        response = model.generate_content(prompt)
        text = response.text.strip()
        # Clean markdown if model still returned it
        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        
        skills = json.loads(text.strip())
        return skills
    except Exception as e:
        print(f"Error extracting skills: {e}")
        return []

def generate_recommendation_explanation(user_skills, course_title, course_description):
    """
    Use LLM to explain why a course is recommended based on user skills.
    """
    if not Config.GEMINI_API_KEY:
        return "This course matches your profile."
        
    try:
        model = genai.GenerativeModel("gemini-flash-latest")
        prompt = f"""
        You are a career advisor. 
        The user has the following skills/interests: {', '.join(user_skills)}.
        You are recommending the course "{course_title}" (Description: {course_description}).
        Provide a very short (1-2 sentences) explanation of why this course is a great match for their skills and goals.
        """
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        print(f"Error generating explanation: {e}")
        return "This course matches your profile."
