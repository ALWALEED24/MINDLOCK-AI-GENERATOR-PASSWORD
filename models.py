# models.py
from sqlalchemy import Boolean, Column, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    
    # --- YOU ARE MISSING THIS LINE ---
    face_encoding_pickle = Column(String, nullable=True)
    # ---------------------------------

    saved_passwords = relationship("SavedPassword", back_populates="owner")

class SavedPassword(Base):
    __tablename__ = "saved_passwords"
    id = Column(Integer, primary_key=True, index=True)
    platform = Column(String, index=True)
    username = Column(String, index=True)
    password = Column(String)
    image_hint = Column(String) # Ensure this is here too
    owner_id = Column(Integer, ForeignKey("users.id"))
    owner = relationship("User", back_populates="saved_passwords")