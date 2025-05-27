from flask import Flask, request, send_from_directory, Response
from functools import wraps
import os
import requests
import fitz
import tempfile

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


# Upload endpoint
@app.route("/upload", methods=["POST"])
@requires_auth
def upload_file():
    if "file" not in request.files:
        return "No file part", 400
    file = request.files["file"]
    if file.filename == "":
        return "No selected file", 400
    filepath = os.path.join(UPLOAD_FOLDER, file.filename)
    file.save(filepath)
    return f"File {file.filename} uploaded successfully!"


# Download endpoint
@app.route("/download/<filename>", methods=["GET"])
@requires_auth
def download_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename, as_attachment=True)


# Home
@app.route("/")
def index():
    return "PDF Upload/Download API is running!"


# Upload form page (HTML)
@app.route("/upload-form")
@requires_auth
def upload_form():
    return """
    <!doctype html>
    <html>
    <head>
        <title>Upload PDF</title>
    </head>
    <body>
        <h2>Upload a PDF</h2>
        <form action="/upload" method="post" enctype="multipart/form-data">
            <input type="file" name="file" accept=".pdf" required><br><br>
            <input type="submit" value="Upload">
        </form>
    </body>
    </html>
    """


@app.route("/files", methods=["GET"])
@requires_auth
def list_files():
    files = os.listdir(UPLOAD_FOLDER)
    list_items = ""
    for file in files:
        if file.endswith(".pdf"):
            list_items += f"""
                <li>
                    {file}
                    [<a href="/download/{file}" target="_blank">Download</a>]
                    <form method="POST" action="/delete/{file}" style="display:inline;">
                        <button type="submit" onclick="return confirm('Delete {file}?')">Delete</button>
                    </form>
                </li>
            """
    return f"""
    <!doctype html>
    <html>
    <head><title>Uploaded PDFs</title></head>
    <body>
        <h2>Available PDFs</h2>
        <ul>
            {list_items if list_items else '<li>No files found.</li>'}
        </ul>
        <a href="/upload-form">Upload another</a>
    </body>
    </html>
    """


@app.route("/delete/<filename>", methods=["POST"])
@requires_auth
def delete_file(filename):
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    if os.path.exists(filepath):
        os.remove(filepath)
        return f"Deleted {filename}. <a href='/files'>Back</a>"
    else:
        return f"{filename} not found. <a href='/files'>Back</a>", 404


from requests.auth import HTTPBasicAuth




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
    doc = fitz.open(stream=r.content, filetype="pdf")
    all_text = ""
    for page_num in range(len(doc)):
        page = doc.load_page(page_num)
        text = page.get_text()
        all_text += f"\n--- Page {page_num + 1} ---\n{text}"

    return all_text, 200, {"Content-Type": "text/plain"}
    # def generate():
    #     for chunk in r.iter_content(chunk_size=8192):
    #         if chunk:
    #             yield chunk

    # content_type = r.headers.get("Content-Type", "application/octet-stream")
    # return Response(generate(), content_type=content_type)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
