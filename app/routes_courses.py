from datetime import datetime
from flask import Blueprint, request, jsonify
from sqlalchemy import select, or_, insert, delete
from app.db import engine
from app.models import courses, skills, user_skills, user_courses, user_favorites
from app.auth import token_required

courses_bp = Blueprint("courses", __name__)

SKILL_CATEGORY_MAP = {
    "frontend": ["html", "css", "javascript", "figma", "ui/ux", "web", "design"],
    "backend": ["python", "node.js", "sql", "postgresql", "database", "api"],
    "hacking": ["cybersecurity", "networking", "ethical hacking", "linux", "security"],
    "cybersecurity": ["cybersecurity", "networking", "ethical hacking", "linux", "security"],
    "ai": ["python", "machine learning", "tensorflow", "deep learning", "ai", "pandas"],
    "design": ["ui/ux", "figma", "prototyping", "design systems", "design"],
    "devops": ["git", "docker", "kubernetes", "ci/cd", "aws", "cloud computing"],
    "mobile": ["mobile dev", "flutter", "dart", "mobile architecture"],
    "database": ["sql", "postgresql", "database design", "database"]
}

@courses_bp.route("/api/courses", methods=["GET"])
def get_courses():
    search = request.args.get("search", "").strip()
    category = request.args.get("category", "").strip().lower()

    with engine.connect() as conn:
        stmt = select(courses)
        if search:
            search_pattern = f"%{search}%"
            stmt = stmt.where(
                or_(
                    courses.c.title.ilike(search_pattern),
                    courses.c.description.ilike(search_pattern),
                    courses.c.instructor.ilike(search_pattern),
                    courses.c.skill_requirements.ilike(search_pattern)
                )
            )

        rows = conn.execute(stmt).fetchall()
        results = []

        for r in rows:
            reqs = (r.skill_requirements or "").lower()

            # Category filter check if requested
            if category and category != "all":
                category_keywords = SKILL_CATEGORY_MAP.get(category, [category])
                if not any(kw in reqs or kw in r.title.lower() for kw in category_keywords):
                    continue

            results.append({
                "id": r.id,
                "title": r.title,
                "description": r.description,
                "instructor": r.instructor,
                "skill_requirements": r.skill_requirements
            })

    return jsonify(results), 200


@courses_bp.route("/api/courses/<course_id>", methods=["GET"])
def get_course_details(course_id):
    with engine.connect() as conn:
        stmt = select(courses).where(courses.c.id == str(course_id))
        r = conn.execute(stmt).fetchone()
        if not r:
            return jsonify({"error": "Course not found"}), 404

        course_info = {
            "id": r.id,
            "title": r.title,
            "description": r.description,
            "instructor": r.instructor,
            "skill_requirements": r.skill_requirements
        }
    return jsonify(course_info), 200


@courses_bp.route("/api/courses/<course_id>/enroll", methods=["POST"])
@token_required
def enroll_course(current_user_id, course_id):
    with engine.connect() as conn:
        # Check course exists
        c_row = conn.execute(select(courses).where(courses.c.id == str(course_id))).fetchone()
        if not c_row:
            return jsonify({"error": "Course not found"}), 404

        # Check existing enrollment
        existing = conn.execute(
            select(user_courses).where(
                (user_courses.c.user_id == str(current_user_id)) & (user_courses.c.course_id == str(course_id))
            )
        ).fetchone()

        if existing:
            return jsonify({"message": "Already enrolled in this course", "enrolled": True}), 200

        enrolled_time = datetime.now().strftime("%Y-%m-%d %H:%M")
        conn.execute(
            insert(user_courses).values(
                user_id=str(current_user_id),
                course_id=str(course_id),
                enrolled_at=enrolled_time
            )
        )
        conn.commit()

    return jsonify({"message": "Successfully enrolled in course!", "enrolled": True}), 200


@courses_bp.route("/api/courses/<course_id>/unenroll", methods=["DELETE"])
@token_required
def unenroll_course(current_user_id, course_id):
    with engine.connect() as conn:
        conn.execute(
            delete(user_courses).where(
                (user_courses.c.user_id == str(current_user_id)) & (user_courses.c.course_id == str(course_id))
            )
        )
        conn.commit()
    return jsonify({"message": "Successfully unenrolled from course", "enrolled": False}), 200


from app.models import courses, skills, user_skills, user_courses, user_favorites, course_vectors
from app.ai_services import generate_user_profile_vector, compute_similarity, generate_recommendation_explanation
import json

@courses_bp.route("/api/recommendations", methods=["GET"])
@token_required
def get_recommendations(current_user_id):
    with engine.connect() as conn:
        # Get user's selected skills
        user_skills_stmt = (
            select(skills.c.name)
            .select_from(user_skills.join(skills, user_skills.c.skill_id == skills.c.id))
            .where(user_skills.c.user_id == str(current_user_id))
        )
        user_skill_rows = conn.execute(user_skills_stmt).fetchall()
        user_skills_list = [r.name.strip() for r in user_skill_rows]

        # Generate User Profile Vector
        user_vector = generate_user_profile_vector(user_skills_list)
        
        # Get all course vectors
        stmt = select(
            courses.c.id, courses.c.title, courses.c.description, 
            courses.c.instructor, courses.c.skill_requirements,
            course_vectors.c.embedding_vector
        ).select_from(
            courses.join(course_vectors, courses.c.id == course_vectors.c.course_id)
        )
        
        all_courses = conn.execute(stmt).fetchall()
        recommended = []

        for c in all_courses:
            course_vec = json.loads(c.embedding_vector)
            
            # Compute cosine similarity
            sim_score = compute_similarity(user_vector, course_vec)
            
            recommended.append({
                "id": c.id,
                "title": c.title,
                "description": c.description,
                "instructor": c.instructor,
                "skill_requirements": c.skill_requirements,
                "match_score": round(sim_score * 100, 2),  # Percentage for display
                "explanation": "" # We will generate this for top few
            })

        # Sort recommendations by highest match score first
        recommended.sort(key=lambda x: x["match_score"], reverse=True)
        
        # Take top 3 for LLM explanation to save time/tokens
        top_recommendations = recommended[:3]
        for rec in top_recommendations:
            rec["explanation"] = generate_recommendation_explanation(
                user_skills_list, 
                rec["title"], 
                rec["description"]
            )
            
        # Add the rest without explanations
        final_list = top_recommendations + recommended[3:]

    return jsonify(final_list), 200


@courses_bp.route("/api/courses/<course_id>/favorite", methods=["POST"])
@token_required
def toggle_favorite_course(current_user_id, course_id):
    with engine.connect() as conn:
        # Check course exists
        c_row = conn.execute(select(courses).where(courses.c.id == str(course_id))).fetchone()
        if not c_row:
            return jsonify({"error": "Course not found"}), 404

        # Check existing favorite
        fav_stmt = select(user_favorites).where(
            (user_favorites.c.user_id == str(current_user_id)) & (user_favorites.c.course_id == str(course_id))
        )
        existing = conn.execute(fav_stmt).fetchone()

        if existing:
            # Unfavorite
            del_stmt = delete(user_favorites).where(
                (user_favorites.c.user_id == str(current_user_id)) & (user_favorites.c.course_id == str(course_id))
            )
            conn.execute(del_stmt)
            conn.commit()
            return jsonify({"message": "Removed from favorites", "favorited": False}), 200
        else:
            # Favorite
            created_time = datetime.now().strftime("%Y-%m-%d %H:%M")
            ins_stmt = insert(user_favorites).values(
                user_id=str(current_user_id),
                course_id=str(course_id),
                created_at=created_time
            )
            conn.execute(ins_stmt)
            conn.commit()
            return jsonify({"message": "Added to favorites", "favorited": True}), 200


@courses_bp.route("/api/favorites", methods=["GET"])
@token_required
def get_user_favorites(current_user_id):
    with engine.connect() as conn:
        stmt = (
            select(
                courses.c.id,
                courses.c.title,
                courses.c.description,
                courses.c.instructor,
                courses.c.skill_requirements,
                user_favorites.c.created_at
            )
            .select_from(user_favorites.join(courses, user_favorites.c.course_id == courses.c.id))
            .where(user_favorites.c.user_id == str(current_user_id))
        )
        rows = conn.execute(stmt).fetchall()
        favorites_list = [
            {
                "id": r.id,
                "title": r.title,
                "description": r.description,
                "instructor": r.instructor,
                "skill_requirements": r.skill_requirements,
                "created_at": r.created_at
            }
            for r in rows
        ]

    return jsonify(favorites_list), 200


