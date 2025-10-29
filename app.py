import streamlit as st
import spacy
import fitz  # PyMuPDF
from docx import Document
import os
import re

# Check and download spaCy model if not present
@st.cache_resource
def load_spacy_model():
    try:
        nlp = spacy.load("en_core_web_sm")
    except OSError:
        st.info("Downloading spaCy model 'en_core_web_sm'. This may take a moment...")
        os.system("python -m spacy download en_core_web_sm")
        nlp = spacy.load("en_core_web_sm")
    return nlp

nlp = load_spacy_model()

# Function to extract text from PDF
def extract_text_from_pdf(file):
    doc = fitz.open(stream=file.read(), filetype="pdf")
    text = ""
    for page in doc:
        text += page.get_text()
    return text

# Function to extract text from DOCX
def extract_text_from_docx(file):
    doc = Document(file)
    text = ""
    for para in doc.paragraphs:
        text += para.text + "\n"
    return text

# Function to analyze keywords using spaCy
def analyze_keywords(text):
    doc = nlp(text)
    keywords = [token.text for token in doc if token.pos_ in ["NOUN", "PROPN", "ADJ"] and not token.is_stop]
    return list(set(keywords))  # Remove duplicates

# Function to extract keywords from job description
def extract_job_keywords(job_description):
    doc = nlp(job_description)
    job_keywords = [token.text.lower() for token in doc if token.pos_ in ["NOUN", "PROPN", "ADJ", "VERB"] and not token.is_stop]
    return list(set(job_keywords))

# Function to calculate match score
def calculate_match_score(job_keywords, matching_keywords):
    if not job_keywords:
        return 0.0
    return (len(matching_keywords) / len(job_keywords)) * 100

# Function to optimize resume without OpenAI (rule-based approach)
def optimize_resume_rule_based(resume_text, job_description):
    # Extract keywords from job description
    job_keywords = extract_job_keywords(job_description)

    # Analyze resume keywords
    resume_keywords = analyze_keywords(resume_text)

    # Find matching keywords
    matching_keywords = [kw for kw in resume_keywords if kw.lower() in job_keywords]

    # Calculate match score
    match_score = calculate_match_score(job_keywords, matching_keywords)

    # Simple optimization: restructure resume to highlight matching keywords
    lines = resume_text.split('\n')
    optimized_lines = []

    # Add a summary section with matching keywords
    if matching_keywords:
        optimized_lines.append("PROFESSIONAL SUMMARY")
        summary = f"Experienced professional with expertise in {', '.join(matching_keywords[:5])}."
        optimized_lines.append(summary)
        optimized_lines.append("")

    # Add the rest of the resume
    optimized_lines.extend(lines)

    # Add a skills section with matching keywords
    if matching_keywords:
        optimized_lines.append("")
        optimized_lines.append("SKILLS")
        optimized_lines.append(", ".join(matching_keywords))

    return "\n".join(optimized_lines), match_score, matching_keywords

# Streamlit UI
st.title("AI Resume Optimizer")

# Sidebar
st.sidebar.header("Instructions")
st.sidebar.write("""
1. Upload your resume (PDF or DOCX).
2. Enter the job description.
3. Click 'Optimize Resume'.
4. View extracted text, keywords, and optimized resume.
5. Download the optimized resume.
""")

# Option to choose optimization method
optimization_method = st.sidebar.radio("Optimization Method", ["Rule-based (Free)", "OpenAI API"])
api_key = ""
if optimization_method == "OpenAI API":
    api_key = st.sidebar.text_input("OpenAI API Key", type="password")

# Main content
uploaded_file = st.file_uploader("Upload Resume (PDF or DOCX)", type=["pdf", "docx"])
job_description = st.text_area("Job Description")

if st.button("Optimize Resume"):
    if optimization_method == "OpenAI API" and not api_key:
        st.error("Please enter your OpenAI API key.")
    elif not uploaded_file:
        st.error("Please upload a resume file.")
    elif not job_description:
        st.error("Please enter a job description.")
    else:
        # Extract text
        if uploaded_file.type == "application/pdf":
            resume_text = extract_text_from_pdf(uploaded_file)
        elif uploaded_file.type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
            resume_text = extract_text_from_docx(uploaded_file)
        else:
            st.error("Unsupported file type.")
            resume_text = None

        if resume_text:
            st.subheader("Extracted Resume Text")
            st.text_area("Resume Text", resume_text, height=200)

            # Analyze keywords
            resume_keywords = analyze_keywords(resume_text)
            job_keywords = extract_job_keywords(job_description)
            matching_keywords = [kw for kw in resume_keywords if kw.lower() in job_keywords]
            match_score = calculate_match_score(job_keywords, matching_keywords)

            st.subheader("Extracted Keywords")
            st.write(", ".join(resume_keywords))

            st.subheader("Matching Keywords")
            st.write(", ".join(matching_keywords) if matching_keywords else "No matching keywords found.")

            st.metric("Match Score", f"{match_score:.2f}%")

            # Optimize resume
            with st.spinner("Optimizing resume..."):
                if optimization_method == "Rule-based (Free)":
                    optimized_resume, _, _ = optimize_resume_rule_based(resume_text, job_description)
                else:
                    # Import OpenAI only when needed
                    from openai import OpenAI
                    client = OpenAI(api_key=api_key)
                    prompt = f"""
                    Optimize the following resume based on the job description. Make it more relevant by incorporating keywords from the job description, improving structure, and highlighting relevant experience.

                    Resume:
                    {resume_text}

                    Job Description:
                    {job_description}

                    Provide the optimized resume in a professional format.
                    """
                    try:
                        response = client.chat.completions.create(
                            model="gpt-3.5-turbo",
                            messages=[{"role": "user", "content": prompt}],
                            max_tokens=1500,
                            temperature=0.7
                        )
                        optimized_resume = response.choices[0].message.content.strip()
                    except Exception as e:
                        st.error(f"Error optimizing resume: {str(e)}")
                        optimized_resume = None

            if optimized_resume:
                st.subheader("Optimized Resume")
                st.text_area("Optimized Resume", optimized_resume, height=300)

                # Download button
                st.download_button(
                    label="Download Optimized Resume",
                    data=optimized_resume,
                    file_name="optimized_resume.txt",
                    mime="text/plain"
                )
            else:
                st.error("Resume optimization failed. Please check your OpenAI API key and ensure you have sufficient credits/quota. Visit https://platform.openai.com/account/billing to manage your billing.")
