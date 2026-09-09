import sys
import os
import json

# Add parent directory to path to allow importing app modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select, insert
from app.db import engine
from app.models import courses, course_vectors
from app.ai_services import generate_embedding

def populate_course_embeddings():
    print("Fetching courses from database...")
    with engine.connect() as conn:
        all_courses = conn.execute(select(courses)).fetchall()
        
        print(f"Found {len(all_courses)} courses. Generating embeddings...")
        
        for idx, course in enumerate(all_courses):
            print(f"Processing ({idx+1}/{len(all_courses)}): {course.title}")
            
            # Combine text fields for a rich representation
            course_text = f"Title: {course.title}\nDescription: {course.description or ''}\nSkills required: {course.skill_requirements or ''}"
            
            # Generate embedding
            vector = generate_embedding(course_text)
            
            # Check if vector already exists for course
            existing = conn.execute(select(course_vectors).where(course_vectors.c.course_id == course.id)).fetchone()
            
            if existing:
                # Update (using basic delete + insert for simplicity in SQLAlchemy Core)
                conn.execute(course_vectors.delete().where(course_vectors.c.course_id == course.id))
                
            # Insert new vector
            conn.execute(
                insert(course_vectors).values(
                    course_id=course.id,
                    embedding_vector=json.dumps(vector)  # Store as JSON string in Text column
                )
            )
            
        conn.commit()
        print("Successfully generated and saved embeddings for all courses.")

if __name__ == "__main__":
    populate_course_embeddings()
