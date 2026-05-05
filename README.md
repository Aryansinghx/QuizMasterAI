# 🚀 QuizMasterAI / QuizEducator

🌐 **Live Demo:** https://quizeducator12.streamlit.app/

QuizMasterAI (QuizEducator) is an AI-powered learning platform that transforms any content into an interactive quiz.  
Simply upload a PDF, paste text, or provide a link — and instantly generate questions to enhance learning through active recall.

---

## ✨ Features

- 📄 **PDF Upload → Quiz Generation**  
  Convert study materials into structured questions instantly  

- 🔗 **URL to Quiz**  
  Paste blog/article links and generate quizzes automatically  

- 📝 **Text Input Support**  
  Add your own notes and test yourself in seconds  

- 🧠 **AI-Based Question Generation**  
  - Multiple Choice Questions (MCQs)  
  - Conceptual Questions  
  - Short Answer Questions  

- ⚡ **Fast & Interactive UI**  
  Built with Streamlit for smooth real-time interaction  

---

## 💡 Use Cases

- 📚 Exam revision and last-minute practice  
- 👨‍💻 Learning from technical documentation  
- 📖 Self-testing for better retention  
- 🎓 Students, developers, and lifelong learners  

---

## 🛠️ Tech Stack

**Language:** Python  
**Framework:** Streamlit  
**AI Integration:** OpenAI API  
**PDF Processing:** PyPDF / pdfplumber  
**Web Scraping:** BeautifulSoup / Requests  

> Streamlit allows building interactive web apps directly using Python with minimal setup and fast deployment :contentReference[oaicite:2]{index=2}  

---

## ⚙️ Installation & Setup

### 1️⃣ Clone the Repository
```bash
git clone https://github.com/your-username/quizmasterai.git
cd quizmasterai

### 2️⃣ Create Virtual Environment
```bash
python -m venv venv
source venv/bin/activate   # Mac/Linux
venv\Scripts\activate      # Windows

### 3️⃣ Install Dependencies
```bash
pip install -r requirements.txt

### 4️⃣ Add Environment Variables
```env
OPENAI_API_KEY=your_api_key_here

### 5️⃣ Run the App
```bash
streamlit run app.py

### 📂 Project Structure
quizmasterai/
│── app.py
│── requirements.txt
│── utils/
│   ├── pdf_parser.py
│   ├── quiz_generator.py
│   ├── web_scraper.py
│── data/
│── .env

