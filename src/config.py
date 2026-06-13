# =============================================================================
# src/config.py — Configurações centralizadas do pipeline
# =============================================================================
"""
Carrega variáveis de ambiente e centraliza constantes de configuração.
Todas as credenciais são lidas via os.getenv (nunca hardcoded).
"""

import os
import logging
from dotenv import load_dotenv
from sqlalchemy import create_engine

# Carregar .env (se existir)
load_dotenv()

# Logging
LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
logger = logging.getLogger("censo_escolar")

# Banco de Dados
SUPABASE_DB_URL: str = os.getenv("SUPABASE_DB_URL", "")
if not SUPABASE_DB_URL:
    raise EnvironmentError(
        "A variável SUPABASE_DB_URL não foi definida. "
        "Copie .env.example para .env e preencha com suas credenciais."
    )

# Configurações do Pipeline
CHUNK_SIZE: int = int(os.getenv("CHUNK_SIZE", "50000"))
TARGET_UF: str = "SP"  # Filtra apenas São Paulo para poupar armazenamento
CSV_ENCODING: str = "latin-1"
CSV_SEPARATOR: str = ";"

# INEP — Página de Microdados do Censo Escolar
INEP_BASE_URL: str = (
    "https://www.gov.br/inep/pt-br/acesso-a-informacao"
    "/dados-abertos/microdados/censo-escolar"
)

# Padrão de fallback para download direto (caso o scraping falhe)
INEP_DOWNLOAD_PATTERN: str = (
    "https://download.inep.gov.br/dados_abertos/"
    "microdados_censo_escolar_{year}.zip"
)

# Schemas do banco de dados (Medallion Architecture)
SCHEMA_RAW: str = "raw"
SCHEMA_SILVER: str = "silver"
SCHEMA_GOLD: str = "gold"

# Colunas relevantes por tabela
COLUNAS_ESCOLAS: list[str] = [
    "NU_ANO_CENSO", "CO_ENTIDADE", "NO_ENTIDADE",
    "CO_UF", "SG_UF", "CO_MUNICIPIO", "NO_MUNICIPIO",
    "TP_DEPENDENCIA", "TP_LOCALIZACAO", "TP_SITUACAO_FUNCIONAMENTO",
    "IN_AGUA_POTAVEL", "IN_AGUA_REDE_PUBLICA",
    "IN_ENERGIA_INEXISTENTE", "IN_ENERGIA_REDE_PUBLICA",
    "IN_INTERNET", "IN_BANDA_LARGA",
    "IN_ACESSIBILIDADE_CORRIMAO", "IN_ACESSIBILIDADE_ELEVADOR",
    "IN_ACESSIBILIDADE_PISOS_TATEIS", "IN_ACESSIBILIDADE_RAMPAS",
    "IN_ACESSIBILIDADE_VAO_LIVRE", "IN_ACESSIBILIDADE_SINALIZACAO_TATIL",
]

COLUNAS_TURMAS: list[str] = [
    "NU_ANO_CENSO", "CO_ENTIDADE", 
    "QT_TUR_BAS", "QT_TUR_INF", "QT_TUR_FUND", "QT_TUR_MED", "QT_TUR_PROF", "QT_TUR_EJA"
]

COLUNAS_MATRICULAS: list[str] = [
    "NU_ANO_CENSO", "CO_ENTIDADE", 
    "QT_MAT_BAS", "QT_MAT_INF", "QT_MAT_FUND", "QT_MAT_MED", "QT_MAT_PROF", "QT_MAT_EJA"
]

# Engine SQLAlchemy

def get_engine():
    """Cria e retorna a engine SQLAlchemy com pool configurado."""
    return create_engine(
        SUPABASE_DB_URL,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,  # Testa conexão antes de usar
        connect_args={"options": "-c statement_timeout=300000"},  # 5min timeout
    )
