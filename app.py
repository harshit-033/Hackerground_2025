from flask import Flask, render_template, request, jsonify, send_file
import google.generativeai as genai
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
import tempfile, os, json, re

app = Flask(__name__)

genai.configure(api_key=os.getenv('GEMINI_API_KEY', 'AIzaSyB0MN0OS_Djzb8k862CbHv8Dyfkp5xhtgo'))
model = genai.GenerativeModel('gemini-1.5-flash')

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/resume-analyzer')
def resume_page():
    return render_template('resume_analyzer.html')

@app.route('/job-search')
def job_page():
    return render_template('job_search.html')

def try_parse_json(text):
    # Try to find a JSON object inside the model text
    text = text.strip()
    # Quick check if text is pure JSON:
    try:
        return json.loads(text)
    except Exception:
        pass
    # Attempt to extract JSON substring using braces
    m = re.search(r'\{[\s\S]*\}$', text)
    if m:
        try:
            return json.loads(m.group(0))
        except Exception:
            pass
    return None

@app.route('/api/analyze_resume', methods=['POST'])
def analyze_resume():
    data = request.get_json() or {}
    resume = data.get('resume', '')
    job_desc = data.get('job_description', '')
    if not resume or not job_desc:
        return jsonify({'error': 'Resume and Job Description are required.'}), 400

    prompt = f"""You are an AI Resume Analyzer.
Compare the following RESUME and JOB DESCRIPTION.

RESUME:
{resume}

JOB DESCRIPTION:
{job_desc}

Tasks:
1. Provide a match score (0-100%).
2. List missing skills or keywords.
3. Suggest 3 bullet-point improvements to the resume.
4. Provide a short summary.
Return the result in JSON format with keys: match_score, missing_skills (list), improvements (list), summary.
If you cannot produce JSON, still return a clear plain-text analysis.
"""

    try:
        response = model.generate_content(prompt)
        text = response.text
        parsed = try_parse_json(text)
        if parsed:
            return jsonify({'structured': parsed, 'raw': text})
        else:
            return jsonify({'raw': text})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/search_jobs', methods=['POST'])
def search_jobs():
    data = request.get_json() or {}
    qualifications = data.get('qualifications', '')
    achievements = data.get('achievements', '')
    if not qualifications:
        return jsonify({'error': 'Qualifications required.'}), 400

    prompt = f"""You are a career advisor AI.
Based on the following qualifications and achievements, suggest 6 suitable job roles.
For each role, give a one-line description and 2 small resume improvements to match that role.
Return the result as JSON list where each item: {{'role':..., 'description':..., 'improvements':[...]}}
If JSON is not possible, return human-readable text.
QUALIFICATIONS:
{qualifications}

ACHIEVEMENTS:
{achievements}
"""

    try:
        response = model.generate_content(prompt)
        text = response.text
        parsed = try_parse_json(text)
        if parsed:
            return jsonify({'structured': parsed, 'raw': text})
        else:
            return jsonify({'raw': text})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/generate_pdf', methods=['POST'])
def generate_pdf_endpoint():
    data = request.get_json() or {}
    # Accept structured JSON or plain text
    structured = data.get('structured')
    text = data.get('text', '')
    title = data.get('title', 'Report')

    with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp:
        path = tmp.name

    try:
        if structured:
            create_pdf_from_structured(structured, title, path)
        else:
            create_pdf_from_text(text, title, path)
        return send_file(path, as_attachment=True, download_name=f"{title.replace(' ', '_')}.pdf")
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def create_pdf_from_text(text, title, filename):
    styles = getSampleStyleSheet()
    header = Paragraph(title, styles['Title'])
    doc = SimpleDocTemplate(filename, pagesize=A4)
    story = [header, Spacer(1,12)]
    for line in text.split('\n'):
        if line.strip():
            story.append(Paragraph(line.strip(), styles['BodyText']))
            story.append(Spacer(1,6))
    doc.build(story)

def create_pdf_from_structured(obj, title, filename):
    styles = getSampleStyleSheet()
    # Custom styles
    header_style = ParagraphStyle('Header', parent=styles['Heading1'], fontSize=18, textColor=colors.HexColor('#00f0ff'))
    subtitle_style = ParagraphStyle('Sub', parent=styles['Heading2'], fontSize=12, textColor=colors.HexColor('#ff073a'))
    normal = styles['BodyText']
    normal.spaceAfter = 6

    doc = SimpleDocTemplate(filename, pagesize=A4, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
    story = []
    story.append(Paragraph(title, header_style))
    story.append(Spacer(1,8))

    # If it's a dict with match_score etc.
    if isinstance(obj, dict):
        ms = obj.get('match_score')
        if ms is not None:
            story.append(Paragraph(f"Match Score: <b>{ms}%</b>", subtitle_style))
            story.append(Spacer(1,6))
        if 'summary' in obj:
            story.append(Paragraph('Summary:', subtitle_style))
            story.append(Paragraph(obj.get('summary',''), normal))
            story.append(Spacer(1,8))
        if 'missing_skills' in obj:
            story.append(Paragraph('Missing Skills:', subtitle_style))
            for sk in obj.get('missing_skills', []):
                story.append(Paragraph(f'- {sk}', normal))
            story.append(Spacer(1,8))
        if 'improvements' in obj:
            story.append(Paragraph('Suggested Improvements:', subtitle_style))
            for imp in obj.get('improvements', []):
                story.append(Paragraph(f'- {imp}', normal))
            story.append(Spacer(1,8))
    # If it's a list (job suggestions)
    elif isinstance(obj, list):
        for item in obj:
            role = item.get('role') or item.get('title') or item.get('name')
            desc = item.get('description','')
            imps = item.get('improvements', [])
            story.append(Paragraph(f"{role}", subtitle_style))
            story.append(Paragraph(desc, normal))
            for imp in imps:
                story.append(Paragraph(f'- {imp}', normal))
            story.append(Spacer(1,8))

    else:
        # fallback: print as text
        story.append(Paragraph(str(obj), normal))

    doc.build(story)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
