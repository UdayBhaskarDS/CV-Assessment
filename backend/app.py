
import os
import json
from flask import Flask, request, jsonify
from pypdf import PdfReader
from flask_cors import CORS
from resumeparser import ats_extractor  # expects ats_extractor(resume_text, api_key=None)

BASE_DIR = os.path.dirname(__file__)
UPLOAD_PATH = os.path.join(BASE_DIR, "__DATA__")
os.makedirs(UPLOAD_PATH, exist_ok=True)

app = Flask(__name__)
CORS(app)  # allow cross-origin from frontend during development

@app.route('/')
def index():
    return "Resume Parser API is running. Use POST /api/process to upload PDF."

@app.route("/api/process", methods=["POST"])
def api_process():
    # 1) check file
    if 'pdf_doc' not in request.files:
        return jsonify({"success": False, "error": "No file provided (field name must be 'pdf_doc')"}), 400

    doc = request.files['pdf_doc']
    filename = "file.pdf"
    file_path = os.path.join(UPLOAD_PATH, filename)

    # 2) optional user-provided OpenAI key from header
    user_api_key = request.headers.get("x-openai-key") or request.form.get("openai_key")

    try:
        # save uploaded file
        doc.save(file_path)

        # extract text from PDF
        text = _read_file_from_path(file_path)

        # call parser with optional api_key (resumeparser handles None -> fallback key)
        parsed = ats_extractor(text, api_key=user_api_key)

        # parsed may already be a dict, or a JSON string, or something else
        if isinstance(parsed, dict):
            result = parsed
        elif isinstance(parsed, str):
            # try to parse JSON string
            try:
                result = json.loads(parsed)
            except Exception:
                result = {"raw_output": parsed}
        else:
            # unknown type -> convert to dict wrapper
            result = {"raw_output": str(parsed)}

        return jsonify({"success": True, "result": result}), 200

    except Exception as e:
        # return full error for dev; sanitize before production
        return jsonify({"success": False, "error": str(e)}), 500

def _read_file_from_path(path: str) -> str:
    reader = PdfReader(path)
    data = ""
    for page_no in range(len(reader.pages)):
        try:
            page = reader.pages[page_no]
            page_text = page.extract_text() or ""
            data += page_text + "\n"
        except Exception:
            # skip page if any extraction error
            continue
    return data

if __name__ == "__main__":
    # Run on 0.0.0.0 so it is reachable from other local hosts if needed
    app.run(host="0.0.0.0", port=8000, debug=True)
