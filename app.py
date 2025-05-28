from flask import Flask, request, send_from_directory, Response
from dotenv import load_dotenv
load_dotenv() 
from functools import wraps
import os
import requests
import fitz
import tempfile
import dotenv


app = Flask(__name__)

UPLOAD_FOLDER = "uploads"
USERNAME = os.getenv("username")
PASSWORD = os.getenv("password")

# Create uploads dir if not exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


# Basic auth decorator
def check_auth(username, password):
    return username == USERNAME and password == PASSWORD


def authenticate():
    return Response("Unauthorized", 401,
                    {"WWW-Authenticate": 'Basic realm="Login Required"'})


def requires_auth(f):

    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return authenticate()
        return f(*args, **kwargs)

    return decorated


# Home
@app.route("/")
def index():
    return "PDF Upload/Download API is running!"

from requests.auth import HTTPBasicAuth



from bs4 import BeautifulSoup


def extract_clean_text_from_pdf(pdf_path):
    """
    Extracts HTML from PDF pages, parses it with BeautifulSoup, and returns clean text.
    
    Parameters:
    - pdf_path (str): Path to the PDF file.
    
    Returns:
    - str: Cleaned and concatenated text from all pages.
    """
    full_text = []

    with fitz.open(stream=pdf_path, filetype="pdf") as doc:
        for page in doc:
            html = page.get_text("html")
            soup = BeautifulSoup(html, "html.parser")

            # Remove all style, class, and other non-semantic attributes
            for tag in soup.find_all(True):
                tag.attrs = {}
            # Remove empty elements including those with empty inline children
            for p in soup.find_all("p"):
                if not p.get_text(strip=True):
                    p.decompose()

            # Merge consecutive <p> tags into one, if they contain only inline text (no block tags inside)
            # This reduces vertical gaps from multiple <p>
            new_p_contents = []
            for p in soup.find_all("p"):
                text = p.get_text(separator=" ", strip=True)
                if text:
                    new_p_contents.append(text)

            # Replace entire body with combined paragraphs joined by a single <p>
            combined_html = "".join(f"<p>{content}</p>" for content in new_p_contents)
            full_text.append(combined_html)

    return "\n".join(full_text)

# Example usage:
# cleaned_text = extract_clean_text_from_pdf("example.pdf")
# print(cleaned_text)


@app.route("/attachment/<headerId>/<attachmentId>")
def proxy_stream(headerId, attachmentId):
    HACKATHON_BASEURL = os.getenv("HACKATHON_BASEURL")
    HACKATHON_USERNAME = os.getenv("HACKATHON_USERNAME")
    HACKATHON_PASSWORD = os.getenv("HACKATHON_PASSWORD")
    target_url = (
        f"{HACKATHON_BASEURL}/fscmRestApi/resources/11.13.18.05/"
        f"omSalesOrders/{headerId}/child/attachments/{attachmentId}/enclosure/FileContents"
    )

    try:
        r = requests.get(
            target_url,
            auth=HTTPBasicAuth(HACKATHON_USERNAME, HACKATHON_PASSWORD),
            stream=True,
            timeout=None
        )
        r.raise_for_status()
    except requests.exceptions.RequestException as e:
        return {"error": str(e)}, 500
    all_text = extract_clean_text_from_pdf(r.content)

    return all_text, 200, {"Content-Type": "text/plain"}

@app.route("/attachment/<headerId>/<orderingDocumentID>/<purchasingOrderID>")
def bothdocs(headerId, orderingDocumentID, purchasingOrderID):
    HACKATHON_BASEURL = os.getenv("HACKATHON_BASEURL")
    HACKATHON_USERNAME = os.getenv("HACKATHON_USERNAME")
    HACKATHON_PASSWORD = os.getenv("HACKATHON_PASSWORD")
    res = {}
    for i, docID in enumerate([orderingDocumentID, purchasingOrderID]):
        all_text = ""
        target_url = (
            f"{HACKATHON_BASEURL}/fscmRestApi/resources/11.13.18.05/"
            f"omSalesOrders/{headerId}/child/attachments/{docID}/enclosure/FileContents"
        )

        try:
            r = requests.get(
                target_url,
                auth=HTTPBasicAuth(HACKATHON_USERNAME, HACKATHON_PASSWORD),
                stream=True,
                timeout=None
            )
            r.raise_for_status()
        except requests.exceptions.RequestException as e:
            return {"error": str(e)}, 500
        all_text = extract_clean_text_from_pdf(r.content)
        if i==0:
            res['ordering_document'] = all_text
        else:
            res['purchasing_order'] = all_text


    return res, 200, {"Content-Type": "application/json"}

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
