from flask import (
    Flask,
    render_template,
    request,
    session,
    redirect,
    url_for,
    jsonify,
    send_from_directory,
)
from dotenv import load_dotenv
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import os
import arxiv
import datetime
import json
import google.generativeai as genai
from flaskext.markdown import Markdown

# Load environment variables
load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

app = Flask(__name__)
app.secret_key = "your_secret_key"  # Replace with your actual secret key

# Initialize Markdown
Markdown(app)

# Set up rate limiting
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://",
)

# Initialize Google Generative AI
genai.configure(api_key=GOOGLE_API_KEY)
# Set the model configuration correctly
generation_config = {
    # Remove the unsupported "response_mime_type" parameter
    # Instead use proper parameters the SDK supports
    "temperature": 0.7,  # Controls randomness (0.0 to 1.0)
    "top_p": 0.95,  # Nucleus sampling
    "top_k": 40,  # Limits vocabulary selection
}
model = genai.GenerativeModel("gemini-1.5-flash", generation_config=generation_config)


def get_papers(topic):
    try:
        # Search for papers on arXiv
        search = arxiv.Search(
            query=topic, max_results=5, sort_by=arxiv.SortCriterion.Relevance
        )

        papers = {}
        for i, paper in enumerate(search.results()):
            # Format the authors
            authors = ", ".join([author.name for author in paper.authors])

            # Use a simple summary instead of calling the API
            summary_text = f"This is a simplified summary of the paper. The original abstract is: {paper.summary[:200]}..."

            # Get the PDF URL
            pdf_url = paper.pdf_url

            papers[str(i)] = {
                "title": paper.title,
                "authors": authors,
                "published": paper.published.strftime("%B %d, %Y"),
                "summary": summary_text,
                "url": pdf_url,
            }

        return papers
    except Exception as e:
        app.logger.error(f"Error fetching papers: {e}")
        return {}


def generate_summary(text):
    # This function is used in the template to format the summary
    # Add the 'safe' filter in the template to render HTML from Markdown
    return text


@app.context_processor
def utility_processor():
    return dict(generate_summary=generate_summary)


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        session.clear()
        topic = request.form.get("topic")

        if not topic:
            return render_template("index.html", error="Please enter a search topic.")

        session["topic"] = topic  # Store topic in session

        try:
            papers = get_papers(topic)

            if not papers:
                return render_template(
                    "index.html", error="No papers found. Please try a different topic."
                )

            # Store in session
            session["papers"] = papers

            # Initialize chat history as empty list
            session["chat_history"] = []

            return redirect(url_for("results"))
        except Exception as e:
            app.logger.error(f"Error in index route: {str(e)}")
            return render_template("index.html", error=f"An error occurred: {str(e)}")

    return render_template("index.html")


@app.route("/results")
def results():
    papers = session.get("papers", {})
    return render_template("results.html", papers=papers)


@app.route("/search", methods=["POST"])
@limiter.limit("10 per minute")
def search():
    query = request.form.get("query", "")

    if not query:
        return jsonify([])

    try:
        # Search for papers on arXiv
        search = arxiv.Search(
            query=query, max_results=5, sort_by=arxiv.SortCriterion.Relevance
        )

        results = []
        for paper in search.results():
            # Generate summary using Google Generative AI
            prompt = f"Summarize the following research paper in 3-4 sentences, highlighting the main contributions and findings:\nTitle: {paper.title}\nAbstract: {paper.summary}"
            summary_response = model.generate_content(prompt)

            # Handle response from the model
            summary = summary_response.text

            # Format the authors
            authors = ", ".join([author.name for author in paper.authors])

            results.append(
                {
                    "title": paper.title,
                    "authors": authors,
                    "published": paper.published.strftime("%B %d, %Y"),
                    "summary": summary,
                    "url": paper.pdf_url,  # Make sure PDF URL is included
                }
            )

        return jsonify(results)

    except Exception as e:
        app.logger.error(f"Error processing search: {str(e)}")
        return jsonify({"error": str(e)}), 500


@app.route("/chat", methods=["POST"])
@limiter.limit("5 per minute")
def chat():
    try:
        papers = session.get("papers")
        if not papers:
            if request.is_json:
                return (
                    jsonify(
                        {"error": "No papers available. Please start a new search."}
                    ),
                    400,
                )
            else:
                return redirect(url_for("index"))

        # Process JSON requests
        if request.is_json:
            data = request.get_json()
            user_message = data.get("message")
            app.logger.info(f"Received chat message: {user_message}")

            try:
                # Create a context from the papers for the AI
                paper_context = ""
                for paper_id, paper in papers.items():
                    paper_context += f"Paper {int(paper_id) + 1}:\n"
                    paper_context += f"Title: {paper['title']}\n"
                    paper_context += f"Authors: {paper['authors']}\n"
                    paper_context += f"Published: {paper['published']}\n"
                    paper_context += f"Summary: {paper['summary']}\n\n"

                # Generate response using Google Generative AI
                prompt = f"""You are a helpful research assistant. The user is asking about these research papers:

{paper_context}

User question: {user_message}

Provide a helpful, informative response based on the papers. Format your response using Markdown with proper headings, lists, emphasis, and other formatting as appropriate. If the question cannot be answered based on the papers, politely explain that and provide general information if possible."""

                # Fix: Remove any custom config that might be causing the error
                response = model.generate_content(prompt)

                # Handle response from the model
                response_text = response.text

                # Update chat history in session
                chat_history = session.get("chat_history", [])
                chat_history.append({"role": "user", "content": user_message})
                chat_history.append({"role": "assistant", "content": response_text})
                session["chat_history"] = chat_history

                app.logger.info(f"Sending AI response")
                return jsonify({"response": response_text})
            except Exception as e:
                app.logger.error(f"Error generating response: {str(e)}")
                return jsonify({"error": f"Error generating response: {str(e)}"}), 500
        # Process form submissions (from chat form)
        else:
            user_message = request.form.get("message")
            if not user_message:
                return redirect(url_for("results"))

            # Update chat history
            chat_history = session.get("chat_history", [])
            chat_history.append({"role": "user", "content": user_message})

            # Create a context from the papers for the AI
            paper_context = ""
            for paper_id, paper in papers.items():
                paper_context += f"Paper {int(paper_id) + 1}:\n"
                paper_context += f"Title: {paper['title']}\n"
                paper_context += f"Authors: {paper['authors']}\n"
                paper_context += f"Published: {paper['published']}\n"
                paper_context += f"Summary: {paper['summary']}\n\n"

            # Generate response using Google Generative AI
            prompt = f"""You are a helpful research assistant. The user is asking about these research papers:

{paper_context}

User question: {user_message}

Provide a helpful, informative response based on the papers. Format your response using Markdown with proper headings, lists, emphasis, and other formatting as appropriate. If the question cannot be answered based on the papers, politely explain that and provide general information if possible."""

            # Fix: Remove any custom config that might be causing the error
            response = model.generate_content(prompt)

            # Handle response from the model
            response_text = response.text

            chat_history.append({"role": "assistant", "content": response_text})
            session["chat_history"] = chat_history
            return redirect(url_for("results"))
    except Exception as e:
        app.logger.error(f"Error in chat route: {str(e)}")
        if request.is_json:
            return jsonify({"error": str(e)}), 500
        else:
            return redirect(url_for("results"))


@app.route("/kit-papers")
def kit_papers():
    """Display all papers available in the papers folder with titles and summaries from JSON"""
    papers_dir = os.path.join(app.root_path, "papers")
    papers = []

    # Try to load paper summaries from JSON file
    summaries_file = os.path.join(app.root_path, "papers", "paper_summaries.json")
    paper_summaries = {}

    if os.path.exists(summaries_file):
        try:
            with open(summaries_file, "r") as f:
                data = json.load(f)
                for paper_data in data.get("papers", []):
                    # Extract filename from path
                    path = paper_data.get("path", "")
                    filename = os.path.basename(path)
                    paper_summaries[filename] = {
                        "title": paper_data.get("title", ""),
                        "summary": paper_data.get("summary", ""),
                    }
        except Exception as e:
            app.logger.error(f"Error loading paper summaries: {e}")

    # Get all PDF files from the papers folder
    for filename in os.listdir(papers_dir):
        if filename.endswith(".pdf"):
            # Get file creation/modification time
            file_path = os.path.join(papers_dir, filename)
            timestamp = os.path.getmtime(file_path)
            date = datetime.datetime.fromtimestamp(timestamp).strftime("%B %d, %Y")

            # Use title and summary from JSON if available, otherwise use defaults
            if filename in paper_summaries:
                title = paper_summaries[filename]["title"]
                summary = paper_summaries[filename]["summary"]
            else:
                # Extract title from filename (remove extension and replace underscores with spaces)
                title = (
                    os.path.splitext(filename)[0]
                    .replace("_", " ")
                    .replace("-", " ")
                    .title()
                )
                summary = ""

            papers.append(
                {"title": title, "filename": filename, "date": date, "summary": summary}
            )

    # Sort papers by date (newest first)
    papers.sort(key=lambda x: x["date"], reverse=True)

    return render_template("kit_papers.html", papers=papers)


@app.route("/view-paper/<filename>")
def view_paper(filename):
    """View a paper from the papers folder directly in the browser"""
    papers_dir = os.path.join(app.root_path, "papers")
    return send_from_directory(papers_dir, filename, as_attachment=False)


@app.route("/download-paper/<filename>")
def download_paper(filename):
    """Download a paper from the papers folder"""
    papers_dir = os.path.join(app.root_path, "papers")
    return send_from_directory(papers_dir, filename, as_attachment=True)


if __name__ == "__main__":
    app.run(debug=True)
