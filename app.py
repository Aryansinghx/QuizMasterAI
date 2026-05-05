import streamlit as st
from groq import Groq
import os
import json
import PyPDF2
from datetime import date, datetime, timedelta
from dotenv import load_dotenv
import random
import re
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

# Import your custom logic
from utils.gamification import calculate_xp, update_streak
from utils.auth import init_db, get_user_stats, update_user_xp, register_user, authenticate_user

# 1. Configuration & Setup
load_dotenv()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))
st.set_page_config(page_title="Quiz Master AI", page_icon="🎓", layout="wide")

try:
    db = init_db()
except Exception as e:
    st.error("Firebase not connected. Check firebase-sdk.json")
    db = None

# 2. Session State Management
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'user_email' not in st.session_state:
    st.session_state.user_email = ""
if 'quiz_data' not in st.session_state:
    st.session_state.quiz_data = None
if 'summary_text' not in st.session_state:
    st.session_state.summary_text = ""
if 'flashcards' not in st.session_state:
    st.session_state.flashcards = None
if 'current_q' not in st.session_state:
    st.session_state.current_q = 0
if 'score' not in st.session_state:
    st.session_state.score = 0
if 'source_text' not in st.session_state:
    st.session_state.source_text = ""
if 'study_mode' not in st.session_state:
    st.session_state.study_mode = "Quiz"
if 'content_source' not in st.session_state:
    st.session_state.content_source = "Upload file"
if 'learning_topic' not in st.session_state:
    st.session_state.learning_topic = "General Study"
if 'difficulty' not in st.session_state:
    st.session_state.difficulty = "Medium"
if 'study_goal' not in st.session_state:
    st.session_state.study_goal = 10
if 'tutor_history' not in st.session_state:
    st.session_state.tutor_history = [{"role":"assistant","content":"Hello! I'm your study tutor. Ask me anything about your material."}]
if 'challenge_end' not in st.session_state:
    st.session_state.challenge_end = None
if 'timed_mode' not in st.session_state:
    st.session_state.timed_mode = False

# 3. Helper Functions
def extract_text_from_pdf(file):
    pdf_reader = PyPDF2.PdfReader(file)
    return "".join([page.extract_text() or "" for page in pdf_reader.pages])


def clean_text_for_prompt(text):
    if not text:
        return ""
    normalized = text.replace('"', "'").replace('\n', ' ').replace('\r', ' ')
    normalized = re.sub(r'\s+', ' ', normalized).strip()
    return normalized


def fetch_url_text(url):
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        request = Request(url, headers=headers)
        with urlopen(request, timeout=12) as response:
            raw_bytes = response.read()
        text = raw_bytes.decode("utf-8", errors="ignore")
        text = re.sub(r'<script.*?>.*?</script>', '', text, flags=re.S)
        text = re.sub(r'<style.*?>.*?</style>', '', text, flags=re.S)
        text = re.sub(r'<[^>]+>', ' ', text)
        return clean_text_for_prompt(text)
    except (URLError, HTTPError, ValueError):
        return None
    except Exception:
        return None


def create_ai_completion(messages, response_format=None, temperature=0.2):
    try:
        if response_format:
            completion = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=messages,
                temperature=temperature,
                response_format=response_format
            )
        else:
            completion = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=messages,
                temperature=temperature
            )
        return completion.choices[0].message.content
    except Exception as e:
        st.error(f"AI request failed: {e}")
        return None


def parse_json_output(raw_content):
    if isinstance(raw_content, dict):
        return raw_content
    if not isinstance(raw_content, str):
        return None
    try:
        return json.loads(raw_content)
    except json.JSONDecodeError:
        match = re.search(r'(\{.*\})', raw_content, flags=re.S)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                return None
        return None


def generate_quiz(text, learning_topic="General Study", difficulty="Medium", question_style="Mixed", question_count=10):
    clean_text = clean_text_for_prompt(text)[:3800]
    prompt = f"""
    Create {question_count} university-level {difficulty} quiz questions about the topic '{learning_topic}' using the text below.
    Use {question_style} question style and output only valid JSON.

    Output structure:
    {{
      "quiz": [
        {{"question":"...","answer":"...","explanation":"...","type":"..."}}
      ]
    }}

    Material:
    {clean_text}
    """

    messages = [
        {"role": "system", "content": "You are an academic quiz generator who only returns valid JSON."},
        {"role": "user", "content": prompt}
    ]

    raw_content = create_ai_completion(messages, response_format={"type": "json_object"})
    if not raw_content:
        return None

    raw_data = parse_json_output(raw_content)
    questions = []
    if isinstance(raw_data, dict) and "quiz" in raw_data and isinstance(raw_data["quiz"], list):
        questions = raw_data["quiz"]
    elif isinstance(raw_data, list):
        questions = raw_data
    elif isinstance(raw_data, dict):
        for value in raw_data.values():
            if isinstance(value, list):
                questions = value
                break

    final_quiz = []
    for q in questions:
        if isinstance(q, dict):
            final_quiz.append({
                "question": q.get("question") or q.get("q") or "Missing Question",
                "answer": q.get("answer") or q.get("a") or "No answer provided",
                "explanation": q.get("explanation") or q.get("e") or "No explanation",
                "type": q.get("type") or q.get("format") or "Short Answer"
            })

    return final_quiz if len(final_quiz) > 0 else None


def generate_flashcards(text, learning_topic="General Study", flashcard_count=10):
    clean_text = clean_text_for_prompt(text)[:3800]
    prompt = f"""
    From the material below, create {flashcard_count} flashcards for the topic '{learning_topic}'.
    Output only valid JSON with this structure:
    {{
      "flashcards": [
        {{"question":"...","answer":"..."}}
      ]
    }}

    Material:
    {clean_text}
    """

    messages = [
        {"role": "system", "content": "You are an academic flashcard creator and return valid JSON only."},
        {"role": "user", "content": prompt}
    ]

    raw_content = create_ai_completion(messages, response_format={"type": "json_object"})
    if not raw_content:
        return None

    raw_data = parse_json_output(raw_content)
    if isinstance(raw_data, dict) and "flashcards" in raw_data and isinstance(raw_data["flashcards"], list):
        return raw_data["flashcards"]
    return None


def generate_summary(text, learning_topic="General Study", difficulty="Medium"):
    clean_text = clean_text_for_prompt(text)[:3800]
    prompt = f"""
    Summarize the main ideas from the following material for a student studying '{learning_topic}' at a {difficulty} level.
    Focus on key concepts, definitions, and high-impact review points.

    Material:
    {clean_text}
    """

    messages = [
        {"role": "system", "content": "You are an academic summarizer that creates concise, exam-ready study notes."},
        {"role": "user", "content": prompt}
    ]

    raw_content = create_ai_completion(messages, temperature=0.15)
    if isinstance(raw_content, str):
        return raw_content.strip()
    return None


def evaluate_answer(question, model_answer, student_answer):
    prompt = f"""
    You are an academic grader. Evaluate the student answer and compare it to the model answer.

    Question: {question}
    Model answer: {model_answer}
    Student answer: {student_answer}

    Return JSON only with keys: score, feedback, strengths, missing_points.
    Score should be an integer between 0 and 100.
    """

    messages = [
        {"role": "system", "content": "You are an objective grader that returns valid JSON only."},
        {"role": "user", "content": prompt}
    ]

    raw_content = create_ai_completion(messages, response_format={"type": "json_object"})
    data = parse_json_output(raw_content)
    if not data:
        return {
            "score": 0,
            "feedback": "Could not generate an evaluation at this time.",
            "strengths": "",
            "missing_points": ""
        }
    return {
        "score": int(data.get("score", 0)),
        "feedback": data.get("feedback", ""),
        "strengths": data.get("strengths", ""),
        "missing_points": data.get("missing_points", "")
    }


def tutor_response(history, user_message):
    system_prompt = {
        "role": "system",
        "content": "You are an empathetic academic tutor. Help the student understand concepts clearly, provide examples, and keep your answers concise and friendly."
    }
    messages = [system_prompt] + history + [{"role": "user", "content": user_message}]
    raw_content = create_ai_completion(messages, temperature=0.25)
    return raw_content or "I'm sorry, I couldn't answer that right now."


def get_achievements(stats):
    xp = stats.get("xp", 0)
    streak = stats.get("streak", 0)
    level = stats.get("level", 1)
    badges = []
    if xp >= 100:
        badges.append("Quiz Apprentice")
    if xp >= 300:
        badges.append("Study Challenger")
    if xp >= 700:
        badges.append("Knowledge Champion")
    if streak >= 3:
        badges.append("3-Day Streak")
    if streak >= 7:
        badges.append("Weekly Warrior")
    if level >= 5:
        badges.append("Honor Scholar")
    return badges


def calculate_level(xp):
    return (xp // 100) + 1


def reset_study_session():
    st.session_state.quiz_data = None
    st.session_state.summary_text = ""
    st.session_state.flashcards = None
    st.session_state.source_text = ""
    st.session_state.current_q = 0
    st.session_state.score = 0
    st.session_state.challenge_end = None
    st.session_state.timed_mode = False
    for key in list(st.session_state.keys()):
        if key.startswith("submitted_") or key.startswith("eval_") or key.startswith("ans_"):
            del st.session_state[key]


# 4. Step 1: Login/Sign-Up View
if not st.session_state.logged_in:
    st.markdown("""
    <style>
    .login-container {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 40px;
        border-radius: 15px;
        color: white;
        margin-bottom: 30px;
    }
    .login-title {
        font-size: 2.8em;
        font-weight: 700;
        margin: 0;
        text-align: center;
    }
    .login-subtitle {
        font-size: 1.2em;
        text-align: center;
        margin-top: 10px;
        opacity: 0.95;
    }
    .feature-box {
        background: rgba(255,255,255,0.15);
        padding: 20px;
        border-radius: 10px;
        border-left: 4px solid #00d4ff;
        margin: 15px 0;
        backdrop-filter: blur(10px);
    }
    .feature-title {
        font-weight: 600;
        font-size: 1.1em;
        margin-bottom: 8px;
    }
    .form-card {
        background: white;
        padding: 35px;
        border-radius: 12px;
        box-shadow: 0 8px 25px rgba(0,0,0,0.1);
    }
    .tab-container {
        border-bottom: 2px solid #e0e0e0;
    }
    </style>
    """, unsafe_allow_html=True)
    
    st.markdown("""<div class="login-container">
        <div class="login-title">🎓 Quiz Master AI</div>
        <div class="login-subtitle">Master Your Subjects with Intelligent Quiz Generation</div>
    </div>""", unsafe_allow_html=True)

    info_col, form_col = st.columns([1, 1.2], gap="large")
    
    with info_col:
        st.markdown("### ✨ Why Join?", unsafe_allow_html=True)
        st.markdown("""<div class="feature-box">
            <div class="feature-title">🏆 Track Progress</div>
            Save XP, streaks, and level up as you study
        </div>""", unsafe_allow_html=True)
        
        st.markdown("""<div class="feature-box">
            <div class="feature-title">📚 Smart Quizzes</div>
            AI-generated quizzes from PDFs, notes, and web content
        </div>""", unsafe_allow_html=True)
        
        st.markdown("""<div class="feature-box">
            <div class="feature-title">🎯 Personalized Learning</div>
            Adaptive difficulty and multiple study modes
        </div>""", unsafe_allow_html=True)
        
        st.markdown("""<div class="feature-box">
            <div class="feature-title">🤖 AI Tutor</div>
            Ask follow-up questions and get instant explanations
        </div>""", unsafe_allow_html=True)

    with form_col:
        login_tab, signup_tab = st.tabs(["🔐 Login", "✍️ Sign Up"])

        with login_tab:
            st.markdown("### Welcome Back!", unsafe_allow_html=True)
            with st.form(key="login_form"):
                login_email = st.text_input(
                    "📧 University Email",
                    placeholder="your.name@university.edu",
                    key="login_email",
                    help="Use your registered university email"
                )
                login_password = st.text_input(
                    "🔑 Password",
                    type="password",
                    key="login_password",
                    help="8+ characters for security"
                )
                st.markdown("")
                login_button = st.form_submit_button("🚀 Login Now", use_container_width=True)

            if login_button:
                if not login_email or "@" not in login_email:
                    st.warning("⚠️ Please enter a valid university email.")
                elif not login_password or len(login_password) < 8:
                    st.warning("⚠️ Password must be at least 8 characters long.")
                elif not db:
                    st.error("❌ Authentication is unavailable because Firebase failed to connect.")
                else:
                    success, message = authenticate_user(db, login_email.strip().lower(), login_password)
                    if success:
                        st.success("✅ Login successful! Redirecting...")
                        st.session_state.user_email = login_email.strip().lower()
                        st.session_state.logged_in = True
                        st.rerun()
                    else:
                        st.error(f"❌ {message}")

        with signup_tab:
            st.markdown("### Join the Community!", unsafe_allow_html=True)
            with st.form(key="signup_form"):
                signup_email = st.text_input(
                    "📧 University Email",
                    placeholder="your.name@university.edu",
                    key="signup_email",
                    help="This will be your unique username"
                )
                signup_password = st.text_input(
                    "🔑 Password",
                    type="password",
                    key="signup_password",
                    help="Use a strong password (8+ characters recommended)"
                )
                confirm_password = st.text_input(
                    "🔑 Confirm Password",
                    type="password",
                    key="confirm_password",
                    help="Must match your password"
                )
                st.markdown("")
                signup_button = st.form_submit_button("🎉 Create Account", use_container_width=True)

            if signup_button:
                if not signup_email or "@" not in signup_email:
                    st.warning("⚠️ Please enter a valid university email.")
                elif not signup_password or len(signup_password) < 8:
                    st.warning("⚠️ Password must be at least 8 characters long.")
                elif signup_password != confirm_password:
                    st.warning("⚠️ Passwords do not match. Please try again.")
                elif not db:
                    st.error("❌ Authentication is unavailable because Firebase failed to connect.")
                else:
                    success, message = register_user(db, signup_email.strip().lower(), signup_password)
                    if success:
                        st.success("✅ Account created! Logging in...")
                        st.session_state.user_email = signup_email.strip().lower()
                        st.session_state.logged_in = True
                        st.rerun()
                    else:
                        st.error(f"❌ {message}")

# 5. Step 2: Main App
else:
    st.markdown("""
    <style>
    .sidebar-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 20px;
        border-radius: 12px;
        color: white;
        margin-bottom: 15px;
        text-align: center;
    }
    .sidebar-title {
        font-size: 1.3em;
        font-weight: 700;
        margin-bottom: 5px;
    }
    .sidebar-subtitle {
        font-size: 0.9em;
        opacity: 0.9;
    }
    .stat-badge {
        background: rgba(255,255,255,0.2);
        padding: 10px;
        border-radius: 8px;
        margin: 8px 0;
        font-weight: 600;
    }
    .achievement-badge {
        background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
        padding: 12px;
        border-radius: 8px;
        color: white;
        margin: 8px 0;
        text-align: center;
        font-weight: 600;
        font-size: 0.9em;
    }
    </style>
    """, unsafe_allow_html=True)

    with st.sidebar:
        st.markdown('<div class="sidebar-card"><div class="sidebar-title">👤 Player Profile</div></div>', unsafe_allow_html=True)
        
        if db:
            stats = get_user_stats(db, st.session_state.user_email)
        else:
            stats = {"xp": 0, "streak": 0, "level": 1}

        level = stats.get("level", calculate_level(stats.get("xp", 0)))
        email_short = st.session_state.user_email.split("@")[0]
        
        st.markdown(f'<div class="stat-badge">📧 {email_short}</div>', unsafe_allow_html=True)
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("⭐ Level", f"{level}", delta=None)
        with col2:
            st.metric("🔥 Streak", f"{stats.get('streak', 0)} days", delta=None)
        
        st.metric("💎 Total XP", stats.get("xp", 0), delta=None)
        
        xp_progress = (stats.get("xp", 0) % 100) / 100
        st.progress(xp_progress, text=f"Next Level: {int(xp_progress*100)}%")

        st.markdown("---")
        st.markdown("### 🎮 Study Settings")
        st.session_state.study_mode = st.radio(
            "Study Mode",
            ["Quiz", "Flashcards", "Summary", "AI Tutor", "Timed Challenge"],
            index=["Quiz", "Flashcards", "Summary", "AI Tutor", "Timed Challenge"].index(st.session_state.study_mode)
        )
        st.session_state.content_source = st.radio(
            "Input Source",
            ["Upload file", "Paste text", "URL"],
            index=["Upload file", "Paste text", "URL"].index(st.session_state.content_source)
        )
        st.session_state.learning_topic = st.text_input("📚 Topic", value=st.session_state.learning_topic)
        st.session_state.difficulty = st.selectbox(
            "📊 Difficulty",
            ["Easy", "Medium", "Hard"],
            index=["Easy", "Medium", "Hard"].index(st.session_state.difficulty)
        )
        st.session_state.study_goal = st.slider("🎯 Questions", 5, 20, value=int(st.session_state.study_goal))

        st.markdown("---")
        with st.expander("🏆 Achievements", expanded=True):
            badges = get_achievements(stats)
            if badges:
                for badge in badges:
                    st.markdown(f'<div class="achievement-badge">✨ {badge}</div>', unsafe_allow_html=True)
            else:
                st.markdown('<div style="text-align: center; color: #999; padding: 15px;"><p>Keep studying to unlock badges!</p></div>', unsafe_allow_html=True)

        st.markdown("---")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔄 Reset", use_container_width=True):
                reset_study_session()
                st.rerun()
        with col2:
            if st.button("🚪 Logout", use_container_width=True):
                st.session_state.logged_in = False
                reset_study_session()
                st.rerun()

    st.markdown("""
    <style>
    .dashboard-header {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 30px;
        border-radius: 12px;
        color: white;
        margin-bottom: 25px;
        text-align: center;
    }
    .dashboard-title {
        font-size: 2.2em;
        font-weight: 700;
        margin: 0;
    }
    .dashboard-subtitle {
        font-size: 1em;
        opacity: 0.95;
        margin-top: 8px;
    }
    </style>
    """, unsafe_allow_html=True)
    
    st.markdown("""<div class="dashboard-header">
        <div class="dashboard-title">📚 Study Dashboard</div>
        <div class="dashboard-subtitle">Choose content source, generate study material, or chat with the AI tutor</div>
    </div>""", unsafe_allow_html=True)

    if st.session_state.content_source == "Upload file":
        st.markdown("### 📤 Upload Study Material")
        uploaded_file = st.file_uploader(
            "Drop your PDF or TXT file here", type=["pdf", "txt"], key="uploaded_file",
            help="Supported formats: PDF, TXT (max 50MB)"
        )
        if uploaded_file:
            file_bytes = uploaded_file.read()
            if uploaded_file.name.lower().endswith("pdf"):
                import io
                text = extract_text_from_pdf(io.BytesIO(file_bytes))
            else:
                text = file_bytes.decode("utf-8", errors="ignore")
            st.session_state.source_text = text
            st.success(f"✅ Loaded: {uploaded_file.name}")

    elif st.session_state.content_source == "Paste text":
        st.markdown("### 📝 Paste Your Notes")
        pasted_text = st.text_area(
            "Paste your lecture notes, study guide, or any text content", 
            value=st.session_state.source_text, 
            height=220, 
            key="paste_text",
            placeholder="Your study material goes here... You can paste lecture notes, textbook excerpts, or any academic content."
        )
        st.session_state.source_text = pasted_text

    else:
        st.markdown("### 🌐 Fetch from URL")
        source_url = st.text_input(
            "Enter website URL", 
            value=st.session_state.get("source_url", ""), 
            key="source_url",
            placeholder="https://example.com/study-page",
            help="Enter a URL to extract text from a webpage"
        )
        if st.button("🔗 Fetch Content", key="fetch_url", use_container_width=True):
            if not source_url:
                st.warning("⚠️ Please enter a valid URL")
            else:
                with st.spinner("🔄 Extracting content..."):
                    fetched = fetch_url_text(source_url)
                if fetched:
                    st.session_state.source_text = fetched
                    st.success("✅ Web content loaded successfully!")
                else:
                    st.error("❌ Unable to extract text from that URL. Try another source.")

    if st.session_state.source_text:
        with st.expander(f"📋 Preview Content ({len(st.session_state.source_text)} chars)", expanded=False):
            st.markdown("""
            <div style="background: #f5f7fa; padding: 15px; border-radius: 8px; border-left: 4px solid #667eea;">
            """, unsafe_allow_html=True)
            st.write(
                st.session_state.source_text[:2000]
                + ("... *(truncated)*" if len(st.session_state.source_text) > 2000 else "")
            )
            st.markdown("</div>", unsafe_allow_html=True)

    needs_generation = st.session_state.study_mode != "AI Tutor"
    if needs_generation:
        st.markdown("### ✨ Generate Study Material")
        if st.button("🚀 Generate Now", key="generate_material", use_container_width=True):
            if not st.session_state.source_text:
                st.warning("⚠️ Please provide source material before generating.")
            else:
                if st.session_state.study_mode in ["Quiz", "Timed Challenge"]:
                    generated = generate_quiz(
                        st.session_state.source_text,
                        learning_topic=st.session_state.learning_topic,
                        difficulty=st.session_state.difficulty,
                        question_style="Mixed",
                        question_count=st.session_state.study_goal,
                    )
                    if generated:
                        st.session_state.quiz_data = generated
                        st.session_state.current_q = 0
                        st.session_state.score = 0
                        if st.session_state.study_mode == "Timed Challenge":
                            duration_map = {"Easy": 420, "Medium": 600, "Hard": 900}
                            st.session_state.timed_mode = True
                            st.session_state.challenge_end = datetime.now() + timedelta(seconds=duration_map.get(st.session_state.difficulty, 600))
                        st.rerun()
                    else:
                        st.error("Failed to generate quiz content. Try a shorter input or a different source.")

                elif st.session_state.study_mode == "Flashcards":
                    cards = generate_flashcards(
                        st.session_state.source_text,
                        learning_topic=st.session_state.learning_topic,
                        flashcard_count=st.session_state.study_goal,
                    )
                    if cards:
                        st.session_state.flashcards = cards
                        st.rerun()
                    else:
                        st.error("Unable to generate flashcards from this material.")

                elif st.session_state.study_mode == "Summary":
                    summary = generate_summary(
                        st.session_state.source_text,
                        learning_topic=st.session_state.learning_topic,
                        difficulty=st.session_state.difficulty,
                    )
                    if summary:
                        st.session_state.summary_text = summary
                        st.rerun()
                    else:
                        st.error("Unable to generate a summary. Try a shorter source or different topic.")

    if st.session_state.study_mode == "AI Tutor":
        st.subheader("🧠 AI Tutor")
        st.write(
            "Ask follow-up questions, request examples, or get explanations based on your loaded material."
        )
        if st.session_state.source_text:
            st.info("Tutor is using your loaded material as context.")

        for message in st.session_state.tutor_history:
            if message["role"] == "assistant":
                st.chat_message("assistant").write(message["content"])
            else:
                st.chat_message("user").write(message["content"])

        user_query = st.chat_input("Ask your AI tutor anything about the topic...")
        if user_query:
            st.session_state.tutor_history.append({"role": "user", "content": user_query})
            answer = tutor_response(st.session_state.tutor_history, user_query)
            st.session_state.tutor_history.append({"role": "assistant", "content": answer})
            st.rerun()

    elif st.session_state.study_mode == "Flashcards":
        st.subheader("📇 Flashcard Review")
        if st.session_state.flashcards:
            for idx, card in enumerate(st.session_state.flashcards, start=1):
                with st.expander(f"Flashcard {idx}: {card.get('question', 'Untitled')}"):
                    st.write(card.get("answer", "No answer available."))
        else:
            st.info("Generate flashcards to begin reviewing key facts.")

    elif st.session_state.study_mode == "Summary":
        st.subheader("📝 Study Summary")
        if st.session_state.summary_text:
            st.write(st.session_state.summary_text)
        else:
            st.info("Generate a summary to see the key ideas from your material.")

    elif st.session_state.study_mode in ["Quiz", "Timed Challenge"]:
        st.markdown("""
        <style>
        .quiz-header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 25px;
            border-radius: 12px;
            color: white;
            margin-bottom: 25px;
            text-align: center;
        }
        .question-box {
            background: linear-gradient(to right, #f5f7fa 0%, #c3cfe2 100%);
            padding: 30px;
            border-radius: 12px;
            border-left: 5px solid #667eea;
            margin: 20px 0;
        }
        .answer-box {
            background: white;
            padding: 20px;
            border-radius: 10px;
            border: 2px solid #e0e0e0;
            margin: 15px 0;
            transition: all 0.3s ease;
        }
        .score-card {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 25px;
            border-radius: 12px;
            color: white;
            text-align: center;
            margin: 20px 0;
        }
        .feedback-box {
            background: #f8f9fa;
            padding: 18px;
            border-radius: 10px;
            border-left: 4px solid #00d4ff;
            margin: 15px 0;
        }
        .strengths-box {
            background: #e8f5e9;
            padding: 18px;
            border-radius: 10px;
            border-left: 4px solid #4caf50;
            margin: 15px 0;
        }
        .missing-box {
            background: #fff3e0;
            padding: 18px;
            border-radius: 10px;
            border-left: 4px solid #ff9800;
            margin: 15px 0;
        }
        .timer-warning {
            background: #ffebee;
            padding: 15px;
            border-radius: 10px;
            border: 2px solid #f44336;
            color: #c62828;
            text-align: center;
            font-weight: bold;
            margin: 15px 0;
        }
        </style>
        """, unsafe_allow_html=True)
        
        if st.session_state.quiz_data:
            quiz = st.session_state.quiz_data
            q_idx = st.session_state.current_q
            progress_val = q_idx / len(quiz) if len(quiz) > 0 else 0
            
            st.markdown(f"""<div class="quiz-header">
                <h2>📝 Question {q_idx + 1} of {len(quiz)}</h2>
            </div>""", unsafe_allow_html=True)
            
            progress_percent = int(progress_val * 100)
            st.progress(progress_val, text=f"Progress: {progress_percent}%")

            if st.session_state.timed_mode and st.session_state.challenge_end:
                remaining = st.session_state.challenge_end - datetime.now()
                if remaining.total_seconds() > 0:
                    minutes = int(remaining.total_seconds() // 60)
                    seconds = int(remaining.total_seconds() % 60)
                    if remaining.total_seconds() < 300:  # Less than 5 minutes
                        st.markdown(f"""<div class="timer-warning">
                            ⏱️ TIME WARNING: {minutes}:{seconds:02d} remaining
                        </div>""", unsafe_allow_html=True)
                    else:
                        col1, col2, col3 = st.columns([1, 2, 1])
                        with col2:
                            st.metric("⏱️ Time Remaining", f"{minutes}:{seconds:02d}")
                else:
                    st.error("⏰ Time's up! This timed challenge has ended.")
                    st.session_state.timed_mode = False

            active_question = q_idx < len(quiz) and (not st.session_state.timed_mode or (st.session_state.challenge_end and (st.session_state.challenge_end - datetime.now()).total_seconds() > 0))
            if active_question:
                current_q = quiz[q_idx]
                if isinstance(current_q, dict) and "question" in current_q:
                    st.markdown(f"""<div class="question-box">
                        <h3>❓ {current_q['question']}</h3>
                        <p><small><em>Type: {current_q.get('type', 'Short Answer')}</em></small></p>
                    </div>""", unsafe_allow_html=True)

                    user_answer = st.text_area(
                        "✍️ Your Answer",
                        height=220,
                        key=f"ans_{q_idx}",
                        placeholder="Write your detailed answer here... Explain your reasoning, provide examples, and connect ideas.",
                        help="Aim for a comprehensive answer that demonstrates understanding"
                    )

                    if not st.session_state.get(f"submitted_{q_idx}"):
                        col1, col2, col3 = st.columns([1, 1.5, 1])
                        with col2:
                            if st.button("🚀 Submit & Get Feedback", key=f"submit_{q_idx}", use_container_width=True):
                                if not user_answer or len(user_answer) < 40:
                                    st.warning("✍️ Please write a more detailed answer (at least 40 characters) before submission.")
                                else:
                                    with st.spinner("🤖 AI is evaluating your answer..."):
                                        result = evaluate_answer(
                                            current_q["question"],
                                            current_q.get("answer", ""),
                                            user_answer,
                                        )
                                        st.session_state[f"submitted_{q_idx}"] = True
                                        st.session_state[f"eval_{q_idx}"] = result
                                    st.rerun()

                    if st.session_state.get(f"submitted_{q_idx}"):
                        evaluation = st.session_state.get(f"eval_{q_idx}", {})
                        st.divider()
                        
                        score = evaluation.get('score', 0)
                        score_color = "#4caf50" if score >= 75 else "#ff9800" if score >= 50 else "#f44336"
                        
                        st.markdown(f"""<div class="score-card" style="background: linear-gradient(135deg, {score_color} 0%, {score_color}dd 100%);">
                            <h2>📊 AI Score: {score}/100</h2>
                            <p style="font-size: 1.1em; margin: 10px 0;">
                                {"🌟 Excellent!" if score >= 85 else "👍 Good!" if score >= 75 else "📈 Keep Improving" if score >= 50 else "💪 Try Again"}
                            </p>
                        </div>""", unsafe_allow_html=True)
                        
                        with st.expander("📋 AI Feedback", expanded=True):
                            st.markdown(f"""<div class="feedback-box">
                                {evaluation.get("feedback", "No feedback available.")}
                            </div>""", unsafe_allow_html=True)
                        
                        with st.expander("✅ Your Strengths", expanded=False):
                            st.markdown(f"""<div class="strengths-box">
                                {evaluation.get("strengths", "No strengths identified.")}
                            </div>""", unsafe_allow_html=True)
                        
                        with st.expander("📌 Areas to Improve", expanded=False):
                            st.markdown(f"""<div class="missing-box">
                                {evaluation.get("missing_points", "No missing points detected.")}
                            </div>""", unsafe_allow_html=True)

                        st.divider()
                        col1, col2, col3 = st.columns([1, 1.5, 1])
                        with col2:
                            if st.button("➡️ Next Question", key=f"next_{q_idx}", use_container_width=True):
                                if evaluation.get("score", 0) >= 65:
                                    st.session_state.score += 1
                                st.session_state.current_q += 1
                                st.rerun()
                else:
                    st.error(f"⚠️ Data formatting error at Question {q_idx + 1}.")
                    if st.button("Skip Question"):
                        st.session_state.current_q += 1
                        st.rerun()
            else:
                st.success("🎉 Study session complete!")
                final_score = st.session_state.score
                difficulty_multiplier = {"Easy": 1.0, "Medium": 1.5, "Hard": 2.0}.get(st.session_state.difficulty, 1.2)
                final_xp = calculate_xp(final_score, len(quiz), difficulty_multiplier=difficulty_multiplier)
                
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown(f"""<div class="score-card">
                        <h3>📈 Final Score</h3>
                        <h2>{final_score}/{len(quiz)}</h2>
                        <p>{int((final_score/len(quiz))*100)}% Correct</p>
                    </div>""", unsafe_allow_html=True)
                with col2:
                    st.markdown(f"""<div class="score-card" style="background: linear-gradient(135deg, #00d4ff 0%, #0099cc 100%);">
                        <h3>⭐ XP Earned</h3>
                        <h2>+{final_xp}</h2>
                        <p>{"Level Up! 🚀" if final_xp > 100 else "Great Job! 💪"}</p>
                    </div>""", unsafe_allow_html=True)

                st.divider()
                col1, col2, col3 = st.columns([1, 1.5, 1])
                with col2:
                    if st.button("💾 Save Progress & Finish", key="sync_finish", use_container_width=True):
                        if db:
                            update_user_xp(db, st.session_state.user_email, final_xp)
                        reset_study_session()
                        st.balloons()
                        st.rerun()
        else:
            st.markdown("""
            <div style="text-align: center; padding: 40px;">
                <h2>📚 Ready to Quiz?</h2>
                <p style="font-size: 1.1em; color: #666;">Generate a quiz to begin your adaptive review session.</p>
            </div>
            """, unsafe_allow_html=True)
