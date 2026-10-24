
import os
import json
import streamlit as st
import pandas as pd
from pypdf import PdfReader
from dotenv import load_dotenv
from google import genai
from docx import Document
from io import BytesIO

load_dotenv()

API_KEY = os.getenv("GEMINI_API_KEY")
MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")

st.set_page_config(
    page_title="AI Document Comparison Assistant",
    page_icon="📄",
    layout="wide"
)

# ---------------- CSS ----------------

st.markdown("""
<style>
.stApp {
    background: linear-gradient(120deg, #f8fafc, #eef6ff);
}
.block-container {
    max-width: 1200px;
    padding-top: 2rem;
}
h1 {
    color: #24344d;
}
div.stButton > button {
    background: #dc3d16;
    color: white;
    border: none;
    border-radius: 8px;
    min-height: 42px;
    font-weight: 600;
}
div.stButton > button:hover {
    background: #b92d0d;
    color: white;
}
</style>
""", unsafe_allow_html=True)


# ---------------- HELPERS ----------------

def extract_text(uploaded_pdf):
    reader = PdfReader(uploaded_pdf)
    pages = []

    for page_no, page in enumerate(reader.pages, 1):
        text = page.extract_text() or ""
        if text.strip():
            pages.append(f"Page {page_no}:\n{text}")

    return "\n\n".join(pages)


def ask_gemini(prompt):
    if not API_KEY:
        raise ValueError(
            "GEMINI_API_KEY is missing from your .env file."
        )

    client = genai.Client(api_key=API_KEY)
    response = client.models.generate_content(
        model=MODEL,
        contents=prompt
    )

    if not response.text:
        raise ValueError("Gemini returned an empty response.")

    return response.text


def create_report(results):
    doc = Document()
    doc.add_heading("AI Document Comparison Report", 0)

    sections = [
        ("Summary A", "summary_a"),
        ("Summary B", "summary_b"),
        ("Similarities", "similarities"),
        ("Differences", "differences"),
        ("Key Details", "key_details"),
        ("Conclusion", "conclusion"),
        ("Limitations", "limitations"),
    ]

    for title, key in sections:
        doc.add_heading(title, level=1)
        value = results.get(key, "")

        if key == "key_details" and isinstance(value, list):
            table = doc.add_table(rows=1, cols=4)
            table.style = "Table Grid"

            headers = [
                "Detail", "Document A", "Document B", "Status"
            ]
            for cell, heading in zip(table.rows[0].cells, headers):
                cell.text = heading

            for item in value:
                cells = table.add_row().cells
                cells[0].text = str(item.get("detail", ""))
                cells[1].text = str(item.get("document_a", ""))
                cells[2].text = str(item.get("document_b", ""))
                cells[3].text = str(item.get("status", ""))

        elif isinstance(value, list):
            for item in value:
                doc.add_paragraph(str(item), style="List Bullet")

        else:
            doc.add_paragraph(str(value))

    buffer = BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer.getvalue()


# ---------------- HEADER ----------------

st.title("📄 AI Document Comparison Assistant")

st.write(
    "Upload two PDF documents to compare their content, summaries, "
    "similarities, differences, and key details."
)

st.info(
    "Suitable for comparing syllabuses, policies, project "
    "requirements, manuals, and other text-based documents."
)


# ---------------- UPLOADS ----------------

left, right = st.columns(2)

with left:
    st.subheader("🟦 Document A")
    pdf_a = st.file_uploader(
        "Upload the first PDF",
        type=["pdf"],
        key="upload_a"
    )

with right:
    st.subheader("🟩 Document B")
    pdf_b = st.file_uploader(
        "Upload the second PDF",
        type=["pdf"],
        key="upload_b"
    )


# ---------------- COMPARISON ----------------

if st.button("🔍 Compare Documents", use_container_width=True):

    if not pdf_a or not pdf_b:
        st.warning("Please upload both PDF documents.")
    else:
        try:
            text_a = extract_text(pdf_a)
            text_b = extract_text(pdf_b)

            if not text_a.strip() or not text_b.strip():
                st.error(
                    "One PDF has no extractable text. "
                    "Scanned PDFs may need OCR."
                )
                st.stop()

            st.success("Both PDFs were read successfully.")

            # Keep enough room for the model context.
            # For very large documents, add chunking/RAG.
            prompt = f"""
You are an accurate document comparison assistant.

Compare Document A and Document B.
Use only the information provided. Do not invent facts.
If a detail is missing, write "Not found in the provided text."

Return ONLY valid JSON, with these exact keys:
{{
  "summary_a": "A concise but informative summary of A",
  "summary_b": "A concise but informative summary of B",
  "similarities": ["shared point 1", "shared point 2"],
  "differences": [
    {{
      "topic": "topic name",
      "document_a": "what A says",
      "document_b": "what B says",
      "status": "Changed, Added, Removed, or Same"
    }}
  ],
  "key_details": [
    {{
      "detail": "detail name",
      "document_a": "value from A",
      "document_b": "value from B",
      "status": "Changed, Added, Removed, or Same"
    }}
  ],
  "conclusion": "Overall conclusion",
  "limitations": ["missing or unspecified information"]
}}

DOCUMENT A:
{text_a}

DOCUMENT B:
{text_b}
"""

            with st.spinner(
                "🤖 Comparing documents and preparing all sections..."
            ):
                raw = ask_gemini(prompt)

            # Remove optional Markdown fences.
            cleaned = raw.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("\n", 1)[1]
                cleaned = cleaned.rsplit("```", 1)[0].strip()

            results = json.loads(cleaned)

            # Store results and source filenames in the session.
            st.session_state["comparison_results"] = results
            st.session_state["filename_a"] = pdf_a.name
            st.session_state["filename_b"] = pdf_b.name

            st.success("Document comparison completed!")

        except json.JSONDecodeError:
            st.error(
                "Gemini returned an invalid JSON response. "
                "Click Compare Documents and try again."
            )
        except Exception as error:
            st.error(f"Comparison failed: {error}")


# ---------------- DISPLAY RESULTS ----------------

if "comparison_results" in st.session_state:

    result = st.session_state["comparison_results"]

    st.divider()
    st.header("📊 Comparison Results")

    # Separate clickable tabs, like your screenshot.
    tab_a, tab_b, tab_sim, tab_diff, tab_key, tab_con = st.tabs([
        "Summary A",
        "Summary B",
        "Similarities",
        "Differences",
        "Key Details",
        "Conclusion"
    ])

    with tab_a:
        st.subheader(st.session_state.get("filename_a", "Document A"))
        st.write(result.get("summary_a", "No summary available."))

    with tab_b:
        st.subheader(st.session_state.get("filename_b", "Document B"))
        st.write(result.get("summary_b", "No summary available."))

    with tab_sim:
        st.subheader("Common Information")
        similarities = result.get("similarities", [])

        if similarities:
            for index, item in enumerate(similarities, 1):
                with st.expander(f"{index}. {item}"):
                    st.write(item)
        else:
            st.info("No similarities were returned.")

    with tab_diff:
        st.subheader("Changes Found")
        differences = result.get("differences", [])

        if differences:
            for index, item in enumerate(differences, 1):
                topic = item.get("topic", f"Difference {index}")

                with st.expander(f"{index}. {topic}"):
                    st.write("**Document A:**")
                    st.write(item.get("document_a", "Not specified"))

                    st.write("**Document B:**")
                    st.write(item.get("document_b", "Not specified"))

                    st.write(
                        f"**Status:** {item.get('status', 'Not specified')}"
                    )
        else:
            st.info("No differences were returned.")

    with tab_key:
        st.subheader("Important Details")
        details = result.get("key_details", [])

        if details:
            table_rows = []

            for item in details:
                table_rows.append({
                    "Detail": item.get("detail", ""),
                    "Document A": item.get("document_a", ""),
                    "Document B": item.get("document_b", ""),
                    "Status": item.get("status", "")
                })

            st.dataframe(
                pd.DataFrame(table_rows),
                use_container_width=True,
                hide_index=True
            )
        else:
            st.info("No key details were returned.")

    with tab_con:
        st.subheader("Overall Conclusion")
        st.write(result.get("conclusion", "No conclusion available."))

        st.subheader("Limitations")
        limitations = result.get("limitations", [])

        if limitations:
            for item in limitations:
                st.markdown(f"- {item}")
        else:
            st.write("No limitations were specified.")

    # ---------------- DOWNLOAD ----------------

    st.divider()
    st.header("📥 Download Your Report")

    try:
        report_bytes = create_report(result)

        st.download_button(
            label="📄 Download Comparison Report (.docx)",
            data=report_bytes,
            file_name="AI_Document_Comparison_Report.docx",
            mime=(
                "application/vnd.openxmlformats-officedocument."
                "wordprocessingml.document"
            ),
            use_container_width=True
        )
    except Exception as error:
        st.error(f"Unable to create the report: {error}")

    if st.button("🔄 Start a New Comparison"):
        st.session_state.pop("comparison_results", None)
        st.session_state.pop("filename_a", None)
        st.session_state.pop("filename_b", None)
        st.rerun()
