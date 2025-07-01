#!/usr/bin/env python
# coding: utf-8

# In[ ]:

# Written by Dr. A.C. van der Heijden, version 1.0
# This script checks the references section of a DOCX document by verifying each citation’s title against Crossref metadata. 
# It flags potentially incorrect or fabricated references when the Crossref title does not appear in the input citation text.

import streamlit as st
import re
import time
import requests
from docx import Document
from io import BytesIO

st.title("Fabricated Reference Checker v1.0")

# Upload DOCX file
uploaded_file = st.file_uploader("Upload your DOCX file", type=["docx"])

# Required metadata fields (for future use)
required_fields = ["author", "title", "container-title", "issued"]

def extract_doi(text):
    match = re.search(r'(10\.\d{4,9}/[-._;()/:A-Z0-9]+)', text, re.I)
    return match.group(1).rstrip(' .;,') if match else None

def check_crossref(query):
    if query and query.startswith("10."):
        url = f"https://api.crossref.org/works/{query}"
        response = requests.get(url)
    else:
        url = "https://api.crossref.org/works"
        params = {"query.title": query or "", "rows": 1}
        response = requests.get(url, params=params)
    time.sleep(1)
    if response.status_code == 200:
        data = response.json()["message"]
        if "items" in data:
            return data["items"][0] if data["items"] else None
        return data
    return None

def is_title_in_reference(crossref_title, reference_text):
    norm_title = re.sub(r'\W+', '', crossref_title).lower()
    norm_ref = re.sub(r'\W+', '', reference_text).lower()
    return norm_title in norm_ref

if uploaded_file is not None:
    # Read the uploaded DOCX file into memory
    file_bytes = BytesIO(uploaded_file.read())
    doc = Document(file_bytes)

    # Extract full text from all paragraphs
    text = "\n".join([para.text for para in doc.paragraphs])

    # Try to extract references section
    match = re.search(r'\bReferences\b', text, re.IGNORECASE)
    if match:
        references_text = text[match.end():].strip()
        reference_list = [ref.strip() for ref in references_text.split("\n") if ref.strip()]
    else:
        st.warning("No 'References' section found. Please ensure your document includes a heading or line with the word References to mark the start of the reference list")
        reference_list = []

    if reference_list:
        st.info(f"Found {len(reference_list)} references. Checking...")

        correct_count = 0
        incorrect_count = 0
        incorrect_references = []

        # Display progress bar
        progress_bar = st.progress(0)

        for i, ref in enumerate(reference_list, 1):
            st.write(f"**Checking Reference {i}:**")
            st.write(ref)

            doi = extract_doi(ref)
            if doi:
                st.write(f"🆔 Extracted DOI: {doi}")

            search_target = doi if doi else ref
            crossref_entry = check_crossref(search_target)

            if crossref_entry:
                crossref_title = crossref_entry.get("title", [""])[0]
                st.success(f"✅ Found in Crossref: {crossref_title}")

                if is_title_in_reference(crossref_title, ref):
                    st.success("✅ Crossref title FOUND in reference text")
                    correct_count += 1
                else:
                    st.error("❌ Crossref title NOT found in citation from input document")
                    st.warning("⚠ Reference might be incorrect or fabricated based on title mismatch")
                    incorrect_count += 1
                    incorrect_references.append(ref)
            else:
                st.error("❌ Not found in Crossref")
                incorrect_count += 1
                incorrect_references.append(ref)

            progress_bar.progress(i / len(reference_list))

        st.markdown("---")
        st.header("Summary Report")
        st.write(f"✅ Correct references: {correct_count}")
        st.write(f"❌ Incorrect/potentially fabricated references: {incorrect_count}")

        if incorrect_references:
            st.subheader("Potentially Incorrect or Fabricated References")
            for i, ref in enumerate(incorrect_references, 1):
                st.write(f"{i}. {ref}")
        else:
            st.balloons()
            st.success("🎉 All references appear correct!")

else:
    st.info("Please upload a DOCX file to start the reference check.")


# In[2]:


