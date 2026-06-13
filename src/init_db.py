"""Executa o DDL (sql/ddl.sql) para criar schemas e tabelas."""

import os
from sqlalchemy import text

from src.config import get_engine, logger


def _read_ddl_file() -> str:
    """Lê o arquivo SQL de DDL relativo à raiz do projeto."""
    # Caminho relativo à raiz do projeto (onde main.py está)
    ddl_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "sql",
        "ddl.sql",
    )
    logger.info(f"Lendo DDL de: {ddl_path}")

    with open(ddl_path, "r", encoding="utf-8") as f:
        return f.read()


def _strip_sql_comments(sql: str) -> str:
    """Remove linhas que são apenas comentários de um bloco SQL."""
    lines = sql.split("\n")
    cleaned = [line for line in lines if not line.strip().startswith("--")]
    return "\n".join(cleaned).strip()


def setup() -> None:
    """Executa o setup completo do banco (Schemas, Tabelas e Índices)."""
    engine = get_engine()
    ddl_content = _read_ddl_file()

    # Divide o DDL em comandos individuais (separados por ;)
    # e remove linhas de comentário de dentro de cada bloco
    statements = [
        _strip_sql_comments(stmt)
        for stmt in ddl_content.split(";")
    ]
    statements = [s for s in statements if s]  # Remove blocos vazios

    logger.info(f"Executando {len(statements)} comandos DDL...")

    with engine.connect() as conn:
        for i, stmt in enumerate(statements, 1):
            try:
                conn.execute(text(stmt))
                conn.commit()  # Commit individual para evitar cascata de erro
                logger.info(f"  [{i}/{len(statements)}] ✅ OK")
            except Exception as e:
                conn.rollback()  # Rollback do statement com erro, continua
                logger.warning(f"  [{i}/{len(statements)}] ⚠️  {e}")

    logger.info("✅ Setup do banco concluído com sucesso.")


if __name__ == "__main__":
    setup()
