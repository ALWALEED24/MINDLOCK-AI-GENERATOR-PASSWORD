
import random
from fastapi import FastAPI, Request, Form, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import uvicorn 
from pyngrok import ngrok
import base64 #face
import numpy as np
import cv2 
import io
from PIL import Image
from sqlalchemy.orm import Session
import crud, models
from database import SessionLocal, engine
import smtplib
from email.message import EmailMessage
import google.generativeai as genai
#  Create Database Tables 
models.Base.metadata.create_all(bind=engine)

# SETUP 
app = FastAPI(title="Password Manager AI")
templates = Jinja2Templates(directory="templates")

# Database Dependency 
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()



#  RULE-BASED "AI" ALGORITHM ---
def generate_passwords_from_survey(data: dict) -> list[str]:
    def get(key):
        return (data.get(key) or "").strip().capitalize()

    leetspeak = {'a': '4', 'e': '3', 'i': '1', 'o': '0', 's': '5', 't': '7'}
    def to_leetspeak(word):
        return ''.join(leetspeak.get(char.lower(), char) for char in word)

    parts = [
        get("nickname"), get("hobby"), get("favourite_food"), get("favourite_sport"),
        get("favourite_subject"), get("favourite_book"), get("childhood_nickname"),
        get("favourite_celebrity"), get("ambition"), get("favourite_place"),
        get("favourite_cafe"), get("username")
    ]
    parts = [p for p in parts if p and len(p) > 2]

    if len(parts) < 2:
        parts.extend(["Mind", "Lock", "Secure", "Pass", "Code", "Key"])

    numbers = (data.get("favourite_number") or "12345")
    symbols = ['!', '@', '#', '$', '%', '&', '*']
    generated = set()

    while len(generated) < 10:
        rule = random.randint(1, 5)
        p1, p2 = random.sample(parts, 2)
        num = ''.join(random.sample(numbers, min(len(numbers), 3)))
        sym = random.choice(symbols)

        if rule == 1:
            password = f"{p1}{num}{sym}"
        elif rule == 2:
            password = f"{to_leetspeak(p1)}{sym}{num}"
        elif rule == 3:
            password = f"{p1}{sym}{p2[:4]}"
        elif rule == 4:
            password = f"{num}{to_leetspeak(p2)}{sym}"
        else:
            password = f"{p1[:3]}{num}{p2[:3]}{sym}"
            
        generated.add(password[:16])
    
    return list(generated)


#  WEB PAGE ENDPOINTS 

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("home.html", {"request": request})

@app.get("/login", response_class=HTMLResponse)
async def show_login_form(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/register", response_class=HTMLResponse)
async def show_register_step1_form(request: Request):
    return templates.TemplateResponse("register_step1.html", {"request": request})

@app.post("/register-step2", response_class=HTMLResponse)
async def show_register_step2_form(request: Request, email: str = Form(), password: str = Form()):
    return templates.TemplateResponse("register.html", {
        "request": request,
        "email": email,
        "password": password
    })

@app.post("/register", response_class=HTMLResponse)
async def handle_survey_and_generate_passwords(request: Request):
    form_data_from_request = await request.form()
    user_survey_data = dict(form_data_from_request)
    generated_passwords = generate_passwords_from_survey(user_survey_data)
    
    return templates.TemplateResponse("password_recommendations.html", {
        "request": request,
        "user_data": user_survey_data,
        "generated_passwords": generated_passwords,
        "social_media_options": ["Instagram", "Facebook", "Gmail", "Twitter", "TikTok", "Snapchat", "Reddit", "Threads", "Youtube", "LinkedIn"]
    })


@app.post("/face-verify", response_class=HTMLResponse)
async def show_face_verify_page(request: Request):
    # Capture ALL form data
    form_data = await request.form()
    
    return templates.TemplateResponse("face_verify.html", {
        "request": request,
        "data": form_data # Pass EVERYTHING to the next page
    })


@app.post("/finalize-registration", response_class=HTMLResponse)
async def finalize_registration(
    request: Request,
    db: Session = Depends(get_db),
    # 1. Basic Info
    email: str = Form(...),
    app_password: str = Form(...),
    username: str = Form(...),
    platform: str = Form(...),
    password: str = Form(...),
    image_hint: str = Form(...), 
    image_data: str = Form(...),
    # 2. Preference Fields (Must match your Survey form names)
    nickname: str = Form(None), favourite_number: str = Form(None), hobby: str = Form(None),
    favourite_food: str = Form(None), favourite_sport: str = Form(None), favourite_subject: str = Form(None),
    favourite_book: str = Form(None), childhood_nickname: str = Form(None), favourite_celebrity: str = Form(None),
    sibling_position: str = Form(None), ambition: str = Form(None), favourite_place: str = Form(None),
    favourite_cafe: str = Form(None)
):
    # --- 1. FACE CHECK (Your existing logic) ---
    if not detect_face_opencv(image_data): # Or verify_face_match if you are using that
        return templates.TemplateResponse("face_verify.html", {
            "request": request, "error": "No face detected.", 
            "email": email, "app_password": app_password, 
            # We must pass these back if error occurs so data isn't lost
            "username": username, "platform": platform, "password": password, "image_hint": image_hint
        })

    # --- 2. CREATE USER & PREFERENCES ---
    db_user = crud.get_user_by_email(db, email=email)
    
    if not db_user:
        # A. Create the User
        db_user = models.User(
            email=email, 
            hashed_password=app_password,
            face_encoding_pickle=image_data 
        )
        db.add(db_user)
        db.commit()
        db.refresh(db_user)

        # B. Create the Preferences (NEW STEP)
        print("Saving initial preferences...")
        new_prefs = models.UserPreferences(
            user_id=db_user.id,
            nickname=nickname,
            favourite_number=favourite_number,
            hobby=hobby,
            favourite_food=favourite_food,
            favourite_sport=favourite_sport,
            favourite_subject=favourite_subject,
            favourite_book=favourite_book,
            childhood_nickname=childhood_nickname,
            favourite_celebrity=favourite_celebrity,
            sibling_position=sibling_position,
            ambition=ambition,
            favourite_place=favourite_place,
            favourite_cafe=favourite_cafe
        )
        db.add(new_prefs)
        db.commit()
    
    # --- 3. SAVE PASSWORD ---
    crud.create_saved_password(db, platform, username, password, image_hint, db_user.id)

    return templates.TemplateResponse("final_summary.html", {
        "request": request, "email": email, "username": username, 
        "platform": platform, "password": password, "image_hint": image_hint
    })


@app.post("/login-check", response_class=HTMLResponse)
async def login_check(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    #  Check if email/password are correct 
    user = crud.get_user_by_email(db, email=email)
    if not user or user.hashed_password != password:
        return templates.TemplateResponse("login.html", {
            "request": request, 
            "error": "Invalid email or password"
        })
    
    # 2. If correct, show the Camera Page
    return templates.TemplateResponse("face_verify_login.html", {
        "request": request,
        "email": email,
        "password": password
    })



# --- CARD 6: DATABASE VIEW (READ ONLY) ---
@app.post("/database-view", response_class=HTMLResponse)
async def database_view_page(
    request: Request, 
    email: str = Form(...),
    # We still need the password to verify identity, but no face check
    password: str = Form(...), 
    db: Session = Depends(get_db)
):
    # 1. Validate Credentials (Basic Security)
    user = crud.get_user_by_email(db, email=email)
    if not user or user.hashed_password != password:
        return templates.TemplateResponse("login.html", {
            "request": request, "error": "Invalid email or password"
        })

    # 2. PREPARE DATA (No Face Check needed here)
    all_platforms_list = ["Instagram", "Facebook", "Gmail", "Twitter", "TikTok", "Snapchat", "Reddit", "Threads", "Youtube", "LinkedIn"]
    
    user_data_map = {}
    for pw in user.saved_passwords:
        user_data_map[pw.platform] = pw
    
    final_display_list = []
    
    for platform_name in all_platforms_list:
        if platform_name in user_data_map:
            db_obj = user_data_map[platform_name]
            
            # Find Icon
            found_icon_url = "" 
            if db_obj.image_hint:
                for icon in ICON_POOL:
                    if icon['name'] == db_obj.image_hint:
                        found_icon_url = icon['url']
                        break
            
            final_display_list.append({
                "platform": platform_name, 
                "password": db_obj.password, 
                "username": db_obj.username, 
                "image_hint": db_obj.image_hint, 
                "icon_url": found_icon_url, 
                "is_empty": False
            })
        else:
            final_display_list.append({
                "platform": platform_name, "password": "Not Set", "username": "", "image_hint": None, "icon_url": "", "is_empty": True
            })

    # 3. Render the Read-Only Template
    return templates.TemplateResponse("Database_view.html", {
        "request": request, 
        "passwords": final_display_list, 
        "user_email": user.email,
        "user_password": password 
    })

@app.post("/reset-password-page", response_class=HTMLResponse)
async def show_reset_page(request: Request, email: str = Form(), platform: str = Form()):
    return templates.TemplateResponse("reset_password.html", {
        "request": request,
        "email": email,
        "platform": platform
    })

#  SAVE the new password to Database
@app.post("/perform-reset", response_class=HTMLResponse)
async def perform_reset(
    request: Request,
    db: Session = Depends(get_db),
    email: str = Form(),
    platform: str = Form(),
    new_password: str = Form()
):
    #  Update the database with the new password
    crud.update_password(db, email, platform, new_password)
    
    #  Show the Success Page (Instead of the Dashboard)
    return templates.TemplateResponse("reset_success.html", {
        "request": request
    })


ICON_POOL = [
    {"name": "mountain", "url": "https://img.icons8.com/color/96/mountain.png"},
    {"name": "tree", "url": "https://img.icons8.com/color/96/deciduous-tree.png"},
    {"name": "beach", "url": "https://img.icons8.com/color/96/beach.png"},
    {"name": "sun", "url": "https://img.icons8.com/color/96/sun--v1.png"},
    {"name": "moon", "url": "https://img.icons8.com/color/96/moon-satellite.png"},
    {"name": "star", "url": "https://img.icons8.com/color/96/star--v1.png"},
    {"name": "cloud", "url": "https://img.icons8.com/color/96/cloud.png"},
    {"name": "fire", "url": "https://img.icons8.com/color/96/fire-element.png"},
    {"name": "water", "url": "https://img.icons8.com/color/96/water.png"},
    {"name": "flower", "url": "https://img.icons8.com/color/96/flower.png"},
    {"name": "dog", "url": "https://img.icons8.com/color/96/dog.png"},
    {"name": "cat", "url": "https://img.icons8.com/color/96/cat.png"},
    {"name": "lion", "url": "https://img.icons8.com/color/96/lion.png"},
    {"name": "fish", "url": "https://img.icons8.com/color/96/clown-fish.png"},
    {"name": "pizza", "url": "https://img.icons8.com/color/96/pizza.png"},
    {"name": "burger", "url": "https://img.icons8.com/color/96/hamburger.png"},
    {"name": "car", "url": "https://img.icons8.com/color/96/car--v1.png"},
    {"name": "camera", "url": "https://img.icons8.com/color/96/camera--v1.png"},
    {"name": "heart", "url": "https://img.icons8.com/color/96/like--v1.png"},
    {"name": "clock", "url": "https://img.icons8.com/color/96/clock--v1.png"}
]


@app.post("/visual-hint", response_class=HTMLResponse)
async def show_visual_hint_page(request: Request):
    # 1. Capture ALL data sent from the previous page (Email, Password, Survey Answers)
    form_data = await request.form()

    # 2. Generate Random Icons
    random_5 = random.sample(ICON_POOL, 5)

    # 3. Pass everything to the HTML
    return templates.TemplateResponse("visual_memory.html", {
        "request": request,
        "security_icons": random_5,
        "data": form_data  #   holds email, password, AND all survey answers
    })
#  Show the "Enter Email" Page
@app.get("/forgot-password", response_class=HTMLResponse)
async def show_forgot_password(request: Request):
    return templates.TemplateResponse("forgot_request.html", {"request": request})

SENDER_EMAIL = "-------------------"  # <--- REAL GMAIL 
APP_PASSWORD = "rror sccn ltgf vqyt"   # <--- 16-CHAR APP PASSWORD 


@app.post("/send-reset-email", response_class=HTMLResponse)
async def send_reset_email(request: Request, email: str = Form(), db: Session = Depends(get_db)):
    #  Check if user exists
    user = crud.get_user_by_email(db, email=email)
    
    if not user:
        return templates.TemplateResponse("forgot_request.html", {
            "request": request,
            "error": "Email not found in our database."
        })
    
    base_url = str(request.base_url) 
    reset_link = f"{base_url}recover-password?email={email}"
    
    #  Create the Email
    msg = EmailMessage()
    msg['Subject'] = "Reset Your Password - MindLock"
    msg['From'] = SENDER_EMAIL
    msg['To'] = email

    # Plain text fallback 
    msg.set_content(f"Please click this link to reset your password: {reset_link}")

    # creates the "Continue" Button) 
    msg.add_alternative(f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            .container {{
                font-family: Arial, sans-serif;
                background-color: #f4f4f4;
                padding: 20px;
                text-align: center;
            }}
            .box {{
                background-color: #ffffff;
                padding: 30px;
                border-radius: 10px;
                max-width: 500px;
                margin: 0 auto;
                box-shadow: 0 4px 10px rgba(0,0,0,0.1);
            }}
            .btn {{
                background-color: #007bff; /* Blue Color */
                color: #ffffff !important;
                padding: 15px 30px;
                text-decoration: none;
                border-radius: 5px;
                font-weight: bold;
                font-size: 16px;
                display: inline-block;
                margin-top: 20px;
                margin-bottom: 20px;
            }}
            .btn:hover {{
                background-color: #0056b3;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="box">
                <h2 style="color: #333;">Reset Password</h2>
                <p style="color: #666;">We received a request to change your password.</p>
                <p style="color: #666;">Click the button below to proceed:</p>
                
                <!-- THIS IS THE CONTINUE BUTTON -->
                <a href="{reset_link}" class="btn">Continue</a>
                
                <p style="font-size: 12px; color: #999; margin-top: 20px;">
                    If the button doesn't work, copy this link:<br>
                    {reset_link}
                </p>
            </div>
        </div>
    </body>
    </html>
    """, subtype='html')

    #  Send via Gmail
    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(SENDER_EMAIL, APP_PASSWORD)
            smtp.send_message(msg)
            print("Email sent successfully!")
            
        return templates.TemplateResponse("email_sent_confirmation.html", {
            "request": request,
            "email": email
        })

    except Exception as e:
        print(f"Error sending email: {e}")
        return templates.TemplateResponse("forgot_request.html", {
            "request": request,
            "error": "System Error: Could not send email."
        })

# Show the "Enter New Password" Page 
@app.get("/recover-password", response_class=HTMLResponse)
async def show_recover_form(request: Request, email: str):
    return templates.TemplateResponse("reset_user_password.html", {
        "request": request,
        "email": email
    })

#  Perform the Update
@app.post("/finalize-master-reset", response_class=HTMLResponse)
async def finalize_master_reset(
    request: Request, 
    email: str = Form(), 
    new_password: str = Form(),
    db: Session = Depends(get_db)
):
    # Update the password in DB
    crud.update_master_password(db, email, new_password)
    
    
    return templates.TemplateResponse("login.html", {
        "request": request,
        "success": "Password updated! You can now log in."
    })

# Basic Detection (Is there a face?) 
def detect_face_opencv(base64_string):
    try:
        if "," in base64_string: header, encoded = base64_string.split(",", 1)
        else: encoded = base64_string
        image_bytes = base64.b64decode(encoded)
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray, 1.1, 4)
        return len(faces) > 0
    except:
        return False


def verify_face_match(img1_b64, img2_b64):
    try:
        #Decode Images
        def decode(b64):
            if "," in b64: _, b64 = b64.split(",", 1)
            nparr = np.frombuffer(base64.b64decode(b64), np.uint8)
            return cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        img1 = decode(img1_b64)
        img2 = decode(img2_b64)

        #Load Face Detector
        face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')

        # 3. Crop & Preprocess
        def process_face(img):
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            # Detect face
            faces = face_cascade.detectMultiScale(gray, 1.1, 4)
            if len(faces) == 0:
                return None
            x, y, w, h = faces[0]
            # Crop to face
            face_roi = img[y:y+h, x:x+w]
            # Resize to standard 100x100 for consistency
            face_roi = cv2.resize(face_roi, (100, 100))
            
            # one photo is dark and the other is bright
            ycrcb = cv2.cvtColor(face_roi, cv2.COLOR_BGR2YCrCb)
            channels = cv2.split(ycrcb)
            cv2.equalizeHist(channels[0], channels[0])
            cv2.merge(channels, ycrcb)
            return cv2.cvtColor(ycrcb, cv2.COLOR_YCrCb2BGR)

        face1 = process_face(img1)
        face2 = process_face(img2)

        if face1 is None or face2 is None:
            print("Error: Face not clearly detected in one image.")
            return False

        
        # Eyes/Forehead (Top 35%)
        #  Nose (Middle 30%)
        #  Mouth/Chin (Bottom 35%)
        
        zones = [
            (0, 35),   # Top
            (35, 65),  # Middle
            (65, 100)  # Bottom
        ]
        
        total_score = 0

        for start, end in zones:
            # Crop the zone
            zone1 = face1[start:end, :]
            zone2 = face2[start:end, :]

            # Convert to HSV
            hsv1 = cv2.cvtColor(zone1, cv2.COLOR_BGR2HSV)
            hsv2 = cv2.cvtColor(zone2, cv2.COLOR_BGR2HSV)

            # Calculate Histogram for this zone
            hist1 = cv2.calcHist([hsv1], [0, 1], None, [180, 256], [0, 180, 0, 256])
            hist2 = cv2.calcHist([hsv2], [0, 1], None, [180, 256], [0, 180, 0, 256])

            cv2.normalize(hist1, hist1, 0, 1, cv2.NORM_MINMAX)
            cv2.normalize(hist2, hist2, 0, 1, cv2.NORM_MINMAX)

            # Compare
            score = cv2.compareHist(hist1, hist2, cv2.HISTCMP_CORREL)
            total_score += score

        # Average the score of the 3 zones
        avg_score = total_score / 3
        print(f"Zonal Accuracy Score: {avg_score}")

        #Threshold 0.5
        if avg_score > 0.3:
            return True
        else:
            return False

    except Exception as e:
        print(f"Comparison Error: {e}")
        return False




@app.get("/help", response_class=HTMLResponse)
async def show_help_page(request: Request):
    return templates.TemplateResponse("help.html", {"request": request})

# --- EXPANDED LOCAL AI BRAIN ---

@app.post("/api/chat")
async def chat_with_ai(request: Request):
    data = await request.json()
    user_message = data.get("message", "").lower() 
    
    response_text = ""

    
    #  GREETINGS & BASICS
    if any(word in user_message for word in ["hello", "hi", "hey", "morning", "evening"]):
        response_text = "Hello! I am MindLock AI. I can help you with Registration, Face Verification, Password Generate, or Account Recovery. What do you need?"

    elif "who are you" in user_message or "what is this" in user_message:
        response_text = "I am the automated support agent for MindLock. My job is to explain how our AI security features protect your data."

    #  PASSWORD GENERATION (THE SURVEY)

    elif any(word in user_message for word in ["generate", "make password", "create password", "survey",]):
        response_text = "MindLock generates passwords based on your personality! During registration, we ask about your hobbies and favorites, then mix them with special characters (Leetspeak) to create a password that is strong but easy for YOU to remember."

    elif "leetspeak" in user_message or "algorithm" in user_message:
        response_text = "Our algorithm converts letters to numbers (like 'E' to '3' or 'A' to '4'). This makes your password harder for hackers to guess but easy for you to read."

    
    #  VISUAL HINT (THE ICONS)
    elif any(word in user_message for word in ["icon", "picture", "image", "visual", " hint"]):
        response_text = "The Visual Hint is a memory anchor. When you register, you select an icon (like a Pizza or Car). On your dashboard, seeing that icon helps you instantly recall which password you used for that account."

    elif "Password Generation" in user_message:
        response_text = "To generate a new password, click the green 'Generate' card on your Dashboard. Our AI will use your saved preferences (like your favorite food or hobby) to build a secure, memorable password instantly."

    elif "forgot icon" in user_message:
        response_text = "If you forgot which icon you chose, don't worry! You can simply view the password on your dashboard, or reset it if needed."

    
    #  FACE VERIFICATION (SECURITY)
   
    elif any(word in user_message for word in ["face", "camera", "webcam", "recognition", "verify"]):
        response_text = "We use Biometric Verification. During registration, we scan your face. Every time you log in, we compare your live video feed against that saved data to ensure it is really you."

    elif "not working" in user_message and ("camera" in user_message or "face" in user_message):
        response_text = "If face verification fails: 1. Ensure you have good lighting. 2. Remove glasses or masks. 3. Make sure you are using the same device you registered with."

    elif "privacy" in user_message or "photo" in user_message:
        response_text = "Your privacy is a priority. We convert your face data into a mathematical code stored securely in our database. We do not sell or share your biometric data."

    
    #  DASHBOARD & USAGE
    
    elif "dashboard" in user_message:
        response_text = "The Dashboard is your secure vault. It shows all your accounts (Instagram, Facebook, etc.). You can see your Visual Hints and copy your passwords with one click."

    elif "copy" in user_message:
        response_text = "On the dashboard, click the small 'Copy' icon next to any password to copy it to your clipboard instantly."

    elif "username" in user_message:
        response_text = "Your dashboard displays both the platform name and the username you registered for that platform, so you never get confused."

    
    #  RESET PASSWORD / FORGOT
    elif "reset" in user_message or "forgot" in user_message or "change password" in user_message:
        response_text = "To reset your password: 1. Go to the Login page. 2. Click 'Forgot Password?'. 3. Enter your email. 4. We will send you a secure link to create a new Master Password."

    elif "email" in user_message:
        response_text = "We use your email to send security alerts and password reset links. Please make sure you use a valid email address."

    elif "register" in user_message:
        response_text = "You can create a new account by clicking 'Sign Up'. We use AI to generate secure passwords for you."

    elif "login" in user_message:
        response_text = "You can click the top left button 'Login' to get login to your account ."    
    #  GENERAL SECURITY
    elif "safe" in user_message or "secure" in user_message or "hack" in user_message:
        response_text = "MindLock is designed with a 'Defense in Depth' strategy. We combine Knowledge (Passwords), Possession (Your Device), and Biometrics (Your Face) to prevent unauthorized access."

    elif "master password" in user_message:
        response_text = "Your Master Password is the key to your vault. It is the only password you need to memorize. If you lose it, use the 'Forgot Password' feature to reset it via email."

    elif "mindlock" in user_message or "what is this" in user_message or "about" in user_message:
        response_text = "MindLock is an advanced AI-powered password manager. Unlike standard tools, we generate custom passwords based on your personality profile and secure them using Biometric Face Verification and Visual Memory Anchors."
    
    elif "Password " in user_message:
        response_text = "To generate a new password, click the green 'Generate' card on your Dashboard. Our AI will use your saved preferences (like your favorite food or hobby) to build a secure, memorable password instantly."

    elif any(word in user_message for word in ["recover", "recovery", "locked out", "lost access"]):
        response_text = "If you are locked out, use the 'Forgot Password?' link on the login page. We will send a recovery link to your registered email address. Note: You will need access to your email to regain entry."

    #  FALLBACK (DEFAULT)
    else:
        response_text = "I am focus on MindLock features. You can ask me about: 'Face Verification', 'Visual', 'Hints',  'How to Register', or 'Resetting Password'."

    # Simulate thinking time
    import time
    time.sleep(0.6) 
    
    return {"response": response_text}


@app.post("/dashboard", response_class=HTMLResponse)
async def dashboard(
    request: Request, 
    email: str = Form(...), 
    password: str = Form(...), 
    image_data: str = Form(None), 
    db: Session = Depends(get_db)
):
    # 1. Credentials Check
    user = crud.get_user_by_email(db, email=email)
    if not user or user.hashed_password != password:
        return templates.TemplateResponse("login.html", {
            "request": request, "error": "Invalid email or password"
        })

    # 2. Face Verification (If image provided)
    if image_data and user.face_encoding_pickle:
        # Assuming you kept the 'verify_face_match' function we wrote earlier
        is_match = verify_face_match(user.face_encoding_pickle, image_data)
        if not is_match:
            return templates.TemplateResponse("face_verify_login.html", {
                "request": request, "error": "Face Verification Failed", "email": email, "password": password
            })

    # 3. Render the Menu (6 Cards)
    username = email.split("@")[0] # Extract name from email
    return templates.TemplateResponse("dashboard_menu.html", {
        "request": request,
        "username": username,
        "email": email,
        "password": password
    })


@app.post("/view-vault", response_class=HTMLResponse)
async def view_vault(
    request: Request, 
    email: str = Form(...),
    password: str = Form(...), 
    db: Session = Depends(get_db)
):
    user = crud.get_user_by_email(db, email=email)
    
    # Define platform list
    all_platforms_list = ["Instagram", "Facebook", "Gmail", "Twitter", "TikTok", "Snapchat", "Reddit", "Threads", "Youtube", "LinkedIn"]
    
    # Map existing data
    user_data_map = {pw.platform: pw for pw in user.saved_passwords}
    final_display_list = []
    
    for platform_name in all_platforms_list:
        if platform_name in user_data_map:
            db_obj = user_data_map[platform_name]
            
            # Find Icon URL
            found_icon_url = "" 
            if db_obj.image_hint:
                for icon in ICON_POOL:
                    if icon['name'] == db_obj.image_hint:
                        found_icon_url = icon['url']
                        break

            final_display_list.append({
                "platform": platform_name, 
                "password": db_obj.password, 
                "username": db_obj.username, 
                "icon_url": found_icon_url, 
                "is_empty": False
            })
        else:
            final_display_list.append({
                "platform": platform_name, "password": "Not Set", "username": "", "icon_url": "", "is_empty": True
            })

    return templates.TemplateResponse("dashboard.html", {
        "request": request, 
        "passwords": final_display_list, 
        "user_email": user.email,
        "user_password": password 
      
    })




# --- CARD 4: PROFILE LOGIC (UPDATED) ---

@app.post("/profile", response_class=HTMLResponse)
async def show_profile(
    request: Request, 
    email: str = Form(), 
    password: str = Form(),
    db: Session = Depends(get_db)
):
    # Get user to display current details
    user = crud.get_user_by_email(db, email=email)
    
    # Get preferences to show the nickname (Username)
    prefs = db.query(models.UserPreferences).filter(models.UserPreferences.user_id == user.id).first()
    current_username = prefs.nickname if prefs else ""

    return templates.TemplateResponse("profile.html", {
        "request": request,
        "email": email,
        "password": password,
        "username": current_username,
        "user": user
    })

@app.post("/update-profile", response_class=HTMLResponse)
async def update_profile(
    request: Request, 
    # We need the ORIGINAL email to find the user in the DB
    original_email: str = Form(...), 
    original_password: str = Form(...),
    # The NEW values typed in the form
    new_email: str = Form(...),
    new_username: str = Form(""),
    new_password: str = Form(None), 
    db: Session = Depends(get_db)
):
    user = crud.get_user_by_email(db, email=original_email)
    message = ""
    error = ""
    
    # Variables to track what the credentials are NOW (for the back button)
    current_email = original_email
    current_password = original_password

    if user:
        # 1. Update Email (If changed)
        if new_email != original_email:
            # Check if new email is already taken by someone else
            existing_user = crud.get_user_by_email(db, email=new_email)
            if existing_user:
                error = "That email is already in use!"
                # Return immediately with error
                return templates.TemplateResponse("profile.html", {
                    "request": request, "email": original_email, "password": original_password,
                    "username": new_username, "error": error
                })
            else:
                user.email = new_email
                current_email = new_email # Update tracker
                message += "Email updated. "

        # 2. Update Password (If provided)
        if new_password and len(new_password) > 0:
            user.hashed_password = new_password
            current_password = new_password # Update tracker
            message += "Password updated. "

        # 3. Update Username (Nickname in Preferences)
        prefs = db.query(models.UserPreferences).filter(models.UserPreferences.user_id == user.id).first()
        if not prefs:
            prefs = models.UserPreferences(user_id=user.id)
            db.add(prefs)
        
        if prefs.nickname != new_username:
            prefs.nickname = new_username
            message += "Username updated."

        db.commit()
        if not message: message = "No changes made."

    else:
        error = "User not found."

    # Return with the NEW credentials so the dashboard doesn't lock us out
    return templates.TemplateResponse("profile.html", {
        "request": request,
        "email": current_email,
        "password": current_password,
        "username": new_username,
        "message": message,
        "error": error
    })


# --- CARD 5: FEEDBACK (Popup Submission) ---
@app.post("/submit-feedback", response_class=HTMLResponse)
async def submit_feedback(rating: str = Form(...), comment: str = Form(...)):
    print(f"🌟 FEEDBACK: {rating} Stars - {comment}")
    # Show a simple Thank You HTML directly
    return HTMLResponse("""
        <body style="background:#141E30; color:white; display:flex; flex-direction:column; justify-content:center; align-items:center; height:100vh; font-family:sans-serif;">
            <h1 style="color:#00e676;">Thank You!</h1>
            <p>Your feedback has been recorded.</p>
            <a href="/" style="color:#00c6ff; margin-top:20px;">Return Home</a>
        </body>
    """)


# --- CARD 6: DATABASE (Simple Admin View) ---
@app.get("/database-view", response_class=HTMLResponse)
async def database_view(request: Request, db: Session = Depends(get_db)):
    # Simple stats for the user
    user_count = db.query(models.User).count()
    pass_count = db.query(models.SavedPassword).count()
    
    return HTMLResponse(f"""
        <body style="background:#141E30; color:white; font-family:sans-serif; padding:50px; text-align:center;">
            <h1>System Database Status</h1>
            <div style="background:rgba(255,255,255,0.1); padding:20px; border-radius:20px; display:inline-block; margin-top:20px;">
                <p><strong>Total Users:</strong> {user_count}</p>
                <p><strong>Total Passwords Vaulted:</strong> {pass_count}</p>
                <p style="color:#00e676;">Database Connection: Active (PostgreSQL)</p>
            </div>
            <br><br>
            <a href="/" style="color:#00c6ff;">Back to Home</a>
        </body>
    """)


@app.post("/setup-preferences", response_class=HTMLResponse)
async def setup_preferences(
    request: Request, 
    email: str = Form(...), 
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    # 1. Verify User
    user = crud.get_user_by_email(db, email=email)
    if not user or user.hashed_password != password:
        return templates.TemplateResponse("login.html", {"request": request, "error": "Access Denied"})

    # 2. Get Existing Preferences (if any)
    prefs = db.query(models.UserPreferences).filter(models.UserPreferences.user_id == user.id).first()

    return templates.TemplateResponse("preferences.html", {
        "request": request,
        "email": email,
        "password": password,
        "prefs": prefs  # Pass the data to HTML
    })

@app.post("/save-preferences", response_class=HTMLResponse)
async def save_preferences(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    # The New Fields from your screenshot
    nickname: str = Form(""), favourite_number: str = Form(""), hobby: str = Form(""),
    favourite_food: str = Form(""), favourite_sport: str = Form(""), favourite_subject: str = Form(""),
    favourite_book: str = Form(""), childhood_nickname: str = Form(""), favourite_celebrity: str = Form(""),
    sibling_position: str = Form(""), ambition: str = Form(""), favourite_place: str = Form(""),
    favourite_cafe: str = Form(""),
    db: Session = Depends(get_db)
):
    user = crud.get_user_by_email(db, email=email)
    
    # Get or Create Prefs
    prefs = db.query(models.UserPreferences).filter(models.UserPreferences.user_id == user.id).first()
    if not prefs:
        prefs = models.UserPreferences(user_id=user.id)
        db.add(prefs)
    
    # Update Data
    prefs.nickname = nickname
    prefs.favourite_number = favourite_number
    prefs.hobby = hobby
    prefs.favourite_food = favourite_food
    prefs.favourite_sport = favourite_sport
    prefs.favourite_subject = favourite_subject
    prefs.favourite_book = favourite_book
    prefs.childhood_nickname = childhood_nickname
    prefs.favourite_celebrity = favourite_celebrity
    prefs.sibling_position = sibling_position
    prefs.ambition = ambition
    prefs.favourite_place = favourite_place
    prefs.favourite_cafe = favourite_cafe

    db.commit()

    return templates.TemplateResponse("preferences.html", {
        "request": request,
        "email": email,
        "password": password,
        "prefs": prefs,
        "message": "AI Memory Updated Successfully!"
    })


# --- CARD 1: GENERATE FROM SAVED PREFERENCES ---

@app.post("/generate-from-db", response_class=HTMLResponse)
async def generate_from_db(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    user = crud.get_user_by_email(db, email=email)
    
    # 1. Check Preferences
    prefs = user.preferences

    # 2. If NO Preferences found -> Redirect to SURVEY PAGE (Register)
    # But we pre-fill their email/password so they don't have to type it again.
    if not prefs:
        return templates.TemplateResponse("register.html", {
            "request": request,
            "email": email,
            "password": password,
            # We need to send icons because register.html expects them
            "security_icons": random.sample(ICON_POOL, 5) 
        })

    # 3. If YES Preferences -> Generate & Show Recommendations
    user_survey_data = {
        "nickname": prefs.nickname,
        "favourite_number": prefs.favourite_number,
        # ... (rest of your mapping) ...
        "email": email,
        "password": password,
        "username": email.split('@')[0]
    }

    generated_passwords = generate_passwords_from_survey(user_survey_data)

    return templates.TemplateResponse("password_recommendations.html", {
        "request": request,
        "user_data": user_survey_data,
        "generated_passwords": generated_passwords,
        "social_media_options": ["Instagram", "Facebook", "Gmail", "Twitter", "TikTok", "Snapchat", "Reddit", "Threads", "Youtube", "LinkedIn"]
    })


if __name__ == "__main__":
    # Import the function from the new file we just created
    from ngrok_runner import run_fastapi_with_ngrok
    run_fastapi_with_ngrok(app_path="main:app", port=8000)