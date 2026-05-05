import google.generativeai as genai
import json
import os

def generate_quiz_data(text):
    model = genai.GenerativeModel('gemini-1.5-flash')
    
    prompt = f"""
    Act as an educational expert. Based on the text provided, generate 3 unique multiple-choice questions.
    Return the output strictly in valid JSON format as a list of objects.
    Each object must have: 'question', 'options' (list of 4), 'answer' (the exact correct string), and 'explanation'.
    
    Text: {text[:2000]}  # Limiting text to avoid token limits
    """
    
    response = model.generate_content(prompt)
    # Clean the response to ensure it's pure JSON
    json_data = response.text.replace('```json', '').replace('```', '').strip()
    return json.loads(json_data)