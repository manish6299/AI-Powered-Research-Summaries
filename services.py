import arxiv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser

from dotenv import load_dotenv

load_dotenv()


def get_papers(topic):
    try:
        search = arxiv.Search(
            query=topic, max_results=5, sort_by=arxiv.SortCriterion.Relevance
        )
        papers = {}
        for result in arxiv.Client().results(search):
            papers[result.title] = {
                "entry_id": result.entry_id,
                "summary": result.summary,
                "pdf_url": result.pdf_url,
            }
        return papers
    except Exception as e:
        print(f"Error fetching papers: {str(e)}")
        return None


def generate_summary(text):
    llm = ChatGoogleGenerativeAI(model="gemini-1.5-flash")
    template = """You give concise, easy to understand summaries of research papers. Keep it under 200 words.
    Text: {text}
    Summary:"""
    prompt = PromptTemplate(input_variables=["text"], template=template)
    chain = prompt | llm | StrOutputParser()
    return chain.invoke(text)


def chat_with_ai(message, papers):
    llm = ChatGoogleGenerativeAI(model="gemini-1.5-flash", temperature=0.3)

    # Create context by joining paper summaries, then trim to a max length to avoid token overflow.
    full_context = " ".join([paper["summary"] for paper in papers.values()])
    # Truncate context to 4000 characters (adjust this threshold as needed)
    max_context_length = 4000
    summaries = full_context[:max_context_length]

    # Enhanced prompt template for concise, focused answers.
    template = """You are a research assistant. Based solely on the provided context, answer the user's question with a concise and focused response. Adhere to the following guidelines:
- Provide a answer to the query under 150 words.
- Clearly list the main findings and cite the relevant paper titles.

**Context:** {summaries}

**Question:** {message}

answer should be short, concise and in one or two paragraph
"""

    prompt = PromptTemplate(template=template, input_variables=["summaries", "message"])

    try:
        chain = prompt | llm | StrOutputParser()
        response = chain.invoke({"summaries": summaries, "message": message})
        final_response = response.strip()
        if not final_response:
            return "I couldn't generate a valid response. Please try rephrasing your question."
        return final_response
    except Exception as e:
        return f"An error occurred while generating the response: {str(e)}"
