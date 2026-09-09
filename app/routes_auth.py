from flask import Blueprint, request, jsonify
from sqlalchemy import select, insert, delete
from app.db import engine
from app.models import users, skills, user_skills
from app.auth import (
    hash_password,
    verify_password,
    generate_jwt_token,
    token_required,
    validate_email,
    validate_password,
    validate_phone,
    validate_age,
)

auth_bp = Blueprint("auth", __name__)

@auth_bp.route("/api/auth/register", methods=["POST"])
def register():
    data = request.get_json() or {}
    username = data.get("username")
    email = data.get("email")
    password = data.get("password")
    phone = data.get("phone")
    age = data.get("age")
    major = data.get("major")
    selected_skills = data.get("skills", [])  # List of skill_ids or skill names

    if not username or not email or not password:
        return jsonify({"error": "Username, email, and password are required"}), 400

    if not validate_email(email):
        return jsonify({"error": "Invalid email format"}), 400

    is_valid_pw, pw_msg = validate_password(password)
    if not is_valid_pw:
        return jsonify({"error": pw_msg}), 400

    if phone:
        is_valid_phone, phone_msg = validate_phone(phone)
        if not is_valid_phone:
            return jsonify({"error": phone_msg}), 400

    if age is not None and str(age).strip() != "":
        is_valid_age, age_msg = validate_age(age)
        if not is_valid_age:
            return jsonify({"error": age_msg}), 400


    hashed_pw = hash_password(password)

    with engine.connect() as conn:
        # Check if email already exists
        stmt = select(users).where(users.c.email == email)
        existing_user = conn.execute(stmt).fetchone()
        if existing_user:
            return jsonify({"error": "User with this email already exists"}), 400

        # Insert user
        ins_user = insert(users).values(
            username=username,
            email=email,
            password=hashed_pw,
            phone=phone,
            age=age,
            major=major
        ).returning(users.c.id)
        
        result = conn.execute(ins_user)
        user_id = result.scalar()

        # Insert selected user skills if provided
        for skill_item in selected_skills:
            skill_id = None
            proficiency = "Beginner"
            if isinstance(skill_item, dict):
                skill_id = skill_item.get("skill_id")
                proficiency = skill_item.get("proficiency", "Beginner")
            elif isinstance(skill_item, str):
                s_name = skill_item.strip()
                s_row = conn.execute(select(skills).where(skills.c.name.ilike(s_name))).fetchone()
                if s_row:
                    skill_id = s_row.id
                else:
                    ins_s = insert(skills).values(name=s_name).returning(skills.c.id)
                    skill_id = conn.execute(ins_s).scalar()

            if skill_id:
                conn.execute(
                    insert(user_skills).values(
                        user_id=user_id,
                        skill_id=skill_id,
                        proficiency_level=proficiency
                    )
                )


        conn.commit()

    token = generate_jwt_token(user_id, email)
    return jsonify({
        "message": "User registered successfully",
        "user_id": user_id,
        "token": token
    }), 201


@auth_bp.route("/api/auth/login", methods=["POST"])
def login():
    data = request.get_json() or {}
    email = data.get("email")
    password = data.get("password")

    if not email or not password:
        return jsonify({"error": "Email and password are required"}), 400

    with engine.connect() as conn:
        stmt = select(users).where(users.c.email == email)
        user = conn.execute(stmt).fetchone()

        if not user or not verify_password(password, user.password):
            return jsonify({"error": "Invalid email or password"}), 401

        token = generate_jwt_token(user.id, user.email)

    return jsonify({
        "message": "Login successful",
        "token": token,
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email
        }
    }), 200


from app.models import users, skills, user_skills, user_courses, courses, user_favorites

from sqlalchemy import update

@auth_bp.route("/api/users/me", methods=["GET"])
@token_required
def get_current_user_profile(current_user_id):
    with engine.connect() as conn:
        # Fetch user
        stmt_user = select(users).where(users.c.id == current_user_id)
        user = conn.execute(stmt_user).fetchone()
        if not user:
            return jsonify({"error": "User not found"}), 404

        # Fetch user skills
        stmt_skills = (
            select(skills.c.id, skills.c.name, user_skills.c.proficiency_level)
            .select_from(user_skills.join(skills, user_skills.c.skill_id == skills.c.id))
            .where(user_skills.c.user_id == current_user_id)
        )
        skills_rows = conn.execute(stmt_skills).fetchall()

        user_skills_list = [
            {"skill_id": r.id, "skill_name": r.name, "proficiency": r.proficiency_level}
            for r in skills_rows
        ]

        # Fetch enrolled courses
        stmt_courses = (
            select(
                courses.c.id,
                courses.c.title,
                courses.c.description,
                courses.c.instructor,
                courses.c.skill_requirements,
                user_courses.c.enrolled_at
            )
            .select_from(user_courses.join(courses, user_courses.c.course_id == courses.c.id))
            .where(user_courses.c.user_id == current_user_id)
        )
        enrolled_rows = conn.execute(stmt_courses).fetchall()
        enrolled_courses_list = [
            {
                "id": r.id,
                "title": r.title,
                "description": r.description,
                "instructor": r.instructor,
                "skill_requirements": r.skill_requirements,
                "enrolled_at": r.enrolled_at
            }
            for r in enrolled_rows
        ]

        # Fetch favorited courses
        stmt_favs = (
            select(
                courses.c.id,
                courses.c.title,
                courses.c.description,
                courses.c.instructor,
                courses.c.skill_requirements,
                user_favorites.c.created_at
            )
            .select_from(user_favorites.join(courses, user_favorites.c.course_id == courses.c.id))
            .where(user_favorites.c.user_id == current_user_id)
        )
        fav_rows = conn.execute(stmt_favs).fetchall()
        favorite_courses_list = [
            {
                "id": r.id,
                "title": r.title,
                "description": r.description,
                "instructor": r.instructor,
                "skill_requirements": r.skill_requirements,
                "created_at": r.created_at
            }
            for r in fav_rows
        ]
        favorite_course_ids = [r.id for r in fav_rows]

    return jsonify({
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "phone": user.phone,
        "age": user.age,
        "major": user.major,
        "avatar_url": getattr(user, "avatar_url", None),
        "skills": user_skills_list,
        "enrolled_courses": enrolled_courses_list,
        "favorite_courses": favorite_courses_list,
        "favorite_course_ids": favorite_course_ids
    }), 200


@auth_bp.route("/api/users/me", methods=["PUT"])
@token_required
def update_user_profile(current_user_id):
    data = request.get_json() or {}
    email = data.get("email")
    username = data.get("username")
    phone = data.get("phone")
    age = data.get("age")
    major = data.get("major")
    avatar_url = data.get("avatar_url")

    with engine.connect() as conn:
        stmt_user = select(users).where(users.c.id == current_user_id)
        current_user = conn.execute(stmt_user).fetchone()
        if not current_user:
            return jsonify({"error": "User not found"}), 404

        update_values = {}

        if username and username.strip():
            update_values["username"] = username.strip()

        if email and email.strip() and email.strip() != current_user.email:
            new_email = email.strip()
            if not validate_email(new_email):
                return jsonify({"error": "Invalid email format"}), 400
            
            existing = conn.execute(select(users).where(users.c.email == new_email)).fetchone()
            if existing:
                return jsonify({"error": "An account with this email already exists"}), 400
            update_values["email"] = new_email

        if phone is not None and str(phone).strip() != "":
            is_valid_phone, phone_msg = validate_phone(phone)
            if not is_valid_phone:
                return jsonify({"error": phone_msg}), 400
            update_values["phone"] = str(phone).strip()
        elif phone is not None:
            update_values["phone"] = None

        if age is not None and str(age).strip() != "":
            is_valid_age, age_msg = validate_age(age)
            if not is_valid_age:
                return jsonify({"error": age_msg}), 400
            update_values["age"] = int(age)
        elif age is not None:
            update_values["age"] = None

        if major is not None:
            update_values["major"] = major.strip() if isinstance(major, str) else major
        if avatar_url is not None:
            update_values["avatar_url"] = avatar_url.strip() if isinstance(avatar_url, str) else avatar_url

        if update_values:
            upd_stmt = update(users).where(users.c.id == current_user_id).values(**update_values)
            conn.execute(upd_stmt)
            conn.commit()

        # Re-fetch updated user
        updated_user = conn.execute(select(users).where(users.c.id == current_user_id)).fetchone()
        new_token = generate_jwt_token(updated_user.id, updated_user.email)

    return jsonify({
        "message": "Profile updated successfully",
        "token": new_token,
        "user": {
            "id": updated_user.id,
            "username": updated_user.username,
            "email": updated_user.email,
            "phone": updated_user.phone,
            "age": updated_user.age,
            "major": updated_user.major,
            "avatar_url": updated_user.avatar_url
        }
    }), 200


@auth_bp.route("/api/users/me/password", methods=["PUT"])
@token_required
def change_password(current_user_id):
    data = request.get_json() or {}
    old_password = data.get("old_password")
    new_password = data.get("new_password")

    if not old_password or not new_password:
        return jsonify({"error": "Both old password and new password are required"}), 400

    with engine.connect() as conn:
        stmt_user = select(users).where(users.c.id == current_user_id)
        current_user = conn.execute(stmt_user).fetchone()
        if not current_user:
            return jsonify({"error": "User not found"}), 404

        if not verify_password(old_password, current_user.password):
            return jsonify({"error": "Current password does not match your account password"}), 400

        is_valid_pw, pw_msg = validate_password(new_password)
        if not is_valid_pw:
            return jsonify({"error": pw_msg}), 400

        hashed_pw = hash_password(new_password)
        upd_stmt = update(users).where(users.c.id == current_user_id).values(password=hashed_pw)
        conn.execute(upd_stmt)
        conn.commit()

    return jsonify({"message": "Password updated successfully!"}), 200





@auth_bp.route("/api/users/skills", methods=["POST"])
@token_required
def add_user_skill(current_user_id):
    data = request.get_json() or {}
    skill_name = data.get("skill_name", "").strip()
    proficiency = data.get("proficiency", "Intermediate").strip()

    if not skill_name:
        return jsonify({"error": "Skill name is required"}), 400

    with engine.connect() as conn:
        # Check if skill exists
        s_stmt = select(skills).where(skills.c.name.ilike(skill_name))
        s_row = conn.execute(s_stmt).fetchone()

        if s_row:
            skill_id = s_row.id
        else:
            ins_s = insert(skills).values(name=skill_name).returning(skills.c.id)
            skill_id = conn.execute(ins_s).scalar()

        # Check if user already has skill
        us_stmt = select(user_skills).where(
            (user_skills.c.user_id == current_user_id) & (user_skills.c.skill_id == skill_id)
        )
        us_row = conn.execute(us_stmt).fetchone()

        if not us_row:
            conn.execute(
                insert(user_skills).values(
                    user_id=current_user_id,
                    skill_id=skill_id,
                    proficiency_level=proficiency
                )
            )
            conn.commit()
            msg = "Skill added successfully"
        else:
            msg = "Skill already exists on your profile"

    return jsonify({"message": msg}), 200


@auth_bp.route("/api/users/skills/<skill_id>", methods=["DELETE"])
@token_required
def delete_user_skill(current_user_id, skill_id):
    with engine.connect() as conn:
        del_stmt = delete(user_skills).where(
            (user_skills.c.user_id == current_user_id) & (user_skills.c.skill_id == skill_id)
        )
        conn.execute(del_stmt)
        conn.commit()
    return jsonify({"message": "Skill deleted successfully"}), 200

from app.ai_services import extract_skills_with_llm

@auth_bp.route("/api/extract-skills", methods=["POST"])
@token_required
def extract_skills_endpoint(current_user_id):
    data = request.get_json() or {}
    text = data.get("text", "").strip()
    
    if not text:
        return jsonify({"error": "Text is required"}), 400
        
    extracted_skills = extract_skills_with_llm(text)
    
    if not extracted_skills:
        return jsonify({"message": "No skills extracted", "skills": []}), 200
        
    added_skills = []
    
    with engine.connect() as conn:
        for skill_name in extracted_skills:
            # Check if skill exists
            s_stmt = select(skills).where(skills.c.name.ilike(skill_name))
            s_row = conn.execute(s_stmt).fetchone()

            if s_row:
                skill_id = s_row.id
            else:
                ins_s = insert(skills).values(name=skill_name).returning(skills.c.id)
                skill_id = conn.execute(ins_s).scalar()

            # Check if user already has skill
            us_stmt = select(user_skills).where(
                (user_skills.c.user_id == current_user_id) & (user_skills.c.skill_id == skill_id)
            )
            us_row = conn.execute(us_stmt).fetchone()

            if not us_row:
                conn.execute(
                    insert(user_skills).values(
                        user_id=current_user_id,
                        skill_id=skill_id,
                        proficiency_level="Beginner" # Default from extraction
                    )
                )
                added_skills.append(skill_name)
        
        conn.commit()
        
    return jsonify({
        "message": f"Successfully extracted and added {len(added_skills)} skills.",
        "skills": added_skills
    }), 200



