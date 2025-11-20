#!/usr/bin/env python
# coding: utf-8
# Created by Dr. A.C. van der Heijden, version 4.0
# This script checks the references section of a DOCX document or pasted text by performing two tasks:
# 1] DOI Validation: It extracts the DOI from the input text and looks it up in the Crossref database (a repository of scholarly publications).
# 2] Title Verification: If a DOI is found, it checks if the input reference title matches the one in Crossref Database.
# The script flags references if:
# 1] The DOI is missing or cannot be found in the Crossref database
# 2] The reference input title does not match the title in the Crossref Database
# Version log: v4.1 has a "wildcard tolerance"; allows a certain amount of typos & handles pasted text as input

import re
import time
import requests
from io import BytesIO
import mammoth
import streamlit as st

st.set_page_config(page_title="Fabricated Reference Checker v4.0")
st.title("Fabricated Reference Checker v4.0")

# Initialize session state for wildcard
if "wildcard" not in st.session_state:
    st.session_state["wildcard"] = 0

st.markdown("""
### How does it work?
This tool checks references by either pasting them directly or uploading a DOCX document:

This tool checks references by:

1. Verifying the DOI for each reference  
2. Checking if the reference title matches an online database of academic papers (Crossref Database)

If there is a mismatch between these titles, the reference will be flagged as potentially incorrect or fabricated.

<div style="color:red; font-weight:bold">
Important: Please double-check flagged references manually. This tool is intended as a first check — not a final evaluation. Additionally, please only upload references and not entire theses/manuscripts to respect privacy regulations.
<br><br>
</div>
""", unsafe_allow_html=True)


# ----------------------------------------------------------------------
# Wildcard setting - explicitly submitted by user
# ----------------------------------------------------------------------
with st.form("wildcard_form"):
    new_wc = st.number_input(
        "Optional: Typo tolerance (allows the to tool ignore the selected number of typos in the title)",
        min_value=0, max_value=20, value=st.session_state["wildcard"], step=1
    )
    confirm_wc = st.form_submit_button("Apply typo tolerance")

if confirm_wc:
    st.session_state["wildcard"] = new_wc
    st.success(f"Typo tolerance updated to {new_wc}")


# ----------------------------------------------------------------------
# Helper Functions
# ----------------------------------------------------------------------
def normalize_text(raw: str) -> str:
    text = raw.replace('\r\n', '\n').replace('\r', '\n')
    lines = text.split('\n')
    merged = []
    buffer = ""
    for line in lines:
        stripped = line.rstrip()
        if not stripped:
            if buffer:
                merged.append(buffer.strip())
                buffer = ""
            merged.append("")
        elif re.search(r'[A-Za-z0-9][\.\?\!;:]?\s*$', stripped):
            if buffer:
                merged.append((buffer + " " + stripped).strip())
                buffer = ""
            else:
                merged.append(stripped)
        else:
            buffer = (buffer + " " + stripped).strip() if buffer else stripped
    if buffer:
        merged.append(buffer.strip())
    return "\n".join(merged)


def split_references(text: str) -> list[str]:
    author_year_pattern = re.compile(r'^(?=[A-Z][a-z]+, .*?\(\d{4}\))', re.MULTILINE)
    text = author_year_pattern.sub('\n', text)
    splitter = re.compile(
        r'(?:^(?:\[\d+\]|\d+\.)\s+)|'
        r'(?:^(?:\d+\))\s+)|'
        r'(?:\n{2,})',
        re.MULTILINE
    )
    parts = splitter.split(text)
    refs = []
    for part in parts:
        part = part.strip()
        if not part or re.fullmatch(r'\[\d+\]|\d+\.|\d+\)', part):
            continue
        refs.append(part)
    return refs


def remove_heading(text: str) -> str:
    headings = [
        "References", "Referenties", "Reference", "Citations",
        "Bibliography", "Literature Cited", "Sources", "Work cited"
    ]
    pattern = re.compile(r'^\s*(?:' + "|".join(headings) + r')\s*$', re.IGNORECASE | re.MULTILINE)
    return pattern.sub("", text)


def extract_doi(text: str) -> str | None:
    m = re.search(r'(10\.\d{4,9}/[-._;()/:A-Z0-9]+)', text, re.I)
    return m.group(1).rstrip(' .;,') if m else None


def check_crossref(query: str):
    if query and query.startswith("10."):
        resp = requests.get(f"https://api.crossref.org/works/{query}")
    else:
        resp = requests.get("https://api.crossref.org/works", params={"query.title": query or "", "rows": 1})
    time.sleep(1)
    if resp.status_code == 200:
        msg = resp.json().get("message", {})
        return (msg["items"][0] if "items" in msg and msg["items"] else msg) or None
    return None


def levenshtein(s1: str, s2: str) -> int:
    if len(s1) < len(s2):
        return levenshtein(s2, s1)
    if len(s2) == 0:
        return len(s1)
    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row
    return previous_row[-1]


def is_title_in_reference(crossref_title: str, ref_text: str, tolerance: int = 0) -> tuple[bool, bool]:
    normalize = lambda s: re.sub(r'\W+', '', s).lower()
    ct = normalize(crossref_title)
    rt = normalize(ref_text)

    if ct in rt:
        return True, False

    if len(ct) <= len(rt):
        for i in range(len(rt) - len(ct) + 1):
            window = rt[i:i+len(ct)]
            if levenshtein(ct, window) <= tolerance:
                return True, True
    else:
        if levenshtein(ct, rt) <= tolerance:
            return True, True

    return False, False


def flatten_docx_via_mammoth(doc_bytes: bytes) -> str:
    result = mammoth.extract_raw_text(BytesIO(doc_bytes))
    return result.value


def get_references_from_docx(doc_bytes: bytes) -> list[str]:
    text = flatten_docx_via_mammoth(doc_bytes)
    headings = ["References", "Referenties", "Reference", "Citations", "Bibliography",
                "Literature Cited", "Sources", "Work cited"]
    pattern = r'^(?:' + "|".join(headings) + r')\b'
    match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
    if match:
        references_text = text[match.end():].strip()
        return [r.strip() for r in references_text.split("\n") if r.strip()]
    return []


# ----------------------------------------------------------------------
# INPUT HANDLING
# ----------------------------------------------------------------------
uploaded_file = st.file_uploader("Upload DOCX file (optional):", type=["docx"])

with st.form("paste_form"):
    input_text = st.text_area("Or paste your references here:", height=400,
                              placeholder="Paste references here if not uploading a file")
    submit_paste = st.form_submit_button("Check Pasted References")

# Determine references based on user action
if uploaded_file is not None:
    references = get_references_from_docx(uploaded_file.read())
    if not references:
        st.warning("No references found in DOCX.")
        st.stop()
elif submit_paste and input_text.strip():
    text_no_heading = remove_heading(input_text)
    normalized = normalize_text(text_no_heading)
    references = split_references(normalized)
else:
    st.info("📋 Upload a DOCX or paste references and submit to begin")
    st.stop()

total = len(references)
if total == 0:
    st.warning("⚠ No references detected.")
    st.stop()


# ----------------------------------------------------------------------
# CLEAR WILDCARD BANNER
# ----------------------------------------------------------------------
st.markdown(f"### Typo Tolerance Setting: **{st.session_state['wildcard']}**")


# ----------------------------------------------------------------------
# PROCESS REFERENCES
# ----------------------------------------------------------------------
status = st.info(f"🔎 Found {total} references. Checking...")
progress = st.progress(0)

with_doi = no_doi = correct = incorrect = 0
no_doi_list = []
incorrect_list = []

for idx, ref in enumerate(references, start=1):
    st.write(f"**Reference {idx}:**")
    st.write(ref)

    doi = extract_doi(ref)
    if doi:
        st.write(f"🆔 Extracted DOI: {doi}")
        with_doi += 1
        entry = check_crossref(doi)
        if entry:
            title = entry.get("title", [""])[0] if isinstance(entry.get("title"), list) else entry.get("title", "")
            st.success(f"✅ Found in Crossref: {title}")
            matched, wildcard_used = is_title_in_reference(title, ref, tolerance=st.session_state["wildcard"])
            if matched:
                if wildcard_used:
                    st.success(f"✔ Title matches (Typo tolerance applied: {st.session_state['wildcard']})")
                else:
                    st.success("✔ Title matches database")
                correct += 1
            else:
                st.error("❌ Title mismatch")
                st.warning("⚠ This reference might be incorrect.")
                incorrect += 1
                incorrect_list.append(ref)
        else:
            st.error("❌ Not found in Crossref")
            incorrect += 1
            incorrect_list.append(ref)
    else:
        st.warning("⚠ No DOI found")
        no_doi += 1
        no_doi_list.append(ref)

    progress.progress(idx / total)

progress.progress(1.0)
status.empty()


# ----------------------------------------------------------------------
# SUMMARY REPORT
# ----------------------------------------------------------------------
st.markdown("---")
st.header("Summary Report")

# Calculate counts and percentages
with_doi_count = with_doi
total_references = total
total_verified_references = with_doi if with_doi > 0 else 1  # avoid division by zero
correct_count = correct
incorrect_count = incorrect

doi_required_percentage = (with_doi_count / total_references) * 100
correct_percentage = (correct_count / total_verified_references) * 100
incorrect_percentage = (incorrect_count / total_verified_references) * 100

# Display counts and percentages
st.write(f"💡 {with_doi_count} out of {total_references} ({doi_required_percentage:.2f}%) references contained a DOI which is required for verification")
st.write(f"✅ Validated references (out of those that contained a DOI): {correct_count} out of {total_verified_references} ({correct_percentage:.2f}%)")
st.write(f"❌ Incorrect/potentially fabricated references (out of those that contained a DOI): {incorrect_count} out of {total_verified_references} ({incorrect_percentage:.2f}%)")

# List details
if incorrect_list:
    st.subheader("Potentially Incorrect or Fabricated References")
    for i, r in enumerate(incorrect_list, 1):
        st.write(f"{i}. {r}")

if no_doi_list:
    st.subheader("References without DOI (Not verifiable)")
    for i, r in enumerate(no_doi_list, 1):
        st.write(f"{i}. {r}")

if incorrect == 0:
    st.balloons()
    st.success("🎉 All references appear correct!")
