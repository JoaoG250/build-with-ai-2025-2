import logging
import sys
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from .client import MCPClient

load_dotenv()


templates = Jinja2Templates(directory="build_with_ai/templates")

mcp_client = MCPClient()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Conecta ao servidor MCP durante o tempo de vida da aplicação."""
    try:
        await mcp_client.connect_to_server("build_with_ai.server")
    except Exception as e:
        logging.error(f"Erro ao conectar com o servidor MCP: {str(e)}")
        sys.exit(1)

    yield

    await mcp_client.cleanup()


app = FastAPI(
    title="Gemini Chat with MCP Tools",
    description="A FastAPI backend for interacting with Gemini and MCP tools.",
    version="1.0.0",
    lifespan=lifespan,
)


class ChatQuery(BaseModel):
    query: str


@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    """Renderiza a página inicial com o template HTML contendo o chat."""

    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/chat")
async def chat_endpoint(chat_query: ChatQuery):
    """Processa a consulta do usuário e retorna a resposta do MCP."""

    user_query = chat_query.query
    if not user_query:
        raise HTTPException(status_code=400, detail="Nenhum prompt recebido")

    try:
        response_text = await mcp_client.process_query(user_query)
        return JSONResponse(content={"response": response_text})
    except Exception as e:
        logging.error(f"Erro ao processar a consulta: {str(e)}")
        raise HTTPException(status_code=500, detail="Erro ao processar a consulta.")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app)
