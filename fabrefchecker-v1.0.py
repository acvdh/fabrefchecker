#!/usr/bin/env python
# coding: utf-8

# Written by Dr. A.C. van der Heijden, version 2.0
# This script checks the references section of a DOCX document by performing two tasks:
# 1] DOI Validation: It extracts the DOI from the input document and looks it up in the Crossref database (a repository of scholarly publications).
# 2] Title Verification: If a DOI is found, it checks if the input reference title matches the one in Crossref Database.

# The script flags references if:
# 1] The DOI is missing or cannot be found in the Crossref database
# 2] The reference input title does not match the title in the Crossref Database

# Version log: v2.0 displays a message if a doi is lacking, updated progress bar

import streamlit as st
import re
import time
import requests
from docx import Document
from io import BytesIO

st.title("Fabricated Reference Checker v2.0")

st.markdown("""
    ### How does it work?
    This tool checks the references in the uploaded DOCX document by:

    1. Verifying the DOI for each reference

    2. Checking if the reference title matches the information in the Crossref Database (a public collection of scholarly publications).
    If the titles do not fully match, the reference will be flagged as potentially incorrect or fabricated. <br> <br>
    **Important:** Please double-check flagged references manually. This tool is intended as a first check — not as a final evaluation.
""",unsafe_allow_html=True)

# Upload DOCX file
uploaded_file = st.file_uploader("Upload your DOCX file:", type=["docx"])

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

    # Set total_references only if references are found
    total_references = len(reference_list)

    if total_references > 0:
        # Show a temporary message indicating the number of references
        status_message = st.info(f"Found {total_references} references. Checking...")
        
        correct_count = 0
        incorrect_count = 0
        incorrect_references = []
        no_doi_count = 0  # Counter for references without DOI
        with_doi_count = 0  # Counter for references with DOI
        no_doi_references = []  # List to store references without DOI

        # Display progress bar
        progress_bar = st.progress(0)

        for i, ref in enumerate(reference_list, 1):
            st.write(f"**Checking Reference {i}:**")
            st.write(ref)

            # Attempt to extract DOI from the reference
            doi = extract_doi(ref)
            
            if doi:
                st.write(f"🆔 Extracted DOI: {doi}")
                with_doi_count += 1  # Increment DOI reference counter
            else:
                # If no DOI is found, display a warning message and skip further processing
                st.warning(f"⚠ No DOI found for Reference {i}: {ref}")
                # Increment the counter for references without DOI and store the reference
                no_doi_count += 1
                no_doi_references.append(ref)
                continue  # Skip to the next reference (no need for Crossref check)

            # Query Crossref to check the metadata using DOI
            crossref_entry = check_crossref(doi)

            if crossref_entry:
                crossref_title = crossref_entry.get("title", [""])[0]
                st.success(f"✅ Found in Crossref Database: {crossref_title}")

                # Perform title comparison only if DOI is found
                if is_title_in_reference(crossref_title, ref):
                    st.success("✅ The reference title from the database matches the one in the input document!")
                    correct_count += 1
                else:
                    st.error("❌ The reference title from the database does not match the one in the input document")
                    st.warning("⚠ This reference might be incorrect or fabricated based on a title mismatch")
                    incorrect_count += 1
                    incorrect_references.append(ref)
            else:
                st.error("❌ Not found in Crossref database")
                incorrect_count += 1
                incorrect_references.append(ref)

            # Update the progress bar after each reference
            progress_bar.progress((i) / total_references)  # Adjusting progress bar scale

        # After all references have been checked, set the progress bar to full
        progress_bar.progress(1.0)  # Set to 100% to show full green progress bar

        # Clear the initial "Found X references..." message
        status_message.empty()

        # Calculate percentages based on references with a DOI
        total_verified_references = with_doi_count  # Total references with a DOI

        if total_verified_references > 0:
            # Calculate correct and incorrect percentages for references with DOI
            correct_percentage = (correct_count / total_verified_references) * 100
            incorrect_percentage = (incorrect_count / total_verified_references) * 100
        else:
            correct_percentage = 0
            incorrect_percentage = 0

        # Calculate other percentages
        if total_references > 0:
            no_doi_percentage = (no_doi_count / total_references) * 100
            with_doi_percentage = (with_doi_count / total_references) * 100
            doi_required_percentage = (with_doi_count / total_references) * 100
        else:
            no_doi_percentage = 0
            with_doi_percentage = 0
            doi_required_percentage = 0

        st.markdown("---")
        st.header("Summary Report")

        # Display counts and percentages with the format "X out of Y (Z%)"
        st.write(f"💡 {with_doi_count} out of {total_references} ({doi_required_percentage:.2f}%) references contained a DOI which is required for verification")
        st.write(f"✅ Validated references (out of those that contained a DOI): {correct_count} out of {total_verified_references} ({correct_percentage:.2f}%)")
        st.write(f"❌ Incorrect/potentially fabricated references (out of those that contained a DOI): {incorrect_count} out of {total_verified_references} ({incorrect_percentage:.2f}%)")

        # List references potentially incorrect/fabricated
        if incorrect_references:
            st.subheader("Potentially Incorrect or Fabricated References")
            for i, ref in enumerate(incorrect_references, 1):
                st.write(f"{i}. {ref}")
                
        # List references without DOI
        if no_doi_references:
            st.subheader("References without DOI (Cannot be verified):")
            for i, ref in enumerate(no_doi_references, 1):
                st.write(f"{i}. {ref}")

        # Show success balloons and message only if there were no incorrect/fabricated references
        if incorrect_count == 0:
            st.balloons()
            st.success("🎉 All references appear correct!")
        #else:
            #st.warning("❗ Some references may be incorrect or fabricated")

else:
    st.info("Please upload a DOCX file to start the reference check.")
