from fastapi import FastAPI, Form, File, UploadFile, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import google.generativeai as genai
import os
from io import BytesIO
import PyPDF2 as pdf
import json
from dotenv import load_dotenv


load_dotenv()

genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))


app = FastAPI()


templates = Jinja2Templates(directory="templates")
def input_pdf_text(uploaded_file: UploadFile):
    reader = pdf.PdfReader(uploaded_file.file)
    text = ""
    for page in range(len(reader.pages)):
        text += reader.pages[page].extract_text()
    return text



def get_gemini_response(input: str):
    model = genai.GenerativeModel('gemini-pro')
    response = model.generate_content(input)
    return response.text



@app.get("/", response_class=HTMLResponse)
async def serve_form(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})



@app.post("/evaluate_resume_form", response_class=HTMLResponse)
async def evaluate_resume_form(
        request: Request,
        job_description: str = Form(...),
        resume: UploadFile = File(...)
):
    resume_text = input_pdf_text(resume)
    input_prompt = f"""
    Act like a highly experienced Applicant Tracking System (ATS) with expertise in resume evaluation for all job fields (not limited to tech).
    Your job is to deeply evaluate resumes based on the provided job description (JD).
    Give detailed feedback with the following:
    1. Common mistakes in the resume, with reasons why they are problematic.
    2. Missing keywords that should be added, specific to the job description.
    3. Suggestions for improving the resume.
    4. A percentage match based on how well the resume aligns with the job description.

    Provide your response in JSON format with the following structure:
    {{
      "Mistakes": ["mistake1", "mistake2", ...],
      "MissingKeywords": ["keyword1", "keyword2", ...],
      "Suggestions": "Detailed suggestions here",
      "JD Match": percentage_as_integer
    }}

    resume: {resume_text}
    description: {job_description}
    """

    response = get_gemini_response(input_prompt)

    try:
        feedback = json.loads(response)
    except json.JSONDecodeError:

        feedback = {}

        # Extract mistakes
        mistakes_start = response.find('"Mistakes": [')
        if mistakes_start != -1:
            mistakes_end = response.find(']', mistakes_start)
            mistakes_str = response[mistakes_start + 12:mistakes_end]
            feedback['Mistakes'] = [m.strip()[1:-1] for m in mistakes_str.split(',')]

        # Extract missing keywords
        keywords_start = response.find('"MissingKeywords": [')
        if keywords_start != -1:
            keywords_end = response.find(']', keywords_start)
            keywords_str = response[keywords_start + 19:keywords_end]
            feedback['MissingKeywords'] = [k.strip()[1:-1] for k in keywords_str.split(',')]

        # Extract suggestions
        suggestions_start = response.find('"Suggestions": "')
        if suggestions_start != -1:
            suggestions_end = response.find('",', suggestions_start)
            feedback['Suggestions'] = response[suggestions_start + 15:suggestions_end]

        # Extract JD Match
        jd_match_start = response.find('"JD Match": ')
        if jd_match_start != -1:
            jd_match_end = response.find(',', jd_match_start)
            feedback['JD Match'] = response[jd_match_start + 11:jd_match_end].strip()

    return templates.TemplateResponse("index.html", {"request": request, "feedback": feedback})