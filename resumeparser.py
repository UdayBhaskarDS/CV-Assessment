
# # resumeparser.py
# """
# Resume parser + experience analysis + AI assessment.

# Public API:
#     ats_extractor(resume_data: str, api_key: str | None = None) -> dict

# Notes:
# - If api_key is provided, it will be used for the OpenAI call(s) for this request.
# - If not, the file will load DEFAULT_API_KEY from config.yaml (same location as before).
# - Returns a Python dict with parsed fields, experience_analysis, and assessment.
# """

# from openai import OpenAI
# import yaml
# import json
# import re
# from datetime import date, datetime
# from typing import Optional

# # -------------------------
# # Load default API key from config (fallback)
# # -------------------------
# CONFIG_PATH = r"config.yaml"
# try:
#     with open(CONFIG_PATH) as file:
#         cfg = yaml.load(file, Loader=yaml.FullLoader) or {}
# except FileNotFoundError:
#     cfg = {}
# DEFAULT_API_KEY = cfg.get("OPENAI_API_KEY")

# # -------------------------
# # Utilities: clean & parse JSON-like model output
# # -------------------------
# def _clean_model_output(raw: str) -> str:
#     """Remove code fences and surrounding noise the model might add."""
#     if raw is None:
#         return ""
#     s = raw.strip()
#     # remove triple backticks and optional "json"
#     s = re.sub(r"^```(?:json)?\s*", "", s, flags=re.IGNORECASE)
#     s = re.sub(r"\s*```$", "", s, flags=re.IGNORECASE)
#     # strip leftover single backticks and whitespace
#     s = s.strip("` \n\r\t")
#     return s

# def _attempt_fix_and_parse(s: str):
#     """
#     Try to parse JSON robustly. Apply small fixes on common issues:
#     - replace smart quotes
#     - convert single quotes to double quotes (best-effort)
#     - remove trailing commas
#     - trim leading garbage before first '{'
#     """
#     if not isinstance(s, str):
#         raise ValueError("Expected string input for JSON parsing.")
#     try:
#         return json.loads(s)
#     except json.JSONDecodeError:
#         fixed = s.replace("“", "\"").replace("”", "\"").replace("‘", "\"").replace("’", "\"")
#         # best-effort single-quote handling (dangerous for nested quotes, but helps many model outputs)
#         fixed = re.sub(r"(?<!\\)\'", "\"", fixed)
#         # remove trailing commas before } or ]
#         fixed = re.sub(r",\s*(\}|])", r"\1", fixed)
#         # drop any leading stuff before first JSON object
#         idx = fixed.find("{")
#         if idx > 0:
#             fixed = fixed[idx:]
#         # finally attempt to parse again
#         return json.loads(fixed)

# # -------------------------
# # Date parsing & experience analysis helpers
# # -------------------------
# MONTHS = {
#     'jan':1,'feb':2,'mar':3,'apr':4,'may':5,'jun':6,
#     'jul':7,'aug':8,'sep':9,'sept':9,'oct':10,'nov':11,'dec':12
# }

# def parse_fuzzy_date(s: Optional[str]):
#     """
#     Parse fuzzy date strings like:
#       - "Jan 2022" / "January 2022"
#       - "2022"
#       - "Aug 2019 – May 2023" (we won't parse the range here; this function returns a single date)
#       - "Present" -> returns today's date
#     Returns a date (first day of month) or None.
#     """
#     if not s or not isinstance(s, str):
#         return None
#     s = s.strip()
#     low = s.lower()
#     if low in ("present", "current", "now"):
#         return date.today()
#     # try MMM YYYY or Month YYYY
#     m = re.search(r"([A-Za-z]{3,9})\s+(\d{4})", s)
#     if m:
#         mon = m.group(1)[:3].lower()
#         year = int(m.group(2))
#         mon_num = MONTHS.get(mon)
#         if mon_num:
#             return date(year, mon_num, 1)
#     # try only year
#     m2 = re.search(r"(\d{4})", s)
#     if m2:
#         year = int(m2.group(1))
#         return date(year, 1, 1)
#     return None

# def months_between(start_date: date, end_date: date):
#     """Return approximate full months between two dates (end >= start)."""
#     if not start_date or not end_date:
#         return None
#     years = end_date.year - start_date.year
#     months = end_date.month - start_date.month
#     total = years*12 + months
#     return max(total, 0)

# def human_duration_from_months(total_months: int) -> str:
#     """Convert months to 'X yrs Y mos' human readable."""
#     if total_months is None:
#         return None
#     years = total_months // 12
#     months = total_months % 12
#     parts = []
#     if years:
#         parts.append(f"{years} yr{'s' if years>1 else ''}")
#     if months:
#         parts.append(f"{months} mo{'s' if months>1 else ''}")
#     return " ".join(parts) if parts else "0 mo"

# def merge_intervals_and_total_days(intervals):
#     """
#     intervals: list of (start_date, end_date) date tuples.
#     Merge overlaps and return total days covered.
#     """
#     clean = [(s, e) for s, e in intervals if s and e and s <= e]
#     if not clean:
#         return 0
#     clean.sort(key=lambda x: x[0])
#     merged = []
#     cur_s, cur_e = clean[0]
#     for s, e in clean[1:]:
#         if s <= cur_e:
#             if e > cur_e:
#                 cur_e = e
#         else:
#             merged.append((cur_s, cur_e))
#             cur_s, cur_e = s, e
#     merged.append((cur_s, cur_e))
#     total_days = sum((e - s).days for s, e in merged)
#     return total_days

# # -------------------------
# # GPT-based assessment (uses provided client)
# # -------------------------
# def generate_assessment_with_gpt(parsed_obj: dict, client: OpenAI):
#     """
#     Using provided OpenAI client, generate a JSON-only assessment dict:
#       { strengths: [], weaknesses: [], red_flags: [], recommendations: [], overall_score: int }
#     Client must be an OpenAI(client API wrapper) instance.
#     """
#     # Short context
#     context = {
#         "full_name": parsed_obj.get("full_name"),
#         "email": parsed_obj.get("email"),
#         "linkedin": parsed_obj.get("linkedin"),
#         "employment_details": parsed_obj.get("employment_details", []),
#         "technical_skills": parsed_obj.get("technical_skills", {}),
#         "soft_skills": parsed_obj.get("soft_skills", []),
#         "education": parsed_obj.get("education", [])
#     }

#     system = {
#         "role": "system",
#         "content": (
#             "You are a JSON-only assessment generator for resumes. Output MUST be valid JSON and nothing else."
#         )
#     }
#     example_user = {
#         "role": "user",
#         "content": "Example: Candidate with stable 5-year data engineering experience, strong Python & SQL, but no certifications and a 2-year gap."
#     }
#     example_assistant = {
#         "role": "assistant",
#         "content": json.dumps({
#             "strengths": ["Strong hands-on experience with Python and SQL", "Multiple years in data engineering"],
#             "weaknesses": ["No relevant certifications"],
#             "red_flags": ["2-year gap 2018-2020 (unexplained)"],
#             "recommendations": ["Good fit for data engineering roles", "Consider cloud certification (AWS/Azure/GCP)"],
#             "overall_score": 72
#         }, indent=2)
#     }

#     user_prompt = {
#         "role": "user",
#         "content": (
#             "Based on the parsed resume JSON below (only keys shown), produce a concise JSON assessment with keys:\n"
#             "strengths (list), weaknesses (list), red_flags (list), recommendations (list), overall_score (integer 0-100).\n"
#             "Return only JSON.\n\n"
#             + json.dumps(context, indent=2) +
#             "\n\nGuidelines:\n- Strengths: clear technical/domain strengths.\n- Weaknesses: missing details (education missing, unclear dates) or weak areas.\n- Red flags: gaps longer than 12 months, overlapping inconsistent dates, >3 jobs in 2 years.\n- Recommendations: suggested roles/next steps.\n"
#         )
#     }

#     messages = [system, example_user, example_assistant, user_prompt]
#     try:
#         resp = client.chat.completions.create(
#             model="gpt-4o",
#             messages=messages,
#             temperature=0.0,
#             max_tokens=500
#         )
#         raw = resp.choices[0].message.content
#         cleaned = _clean_model_output(raw)
#         parsed = _attempt_fix_and_parse(cleaned)
#         # ensure keys
#         defaults = {"strengths": [], "weaknesses": [], "red_flags": [], "recommendations": [], "overall_score": 0}
#         for k, v in defaults.items():
#             if k not in parsed:
#                 parsed[k] = v
#         return parsed
#     except Exception as e:
#         # On failure, return defaults + error message
#         return {"strengths": [], "weaknesses": [], "red_flags": [], "recommendations": [], "overall_score": 0, "error": str(e)}

# # -------------------------
# # MAIN parser function
# # -------------------------
# def ats_extractor(resume_data: str, api_key: Optional[str] = None) -> dict:
#     """
#     Parse resume text and return a Python dict:
#       - parsed fields (full_name, email, linkedin, employment_details, technical_skills, soft_skills, education, languages, certifications)
#       - experience_analysis: { per_job: [...], total_days_covered, total_months_approx, total_years_approx, total_human_readable }
#       - assessment: { strengths, weaknesses, red_flags, recommendations, overall_score }

#     If api_key provided, it's used for this single call. Otherwise DEFAULT_API_KEY from config.yaml is used.
#     """
#     # choose API key
#     key_to_use = api_key or DEFAULT_API_KEY
#     if not key_to_use:
#         return {"error": "No OpenAI API key provided. Pass api_key to ats_extractor or set OPENAI_API_KEY in config.yaml."}

#     # create client for this request
#     client = OpenAI(api_key=key_to_use)

#     # --------- (A) parse resume into structured JSON via model ----------
#     system = {
#         "role": "system",
#         "content": (
#             "You are a JSON-only extraction engine. Given a resume, output ONLY valid JSON following this schema exactly:\n"
#             "{\n"
#             '  "full_name": "",\n'
#             '  "email": "",\n'
#             '  "github": null,\n'
#             '  "linkedin": null,\n'
#             '  "employment_details": [ { "company":"", "job_title":"", "start_date":"", "end_date":"", "location":null, "responsibilities": [] } ],\n'
#             '  "technical_skills": { "analytics_bi": [], "databases_data_management": [], "programming_scripting": [], "tools_technologies": [] },\n'
#             '  "soft_skills": [],\n'
#             '  "education": [],\n'
#             '  "languages": [],\n'
#             '  "certifications": []\n'
#             "}\n"
#             "Return only the JSON object with those keys. Use null or empty arrays where appropriate."
#         )
#     }
#     user_prompt = {
#         "role": "user",
#         "content": "Resume Text:\n```\n" + resume_data + "\n```\n\nReturn JSON only."
#     }

#     messages = [system, user_prompt]
#     try:
#         resp = client.chat.completions.create(
#             model="gpt-4o",
#             messages=messages,
#             temperature=0.0,
#             max_tokens=2000
#         )
#         raw = resp.choices[0].message.content
#         cleaned = _clean_model_output(raw)
#         parsed = _attempt_fix_and_parse(cleaned)
#     except Exception as e:
#         return {"error": f"Parsing error: {str(e)}"}

#     # ensure expected keys exist
#     defaults = {
#         "full_name": None,
#         "email": None,
#         "github": None,
#         "linkedin": None,
#         "employment_details": [],
#         "technical_skills": {
#             "analytics_bi": [],
#             "databases_data_management": [],
#             "programming_scripting": [],
#             "tools_technologies": []
#         },
#         "soft_skills": [],
#         "education": [],
#         "languages": [],
#         "certifications": []
#     }
#     for k, v in defaults.items():
#         if k not in parsed or parsed[k] is None:
#             parsed[k] = v

#     # --------- (B) Experience analysis ----------
#     exp_entries = parsed.get("employment_details", []) or []
#     analysis_entries = []
#     intervals = []

#     for job in exp_entries:
#         # get raw strings
#         start_raw = job.get("start_date") or job.get("start") or ""
#         end_raw = job.get("end_date") or job.get("end") or job.get("to") or ""
#         # parse dates
#         # Note: sometimes resumes have ranges like "Aug 2019 – May 2023" inside a single field;
#         # prefer explicit start_date / end_date fields; fallback: attempt to split on dash.
#         # Try to split if start_raw contains "–" or "-" and end_raw empty
#         if (not end_raw) and isinstance(start_raw, str) and ("–" in start_raw or "-" in start_raw):
#             # split by en dash or hyphen
#             parts = re.split(r"\s*[–-]\s*", start_raw)
#             if len(parts) >= 2:
#                 start_raw = parts[0].strip()
#                 possible_end = parts[1].strip()
#                 # use as end_raw if we don't already have end_raw
#                 end_raw = end_raw or possible_end

#         start_dt = parse_fuzzy_date(start_raw)
#         end_dt = parse_fuzzy_date(end_raw) if end_raw else None

#         # If end is still None but the raw strings say 'present' / 'current' -> treat as today
#         if end_dt is None and isinstance(end_raw, str) and re.search(r"\b(present|current|now)\b", (end_raw or ""), flags=re.IGNORECASE):
#             end_dt = date.today()

#         # If end_dt None but job responsibilities or title includes 'present', attempt to set to today
#         # (Not strictly necessary; skip aggressive heuristics here.)

#         duration_months = None
#         duration_human = None
#         if start_dt and end_dt:
#             months = months_between(start_dt, end_dt)
#             duration_months = months
#             duration_human = human_duration_from_months(months)
#             intervals.append((start_dt, end_dt))

#         analysis_entries.append({
#             "company": job.get("company"),
#             "job_title": job.get("job_title"),
#             "start_date_raw": start_raw or None,
#             "end_date_raw": end_raw or None,
#             "start_date_parsed": start_dt.isoformat() if start_dt else None,
#             "end_date_parsed": end_dt.isoformat() if end_dt else None,
#             "duration_months": duration_months,
#             "duration_human": duration_human,
#             "responsibilities": job.get("responsibilities", []) or []
#         })

#     total_days = merge_intervals_and_total_days(intervals)
#     total_months = total_days // 30
#     total_years = round(total_days / 365.25, 2) if total_days > 0 else 0.0
#     total_human = human_duration_from_months(total_months) if total_months and total_months > 0 else "0 mo"

#     experience_analysis = {
#         "per_job": analysis_entries,
#         "total_days_covered": total_days,
#         "total_months_approx": total_months,
#         "total_years_approx": total_years,
#         "total_human_readable": total_human
#     }
#     parsed["experience_analysis"] = experience_analysis

#     # --------- (C) Assessment generation ----------
#     assessment = generate_assessment_with_gpt(parsed, client)
#     parsed["assessment"] = assessment

#     return parsed


# resumeparser.py
"""
Azure OpenAI-based resume parser + experience analysis + AI assessment.

Public API:
    ats_extractor(resume_data: str,
                  azure_api_key: Optional[str] = None,
                  azure_endpoint: Optional[str] = None,
                  deployment: Optional[str] = None) -> dict

Notes:
- If azure_api_key / azure_endpoint / deployment are provided to ats_extractor, those are used for the single request.
- Otherwise it falls back to config.yaml or environment variables:
    config.yaml keys: AZURE_API_KEY, AZURE_ENDPOINT, AZURE_DEPLOYMENT, AZURE_API_VERSION (optional)
- Expects Azure chat completion deployment that supports the Chat Completions API.
"""

from typing import Optional
import os
import json
import yaml
import re
from datetime import date
from datetime import datetime

# try to import AzureOpenAI wrapper from OpenAI package (as in your screenshot)
try:
    # The newer OpenAI package exposes AzureOpenAI class in some releases.
    # If your local openai package doesn't have it, use the standard OpenAI client and adapt accordingly.
    from openai import AzureOpenAI
except Exception as e:
    AzureOpenAI = None  # we'll raise later with clear message

# -------------------------
# Load default Azure config from config.yaml or environment
# -------------------------
CONFIG_PATH = "config.yaml"
cfg = {}
if os.path.exists(CONFIG_PATH):
    try:
        with open(CONFIG_PATH, "r") as fh:
            cfg = yaml.load(fh, Loader=yaml.FullLoader) or {}
    except Exception:
        cfg = {}

DEFAULT_AZURE_API_KEY = cfg.get("AZURE_API_KEY") or os.environ.get("AZURE_API_KEY") or os.environ.get("OPENAI_API_KEY")
DEFAULT_AZURE_ENDPOINT = cfg.get("AZURE_ENDPOINT") or os.environ.get("AZURE_ENDPOINT") or os.environ.get("OPENAI_ENDPOINT")
DEFAULT_AZURE_DEPLOYMENT = cfg.get("AZURE_DEPLOYMENT") or os.environ.get("AZURE_DEPLOYMENT") or cfg.get("AZURE_DEPLOYMENT_NAME")
DEFAULT_AZURE_API_VERSION = cfg.get("AZURE_API_VERSION") or os.environ.get("AZURE_API_VERSION") or "2024-12-01-preview"

# -------------------------
# Utilities: clean & parse JSON-like model output
# -------------------------
def _clean_model_output(raw: str) -> str:
    """Remove code fences and surrounding noise the model might add."""
    if raw is None:
        return ""
    s = raw.strip()
    s = re.sub(r"^```(?:json)?\s*", "", s, flags=re.IGNORECASE)
    s = re.sub(r"\s*```$", "", s, flags=re.IGNORECASE)
    s = s.strip("` \n\r\t")
    return s

def _attempt_fix_and_parse(s: str):
    """
    Try to parse JSON robustly. Apply small fixes on common issues:
    - replace smart quotes
    - convert single quotes to double quotes (best-effort)
    - remove trailing commas
    - trim leading garbage before first '{'
    """
    if not isinstance(s, str):
        raise ValueError("Expected string input for JSON parsing.")
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        fixed = s.replace("“", "\"").replace("”", "\"").replace("‘", "\"").replace("’", "\"")
        fixed = re.sub(r"(?<!\\)\'", "\"", fixed)
        fixed = re.sub(r",\s*(\}|])", r"\1", fixed)
        idx = fixed.find("{")
        if idx > 0:
            fixed = fixed[idx:]
        return json.loads(fixed)

# -------------------------
# Date parsing & experience analysis helpers
# -------------------------
MONTHS = {
    'jan':1,'feb':2,'mar':3,'apr':4,'may':5,'jun':6,
    'jul':7,'aug':8,'sep':9,'sept':9,'oct':10,'nov':11,'dec':12
}

def parse_fuzzy_date(s: Optional[str]):
    if not s or not isinstance(s, str):
        return None
    s = s.strip()
    low = s.lower()
    if low in ("present", "current", "now"):
        return date.today()
    m = re.search(r"([A-Za-z]{3,9})\s+(\d{4})", s)
    if m:
        mon = m.group(1)[:3].lower()
        year = int(m.group(2))
        mon_num = MONTHS.get(mon)
        if mon_num:
            return date(year, mon_num, 1)
    m2 = re.search(r"(\d{4})", s)
    if m2:
        year = int(m2.group(1))
        return date(year, 1, 1)
    return None

def months_between(start_date: date, end_date: date):
    if not start_date or not end_date:
        return None
    years = end_date.year - start_date.year
    months = end_date.month - start_date.month
    total = years*12 + months
    return max(total, 0)

def human_duration_from_months(total_months: int) -> str:
    if total_months is None:
        return None
    years = total_months // 12
    months = total_months % 12
    parts = []
    if years:
        parts.append(f"{years} yr{'s' if years>1 else ''}")
    if months:
        parts.append(f"{months} mo{'s' if months>1 else ''}")
    return " ".join(parts) if parts else "0 mo"

def merge_intervals_and_total_days(intervals):
    clean = [(s, e) for s, e in intervals if s and e and s <= e]
    if not clean:
        return 0
    clean.sort(key=lambda x: x[0])
    merged = []
    cur_s, cur_e = clean[0]
    for s, e in clean[1:]:
        if s <= cur_e:
            if e > cur_e:
                cur_e = e
        else:
            merged.append((cur_s, cur_e))
            cur_s, cur_e = s, e
    merged.append((cur_s, cur_e))
    total_days = sum((e - s).days for s, e in merged)
    return total_days

# -------------------------
# Azure OpenAI helpers
# -------------------------
def _make_azure_client(azure_api_key: str, azure_endpoint: str, api_version: str = DEFAULT_AZURE_API_VERSION):
    if AzureOpenAI is None:
        raise RuntimeError(
            "AzureOpenAI client not available. Ensure you installed a compatible 'openai' Python package "
            "that exports AzureOpenAI (or adapt this file to your SDK)."
        )
    client = AzureOpenAI(
        api_key=azure_api_key,
        azure_endpoint=azure_endpoint,
        api_version=api_version
    )
    return client

# -------------------------
# GPT-based assessment (Azure)
# -------------------------
def generate_assessment_with_gpt(parsed_obj: dict, client, deployment: str):
    context = {
        "full_name": parsed_obj.get("full_name"),
        "email": parsed_obj.get("email"),
        "linkedin": parsed_obj.get("linkedin"),
        "employment_details": parsed_obj.get("employment_details", []),
        "technical_skills": parsed_obj.get("technical_skills", {}),
        "soft_skills": parsed_obj.get("soft_skills", []),
        "education": parsed_obj.get("education", [])
    }

    system = {
        "role": "system",
        "content": "You are a JSON-only assessment generator for resumes. Output MUST be valid JSON and nothing else."
    }
    example_user = {
        "role": "user",
        "content": "Example: Candidate with stable 5-year data engineering experience, strong Python & SQL, but no certifications and a 2-year gap."
    }
    example_assistant = {
        "role": "assistant",
        "content": json.dumps({
            "strengths": ["Strong hands-on experience with Python and SQL", "Multiple years in data engineering"],
            "weaknesses": ["No relevant certifications"],
            "red_flags": ["2-year gap 2018-2020 (unexplained)"],
            "recommendations": ["Good fit for data engineering roles", "Consider cloud certification (AWS/Azure/GCP)"],
            "overall_score": 72
        }, indent=2)
    }

    user_prompt = {
        "role": "user",
        "content": (
            "Based on the parsed resume JSON below (only keys shown), produce a concise JSON assessment with keys:\n"
            "strengths (list), weaknesses (list), red_flags (list), recommendations (list), overall_score (integer 0-100).\n"
            "Return only JSON.\n\n"
            + json.dumps(context, indent=2) +
            "\n\nGuidelines:\n- Strengths: clear technical/domain strengths.\n- Weaknesses: missing details (education missing, unclear dates) or weak areas.\n- Red flags: gaps longer than 12 months, overlapping inconsistent dates, >3 jobs in 2 years.\n- Recommendations: suggested roles/next steps.\n"
        )
    }

    messages = [system, example_user, example_assistant, user_prompt]

    try:
        resp = client.chat.completions.create(
            model=deployment,
            messages=messages,
            temperature=0.0,
            max_tokens=500
        )
        raw = resp.choices[0].message.content
        cleaned = _clean_model_output(raw)
        parsed = _attempt_fix_and_parse(cleaned)
        defaults = {"strengths": [], "weaknesses": [], "red_flags": [], "recommendations": [], "overall_score": 0}
        for k, v in defaults.items():
            if k not in parsed:
                parsed[k] = v
        return parsed
    except Exception as e:
        return {"strengths": [], "weaknesses": [], "red_flags": [], "recommendations": [], "overall_score": 0, "error": str(e)}

# -------------------------
# MAIN parser function (Azure)
# -------------------------
def ats_extractor(resume_data: str,
                  azure_api_key: Optional[str] = None,
                  azure_endpoint: Optional[str] = None,
                  deployment: Optional[str] = None,
                  api_version: Optional[str] = None) -> dict:
    """
    Parse resume text and return a Python dict.
    Provide optional per-request azure_api_key / azure_endpoint / deployment.
    """

    # decide values (per-request override -> config -> env)
    key_to_use = azure_api_key or DEFAULT_AZURE_API_KEY
    endpoint_to_use = azure_endpoint or DEFAULT_AZURE_ENDPOINT
    deployment_to_use = deployment or DEFAULT_AZURE_DEPLOYMENT
    api_version_to_use = api_version or DEFAULT_AZURE_API_VERSION

    if not key_to_use or not endpoint_to_use or not deployment_to_use:
        return {"error": "Azure credentials or deployment not provided. Provide azure_api_key, azure_endpoint, and deployment."}

    # create Azure client for this request
    client = _make_azure_client(key_to_use, endpoint_to_use, api_version=api_version_to_use)

    # --------- (A) parse resume into structured JSON via model ----------
    system = {
        "role": "system",
        "content": (
            "You are a JSON-only extraction engine. Given a resume, output ONLY valid JSON following this schema exactly:\n"
            "{\n"
            '  "full_name": "",\n'
            '  "email": "",\n'
            '  "github": null,\n'
            '  "linkedin": null,\n'
            '  "employment_details": [ { "company":"", "job_title":"", "start_date":"", "end_date":"", "location":null, "responsibilities": [] } ],\n'
            '  "technical_skills": { "analytics_bi": [], "databases_data_management": [], "programming_scripting": [], "tools_technologies": [] },\n'
            '  "soft_skills": [],\n'
            '  "education": [],\n'
            '  "languages": [],\n'
            '  "certifications": []\n'
            "}\n"
            "Return only the JSON object with those keys. Use null or empty arrays where appropriate."
        )
    }
    user_prompt = {
        "role": "user",
        "content": "Resume Text:\n```\n" + resume_data + "\n```\n\nReturn JSON only."
    }

    try:
        resp = client.chat.completions.create(
            model=deployment_to_use,
            messages=[system, user_prompt],
            temperature=0.0,
            max_tokens=2000
        )
        raw = resp.choices[0].message.content
        cleaned = _clean_model_output(raw)
        parsed = _attempt_fix_and_parse(cleaned)
    except Exception as e:
        return {"error": f"Parsing error: {str(e)}"}

    # ensure expected keys exist
    defaults = {
        "full_name": None,
        "email": None,
        "github": None,
        "linkedin": None,
        "employment_details": [],
        "technical_skills": {
            "analytics_bi": [],
            "databases_data_management": [],
            "programming_scripting": [],
            "tools_technologies": []
        },
        "soft_skills": [],
        "education": [],
        "languages": [],
        "certifications": []
    }
    for k, v in defaults.items():
        if k not in parsed or parsed[k] is None:
            parsed[k] = v

    # --------- (B) Experience analysis ----------
    exp_entries = parsed.get("employment_details", []) or []
    analysis_entries = []
    intervals = []

    for job in exp_entries:
        start_raw = job.get("start_date") or job.get("start") or ""
        end_raw = job.get("end_date") or job.get("end") or job.get("to") or ""
        if (not end_raw) and isinstance(start_raw, str) and ("–" in start_raw or "-" in start_raw):
            parts = re.split(r"\s*[–-]\s*", start_raw)
            if len(parts) >= 2:
                start_raw = parts[0].strip()
                possible_end = parts[1].strip()
                end_raw = end_raw or possible_end

        start_dt = parse_fuzzy_date(start_raw)
        end_dt = parse_fuzzy_date(end_raw) if end_raw else None
        if end_dt is None and isinstance(end_raw, str) and re.search(r"\b(present|current|now)\b", (end_raw or ""), flags=re.IGNORECASE):
            end_dt = date.today()

        duration_months = None
        duration_human = None
        if start_dt and end_dt:
            months = months_between(start_dt, end_dt)
            duration_months = months
            duration_human = human_duration_from_months(months)
            intervals.append((start_dt, end_dt))

        analysis_entries.append({
            "company": job.get("company"),
            "job_title": job.get("job_title"),
            "start_date_raw": start_raw or None,
            "end_date_raw": end_raw or None,
            "start_date_parsed": start_dt.isoformat() if start_dt else None,
            "end_date_parsed": end_dt.isoformat() if end_dt else None,
            "duration_months": duration_months,
            "duration_human": duration_human,
            "responsibilities": job.get("responsibilities", []) or []
        })

    total_days = merge_intervals_and_total_days(intervals)
    total_months = total_days // 30
    total_years = round(total_days / 365.25, 2) if total_days > 0 else 0.0
    total_human = human_duration_from_months(total_months) if total_months and total_months > 0 else "0 mo"

    experience_analysis = {
        "per_job": analysis_entries,
        "total_days_covered": total_days,
        "total_months_approx": total_months,
        "total_years_approx": total_years,
        "total_human_readable": total_human
    }
    parsed["experience_analysis"] = experience_analysis

    # --------- (C) Assessment generation (Azure) ----------
    assessment = generate_assessment_with_gpt(parsed, client, deployment_to_use)
    parsed["assessment"] = assessment

    return parsed
