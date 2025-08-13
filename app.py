from flask import Flask, render_template, request, jsonify, send_file
import google.generativeai as genai
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfgen import canvas   # NEW
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
 only return a clear plain-text analysis, do not return jason.
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
 return human-readable text,do not return jason.
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


def add_neon_background(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(colors.HexColor("#0a0a0f"))  # Dark background
    canvas.rect(0, 0, A4[0], A4[1], fill=1)  # Full page rectangle
    canvas.restoreState()

# ======== CREATE PDF FROM TEXT ========
def create_pdf_from_text(text, title, filename):
    styles = getSampleStyleSheet()

    header_style = ParagraphStyle(
        'Header',
        parent=styles['Title'],
        fontSize=28,
        textColor=colors.HexColor('#00f0ff'),
        spaceAfter=14
    )
    body_style = ParagraphStyle(
        'Body',
        parent=styles['BodyText'],
        fontSize=12,
        textColor=colors.HexColor('#ffffff'),
        spaceAfter=8
    )

    doc = SimpleDocTemplate(
        filename,
        pagesize=A4,
        rightMargin=36, leftMargin=36,
        topMargin=50, bottomMargin=36
    )

    story = [Paragraph(title, header_style), Spacer(1, 20)]
    for line in text.split('\n'):
        if line.strip():
            story.append(Paragraph(line.strip(), body_style))
            story.append(Spacer(1, 6))

    doc.build(story, onFirstPage=add_neon_background, onLaterPages=add_neon_background)

# ======== CREATE PDF FROM STRUCTURED DATA ========
def create_pdf_from_structured(obj, title, filename):
    styles = getSampleStyleSheet()

    header_style = ParagraphStyle(
        'Header',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#00f0ff'),
        spaceAfter=14
    )
    subtitle_style = ParagraphStyle(
        'Sub',
        parent=styles['Heading2'],
        fontSize=14,
        textColor=colors.HexColor('#ff073a'),
        spaceAfter=6
    )
    normal_style = ParagraphStyle(
        'Normal',
        parent=styles['BodyText'],
        fontSize=12,
        textColor=colors.HexColor('#ffffff'),
        spaceAfter=6
    )
    bullet_style = ParagraphStyle(
        'Bullet',
        parent=styles['BodyText'],
        fontSize=12,
        textColor=colors.HexColor('#39ff14'),
        leftIndent=12,
        spaceAfter=4
    )

    doc = SimpleDocTemplate(
        filename,
        pagesize=A4,
        rightMargin=36, leftMargin=36,
        topMargin=50, bottomMargin=36
    )

    story = [Paragraph(title, header_style), Spacer(1, 12)]

    if isinstance(obj, dict):
        ms = obj.get('match_score')
        if ms is not None:
            story.append(Paragraph(f"Match Score: <b>{ms}%</b>", subtitle_style))
        if 'summary' in obj:
            story.append(Paragraph('Summary:', subtitle_style))
            story.append(Paragraph(obj.get('summary', ''), normal_style))
        if 'missing_skills' in obj:
            story.append(Paragraph('Missing Skills:', subtitle_style))
            for sk in obj.get('missing_skills', []):
                story.append(Paragraph(f"• {sk}", bullet_style))
        if 'improvements' in obj:
            story.append(Paragraph('Suggested Improvements:', subtitle_style))
            for imp in obj.get('improvements', []):
                story.append(Paragraph(f"• {imp}", bullet_style))

    elif isinstance(obj, list):
        for item in obj:
            role = item.get('role') or item.get('title') or item.get('name')
            desc = item.get('description', '')
            imps = item.get('improvements', [])
            story.append(Paragraph(role, subtitle_style))
            story.append(Paragraph(desc, normal_style))
            for imp in imps:
                story.append(Paragraph(f"• {imp}", bullet_style))
            story.append(Spacer(1, 8))
    else:
        story.append(Paragraph(str(obj), normal_style))

    doc.build(story, onFirstPage=add_neon_background, onLaterPages=add_neon_background)

# ======== ENDPOINT TO GENERATE PDF ========
@app.route('/api/generate_pdf', methods=['POST'])
def generate_pdf_endpoint():
    try:
        data = request.get_json(force=True) or {}
        structured = data.get('structured')
        text = data.get('text', '')
        title = data.get('title', 'Report')

        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp:
            path = tmp.name

        if structured:
            create_pdf_from_structured(structured, title, path)
        elif text.strip():
            create_pdf_from_text(text, title, path)
        else:
            return jsonify({'error': 'No valid data to generate PDF'}), 400

        return send_file(
            path,
            as_attachment=True,
            download_name=f"{title.replace(' ', '_')}.pdf",
            mimetype='application/pdf'
        )

    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)