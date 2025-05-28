from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime

from mcp.server.fastmcp import FastMCP
from sqlalchemy import func
from sqlmodel import Session, select

from build_with_ai.db.models import Product
from build_with_ai.db.seed import seed_products
from build_with_ai.db.session import get_session, init_db


@dataclass
class AppContext:
    session: Session


@asynccontextmanager
async def app_lifespan(server: FastMCP) -> AsyncIterator[AppContext]:
    """Gerencia o ciclo de vida da aplicação com contexto tipado"""
    init_db()
    session = get_session()
    seed_products(session)
    try:
        yield AppContext(session=session)
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


mcp = FastMCP("build-with-ai", lifespan=app_lifespan)


@mcp.tool(
    description="Consulta um produto pelo nome e retorna suas informações como uma string formatada"
)
def query_product_by_name(name: str) -> str:
    """Consulta um produto pelo nome e retorna suas informações como uma string formatada.

    Esta função recupera ou cria uma entrada de produto no banco de dados com um código de barras fixo e valores padrão.
    Ela utiliza a sessão atual do contexto da requisição para interagir com o banco de dados.
    A string retornada contém o nome, categoria, preço, data de validade, fabricante e código de barras do produto.

    Args:
        name (str): O nome do produto a ser consultado.

    Returns:
        str: Uma string formatada contendo as informações do produto. Exemplo de retorno:
        "Informações do produto:
        Nome: Produto Exemplo
        Categoria: Categoria Exemplo
        Preço: 10.99
        Data de Validade: 2024-12-31
        Fabricante: Fabricante Exemplo
        Código de barras: 1234567890123"
    """
    ctx: AppContext = mcp.get_context().request_context.lifespan_context  # type: ignore
    product = ctx.session.exec(
        select(Product).where(func.lower(Product.name).contains(name.lower()))
    ).first()
    if not product:
        return f"Produto com nome '{name}' não encontrado."
    response_lines = [
        "Informações do produto:",
        f"Nome: {product.name}",
        f"Categoria: {product.category}",
        f"Preço: {product.price:.2f}",
        f"Data de Validade: {product.expiry_date.strftime('%Y-%m-%d')}",
        f"Fabricante: {product.manufacturer}",
        f"Código de barras: {product.bar_code}",
    ]
    return "\n".join(response_lines)


@mcp.tool(
    description="Consulta produtos por categoria e retorna uma lista formatada de produtos"
)
def get_products_by_category(category: str) -> str:
    """Consulta produtos por categoria e retorna uma lista formatada de produtos.

    Esta função recupera todos os produtos de uma categoria específica do banco de dados.

    Args:
        category (str): A categoria dos produtos a serem consultados.

    Returns:
        str: Uma string formatada contendo os produtos encontrados na categoria especificada.
        Se nenhum produto for encontrado, uma mensagem apropriada é retornada. Exemplo de retorno:
        "Produtos na categoria 'Categoria Exemplo':
         - Produto 1 (Fabricante: Fabricante A, Preço: R$10.99)
         - Produto 2 (Fabricante: Fabricante B, Preço: R$15.49)"
    """
    ctx: AppContext = mcp.get_context().request_context.lifespan_context  # type: ignore
    products = ctx.session.exec(
        select(Product).where(func.lower(Product.category).contains(category.lower()))
    ).all()
    if not products:
        return f"Nenhum produto encontrado na categoria '{category}'."

    response_lines = [f"Produtos na categoria '{category}':"]
    for product in products:
        response_lines.append(
            f" - {product.name} (Fabricante: {product.manufacturer}, Preço: R${product.price:.2f})"
        )
    return "\n".join(response_lines)


@mcp.tool(
    description="Consulta produtos fora da data de validade e retorna uma lista formatada de produtos fora da data de validade"
)
def get_expired_products() -> str:
    """Consulta produtos fora da data de validade e retorna uma lista formatada de produtos fora da data de validade.

    Esta função verifica todos os produtos no banco de dados e retorna aqueles cuja data de validade já passou.
    Se nenhum produto for encontrado fora da data de validade, uma mensagem apropriada é retornada.

    Returns:
        str: Uma string formatada contendo os produtos fora da data de validade. Exemplo de retorno:
        "Produtos fora da data de validade:
         - Produto 1 (Data de validade: 2023-01-01, Código de barras: 1234567890123)
         - Produto 2 (Data de validade: 2023-02-15, Código de barras: 9876543210987)"
    """
    ctx: AppContext = mcp.get_context().request_context.lifespan_context  # type: ignore
    today = datetime.now().date()
    expired_products = ctx.session.exec(
        select(Product).where(Product.expiry_date < today)
    ).all()

    if not expired_products:
        return "Nenhum produto encontrado fora da data de validade."

    response_lines = ["Produtos fora da data de validade:"]
    for product in expired_products:
        response_lines.append(
            f" - {product.name} (Data de validade: {product.expiry_date.strftime('%Y-%m-%d')}, Código de barras: {product.bar_code})"
        )
    return "\n".join(response_lines)


@mcp.tool(description="Atualiza o preço de um produto pelo código de barras")
def update_product_price(bar_code: str, new_price: float) -> str:
    """Atualiza o preço de um produto pelo código de barras.

    Esta função busca um produto pelo código de barras e atualiza seu preço.

    Args:
        bar_code (str): O código de barras do produto a ser atualizado.
        new_price (float): O novo preço a ser definido para o produto.

    Returns:
        str: Uma mensagem indicando o sucesso ou falha da atualização do preço. Exemplo de retorno:
        "Preço do produto 'Produto Exemplo' (Código de barras: 1234567890123) atualizado de R$10.99 para R$12.99"
    """
    ctx: AppContext = mcp.get_context().request_context.lifespan_context  # type: ignore
    product = ctx.session.exec(
        select(Product).where(Product.bar_code == bar_code)
    ).first()

    if not product:
        return f"Produto com código de barras '{bar_code}' não encontrado."

    old_price = product.price
    product.price = new_price
    ctx.session.add(product)
    ctx.session.commit()
    ctx.session.refresh(product)

    return f"Preço do produto '{product.name}' (Código de barras: {bar_code}) atualizado de R${old_price:.2f} para R${new_price:.2f}."


@mcp.tool(
    description="Adiciona um novo produto ao banco de dados com as informações fornecidas"
)
def add_new_product(
    name: str,
    category: str,
    price: float,
    bar_code: str,
    expiry_date: str,
    manufacturer: str,
) -> str:
    """Adiciona um novo produto ao banco de dados com as informações fornecidas.

    Esta função verifica se um produto com o mesmo código de barras já existe.
    Se existir, retorna uma mensagem informando que o produto já existe.
    Se não existir, cria um novo produto com as informações fornecidas e o adiciona ao banco de dados.

    Args:
        name (str): O nome do produto.
        category (str): A categoria do produto.
        price (float): O preço do produto.
        bar_code (str): O código de barras do produto.
        expiry_date (str): A data de validade do produto no formato 'YYYY-MM-DD'.
        manufacturer (str): O fabricante do produto.

    Returns:
        str: Uma mensagem indicando o sucesso ou falha da adição do produto. Exemplo de retorno:
        "Produto 'Produto Exemplo' (ID: 1, Código de barras: 1234567890123) adicionado com sucesso."
    """
    ctx: AppContext = mcp.get_context().request_context.lifespan_context  # type: ignore

    existing_product = ctx.session.exec(
        select(Product).where(Product.bar_code == bar_code)
    ).first()
    if existing_product:
        return f"Produto com código de barras '{bar_code}' já existe."

    try:
        parsed_expiry_date = datetime.strptime(expiry_date, "%Y-%m-%d")
    except ValueError:
        return "Data de validade inválida. Use o formato 'YYYY-MM-DD'."

    new_product = Product(
        name=name,
        category=category,
        price=price,
        bar_code=bar_code,
        expiry_date=parsed_expiry_date,
        manufacturer=manufacturer,
    )

    ctx.session.add(new_product)
    ctx.session.commit()
    ctx.session.refresh(new_product)

    return f"Produto '{new_product.name}' (ID: {new_product.id}, Código de barras: {new_product.bar_code}) adicionado com sucesso."


@mcp.tool(
    description="Consulta produtos por fabricante e retorna uma lista formatada de produtos"
)
def get_products_by_manufacturer(manufacturer: str) -> str:
    """Consulta produtos por fabricante e retorna uma lista formatada de produtos.

    Esta função recupera todos os produtos de um fabricante específico do banco de dados.

    Args:
        manufacturer (str): O fabricante dos produtos a serem consultados.

    Returns:
        str: Uma string formatada contendo os produtos encontrados do fabricante especificado.
        Se nenhum produto for encontrado, uma mensagem apropriada é retornada. Exemplo de retorno:
        "Produtos do fabricante 'Fabricante Exemplo':
         - Produto 1 (Categoria: Categoria A, Preço: R$10.99, Código de barras: 1234567890123)
         - Produto 2 (Categoria: Categoria B, Preço: R$15.49, Código de barras: 9876543210987)"
    """
    ctx: AppContext = mcp.get_context().request_context.lifespan_context  # type: ignore
    products = ctx.session.exec(
        select(Product).where(
            func.lower(Product.manufacturer).contains(manufacturer.lower())
        )
    ).all()
    if not products:
        return f"Nenhum produto encontrado do fabricante '{manufacturer}'."
    response_lines = [f"Produtos do fabricante '{manufacturer}':"]
    for product in products:
        response_lines.append(
            f" - {product.name} (Categoria: {product.category}, Preço: R${product.price:.2f}, Código de barras: {product.bar_code})"
        )
    return "\n".join(response_lines)


@mcp.tool(
    description="Consulta todas as categorias de produtos disponíveis e retorna uma lista formatada"
)
def get_product_categories() -> str:
    """Consulta todas as categorias de produtos disponíveis e retorna uma lista formatada.

    Esta função recupera todas as categorias de produtos do banco de dados e retorna uma lista formatada.

    Returns:
        str: Uma string formatada contendo as categorias de produtos disponíveis. Exemplo de retorno:
        "Categorias de produtos disponíveis:
         - Categoria A
         - Categoria B
         - Categoria C"
    """
    ctx: AppContext = mcp.get_context().request_context.lifespan_context  # type: ignore
    categories = ctx.session.exec(select(Product.category).distinct()).all()

    if not categories:
        return "Nenhuma categoria de produto encontrada."

    response_lines = ["Categorias de produtos disponíveis:"]
    for category in categories:
        response_lines.append(f" - {category}")

    return "\n".join(response_lines)


@mcp.tool(
    description="Consulta todos os fabricantes de produtos disponíveis e retorna uma lista formatada"
)
def get_product_manufacturers() -> str:
    """Consulta todos os fabricantes de produtos disponíveis e retorna uma lista formatada.

    Esta função recupera todos os fabricantes de produtos do banco de dados e retorna uma lista formatada.

    Returns:
        str: Uma string formatada contendo os fabricantes de produtos disponíveis. Exemplo de retorno:
        "Fabricantes de produtos disponíveis:
         - Fabricante A
         - Fabricante B
         - Fabricante C"
    """
    ctx: AppContext = mcp.get_context().request_context.lifespan_context  # type: ignore
    manufacturers = ctx.session.exec(select(Product.manufacturer).distinct()).all()

    if not manufacturers:
        return "Nenhum fabricante de produto encontrado."

    response_lines = ["Fabricantes de produtos disponíveis:"]
    for manufacturer in manufacturers:
        response_lines.append(f" - {manufacturer}")

    return "\n".join(response_lines)


if __name__ == "__main__":
    mcp.run(transport="stdio")
