# crud.py
from sqlalchemy.orm import Session
import models 

def get_user_by_email(db: Session, email: str):
    return db.query(models.User).filter(models.User.email == email).first()

def create_user(db: Session, email: str, password: str):
    db_user = models.User(email=email, hashed_password=password)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

# THIS FUNCTION IS CORRECT NOW
# In crud.py

def create_saved_password(db: Session, platform: str, username: str, password: str, image_hint: str, owner_id: int):
    # 1. Create and Save the NEW password first
    db_password = models.SavedPassword(
        platform=platform,
        username=username,
        password=password,
        image_hint=image_hint,
        owner_id=owner_id
    )
    db.add(db_password)
    db.commit()
    db.refresh(db_password)

    
    # Order them by ID descending (Newest IDs are at the top)
    existing_passwords = db.query(models.SavedPassword)\
        .filter(models.SavedPassword.owner_id == owner_id)\
        .filter(models.SavedPassword.platform == platform)\
        .order_by(models.SavedPassword.id.desc())\
        .all()

    # Check if we have more than 5
    if len(existing_passwords) > 5:
        
        passwords_to_delete = existing_passwords[5:]

        for old_pw in passwords_to_delete:
            db.delete(old_pw)
        
        db.commit() 

    return db_password
def update_password(db: Session, email: str, platform: str, new_password: str):
    # 1. Find the user
    user = get_user_by_email(db, email)
    if not user:
        return False
    
    # 2. Find the specific saved password entry for that platform
    for pw_entry in user.saved_passwords:
        if pw_entry.platform == platform:
            pw_entry.password = new_password
            db.commit()
            db.refresh(pw_entry)
            return True
            
    
    #  Added "mountain" as a default image hint so this doesn't crash
    create_saved_password(db, platform, user.email, new_password, "mountain", user.id)
    return True

def update_master_password(db: Session, email: str, new_password: str):
    # 1. Find the user
    user = get_user_by_email(db, email)
    if user:
        # 2. Update the password
        user.hashed_password = new_password
        db.commit()
        db.refresh(user)
        return True
    return False