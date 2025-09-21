#!/usr/bin/env python
# coding: utf-8

# Created by Dr. A.C. van der Heijden, version 3.0
# This script checks the references section of a DOCX document by performing two tasks:
# 1] DOI Validation: It extracts the DOI from the input document and looks it up in the Crossref database (a repository of scholarly publications).
# 2] Title Verification: If a DOI is found, it checks if the input reference title matches the one in Crossref Database.

# The script flags references if:
# 1] The DOI is missing or cannot be found in the Crossref database
# 2] The reference input title does not match the title in the Crossref Database

# Version log: v3.0 works with pasted text and improved separation logic

import re
import time
import requests
import streamlit as st

st.set_page_config(page_title="Fabricated Reference Checker v3.0")
st.title("Fabricated Reference Checker v3.0")

st.markdown("""
### How does it work?
This tool checks references you paste in by:

1. Verifying the DOI for each reference  
2. Checking if the reference title matches an online database of academic papers (Crossref Database)

If titles do not fully match, the reference will be flagged as potentially incorrect or fabricated.

**Important:** Please double-check flagged references manually. This tool is inteded as a first check, not a final evaluation.
""", unsafe_allow_html=True)


def normalize_text(raw: str) -> str:
    """
    Normalize line endings and merge broken lines:
    - Convert all line endings to '\\n'
    - Merge lines not ending in sentence punctuation with the next line
    - Preserve blank lines
    """
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
            merged.append("")  # blank line
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
    """
    Split normalized text into reference entries.
    Handles:
    - Numbered entries: "1. ", "[1] ", "1) "
    - Blank-line separators
    - Author–year pattern
    """
    # Insert blank lines before author–year entries
    author_year_pattern = re.compile(r'^(?=[A-Z][a-z]+, .*?\(\d{4}\))', re.MULTILINE)
    text = author_year_pattern.sub('\n', text)

    splitter = re.compile(
        r'(?:^(?:\[\d+\]|\d+\.)\s+)|'  # [1] or 1.
        r'(?:^(?:\d+\))\s+)|'          # 1)
        r'(?:\n{2,})',                 # Two or more newlines
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
    """
    Remove any line that is exactly a reference heading.
    Supports multilingual variants.
    """
    headings = [
        "References", "Referenties", "Reference", "Citations",
        "Bibliography", "Literature Cited", "Sources", "Work cited"
    ]
    pattern = re.compile(r'^\s*(?:' + "|".join(headings) + r')\s*$', re.IGNORECASE | re.MULTILINE)
    return pattern.sub("", text)


def extract_doi(text: str) -> str | None:
    """Extract DOI using regex."""
    m = re.search(r'(10\.\d{4,9}/[-._;()/:A-Z0-9]+)', text, re.I)
    return m.group(1).rstrip(' .;,') if m else None


def check_crossref(query: str):
    """
    Query Crossref API by DOI or title.
    Returns first matched item or None.
    """
    if query.startswith("10."):
        resp = requests.get(f"https://api.crossref.org/works/{query}")
    else:
        resp = requests.get(
            "https://api.crossref.org/works",
            params={"query.title": query or "", "rows": 1}
        )
    time.sleep(1)
    if resp.status_code == 200:
        msg = resp.json().get("message", {})
        return (msg["items"][0] if "items" in msg and msg["items"] else msg) or None
    return None


def is_title_in_reference(crossref_title: str, ref_text: str) -> bool:
    """Case- and punctuation-insensitive substring match."""
    normalize = lambda s: re.sub(r'\W+', '', s).lower()
    return normalize(crossref_title) in normalize(ref_text)


# --- UI & Processing ---

input_text = st.text_area(
    "Paste your references here:",
    height=400,
    placeholder="Paste references here. Press CTRL ENTER to run."
)

if not input_text.strip():
    st.info("📋 Please paste your references above, press CTRL and ENTER at the same time to start checking")
    st.stop()

# 1. Remove heading
text_no_heading = remove_heading(input_text)

# 2. Normalize & split
normalized = normalize_text(text_no_heading)
references = split_references(normalized)
total = len(references)

if total == 0:
    st.warning("⚠ No references detected. Please check your input formatting.")
    st.stop()

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
            title = entry.get("title", [""])[0]
            st.success(f"✅ Found in Crossref: {title}")
            if is_title_in_reference(title, ref):
                st.success("✔ Title matches database")
                correct += 1
            else:
                st.error("❌ Title mismatch")
                st.warning("⚠ This reference might be incorrect or fabricated.")
                incorrect += 1
                incorrect_list.append(ref)
        else:
            st.error("❌ Not found in Crossref database")
            incorrect += 1
            incorrect_list.append(ref)
    else:
        st.warning("⚠ No DOI found")
        no_doi += 1
        no_doi_list.append(ref)

    progress.progress(idx / total)

progress.progress(1.0)
status.empty()

# 3. Summary Report
st.markdown("---")
st.header("Summary Report")
st.write(f"💡 {with_doi} out of {total} ({with_doi/total*100:.1f}%) references contained a DOI")
if with_doi:
    st.write(f"✅ Validated correct: {correct} / {with_doi} ({correct/with_doi*100:.1f}%)")
    st.write(f"❌ Potentially incorrect: {incorrect} / {with_doi} ({incorrect/with_doi*100:.1f}%)")
#st.write(f"📌 References without DOI: {no_doi} / {total} ({no_doi/total*100:.1f}%)")

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
