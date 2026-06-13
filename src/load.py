# =============================================================================
# src/load.py — Carga de dados: CSV → Raw → Silver (UPSERT)
# =============================================================================
"""Carga de dados: CSV → Raw → Silver (UPSERT) em chunks."""

import gc

import pandas as pd
from sqlalchemy import text

from src.config import (
    CHUNK_SIZE,
    CSV_ENCODING,
    CSV_SEPARATOR,
    COLUNAS_ESCOLAS,
    COLUNAS_MATRICULAS,
    COLUNAS_TURMAS,
    SCHEMA_SILVER,
    SCHEMA_RAW,
    TARGET_UF,
    get_engine,
    logger,
)

# Mapeamento das tabelas e suas configurações
TABLE_CONFIG: dict[str, dict] = {
    "escolas": {
        "raw_table": f"{SCHEMA_RAW}.escolas",
        "silver_table": f"{SCHEMA_SILVER}.escolas",
        "columns": COLUNAS_ESCOLAS,
        "conflict_key": "(co_entidade, nu_ano_censo)",
        "conflict_columns": ["co_entidade", "nu_ano_censo"],
    },
    "turmas": {
        "raw_table": f"{SCHEMA_RAW}.turmas",
        "silver_table": f"{SCHEMA_SILVER}.turmas",
        "columns": COLUNAS_TURMAS,
        "conflict_key": "(co_entidade, nu_ano_censo)",
        "conflict_columns": ["co_entidade", "nu_ano_censo"],
    },
    "matriculas": {
        "raw_table": f"{SCHEMA_RAW}.matriculas",
        "silver_table": f"{SCHEMA_SILVER}.matriculas",
        "columns": COLUNAS_MATRICULAS,
        "conflict_key": "(co_entidade, nu_ano_censo)",
        "conflict_columns": ["co_entidade", "nu_ano_censo"],
    },
}


# Funções de Carga na Raw

def _truncate_raw(engine) -> None:
    """Limpa todas as tabelas de raw antes da ingestão."""
    logger.info("🗑️  Truncando tabelas de raw...")
    with engine.connect() as conn:
        for table_name, config in TABLE_CONFIG.items():
            conn.execute(text(f"TRUNCATE TABLE {config['raw_table']} CASCADE"))
            logger.debug(f"   TRUNCATE {config['raw_table']}")
        conn.commit()
    logger.info("   Raw limpa.")


def _filter_columns(df: pd.DataFrame, desired_columns: list[str]) -> pd.DataFrame:
    """
    Filtra apenas as colunas desejadas que existem no DataFrame.
    Colunas que não existem no CSV são ignoradas (o INEP muda colunas entre anos).
    """
    # Normaliza nomes das colunas para UPPERCASE (padrão INEP)
    df.columns = df.columns.str.strip().str.upper()
    desired_upper = [c.upper() for c in desired_columns]

    available = [c for c in desired_upper if c in df.columns]
    missing = set(desired_upper) - set(df.columns)

    if missing:
        logger.debug(f"   Colunas não encontradas no CSV (ignoradas): {missing}")

    return df[available]


def _load_csv_to_raw(
    csv_path: str,
    table_name: str,
    config: dict,
    engine,
) -> int:
    """
    Carrega um CSV na tabela de raw em chunks.

    Args:
        csv_path: Caminho do arquivo CSV.
        table_name: Nome lógico da tabela (escolas, turmas, matriculas).
        config: Configuração da tabela (colunas, schema, etc).
        engine: SQLAlchemy engine.

    Returns:
        Total de registros inseridos na raw.
    """
    logger.info(f"📂 Carregando {table_name} de: {csv_path}")

    total_rows = 0
    chunk_num = 0

    # Lê CSV em chunks para não explodir memória
    reader = pd.read_csv(
        csv_path,
        sep=CSV_SEPARATOR,
        encoding=CSV_ENCODING,
        chunksize=CHUNK_SIZE,
        dtype=str,       # Tudo como string na raw
        on_bad_lines="skip",  # Ignora linhas mal-formatadas
        low_memory=False,
    )

    schema_name, raw_table_name = config["raw_table"].split(".")

    for chunk in reader:
        chunk_num += 1

        # Trata as mudanças de nomes de colunas no INEP 2025
        chunk.columns = chunk.columns.str.strip().str.upper()
        
        # Log das colunas na primeira iteração
        if chunk_num == 1:
            logger.info(f"   Colunas detectadas no CSV: {list(chunk.columns)}")

        rename_map = {}
        if "CO_TURMA" in chunk.columns:
            rename_map["CO_TURMA"] = "ID_TURMA"
        if "CO_MATRICULA" in chunk.columns:
            rename_map["CO_MATRICULA"] = "ID_MATRICULA"
        if rename_map:
            chunk = chunk.rename(columns=rename_map)

        # Filtra apenas colunas relevantes
        chunk = _filter_columns(chunk, config["columns"])

        # Normaliza nomes para lowercase (padrão PostgreSQL)
        chunk.columns = chunk.columns.str.lower()

        # Insere na raw
        chunk.to_sql(
            name=raw_table_name,
            schema=schema_name,
            con=engine,
            if_exists="append",
            index=False,
            method="multi",
            chunksize=5000,  # Sub-chunks para o INSERT
        )

        rows_in_chunk = len(chunk)
        total_rows += rows_in_chunk

        if chunk_num % 10 == 0:
            logger.info(
                f"   Chunk {chunk_num}: +{rows_in_chunk} linhas "
                f"(total: {total_rows:,})"
            )

        # Libera memória explicitamente
        del chunk
        gc.collect()

    logger.info(
        f"   ✅ {table_name}: {total_rows:,} registros carregados na raw "
        f"({chunk_num} chunks processados)"
    )
    return total_rows


# Mapeamento de tipos para CAST no UPSERT
CAST_TYPES: dict[str, str] = {
    "nu_ano_censo": "INTEGER",
    "co_entidade": "BIGINT",
    "co_uf": "INTEGER",
    "co_municipio": "INTEGER",
    "tp_dependencia": "SMALLINT",
    "tp_localizacao": "SMALLINT",
    "tp_situacao_funcionamento": "SMALLINT",
    "in_agua_potavel": "SMALLINT",
    "in_agua_rede_publica": "SMALLINT",
    "in_energia_inexistente": "SMALLINT",
    "in_energia_rede_publica": "SMALLINT",
    "in_internet": "SMALLINT",
    "in_banda_larga": "SMALLINT",
    "in_acessibilidade_corrimao": "SMALLINT",
    "in_acessibilidade_elevador": "SMALLINT",
    "in_acessibilidade_pisos_tateis": "SMALLINT",
    "in_acessibilidade_rampas": "SMALLINT",
    "in_acessibilidade_vao_livre": "SMALLINT",
    "in_acessibilidade_sinalizacao_tatil": "SMALLINT",
    "qt_tur_bas": "INTEGER",
    "qt_tur_inf": "INTEGER",
    "qt_tur_fund": "INTEGER",
    "qt_tur_med": "INTEGER",
    "qt_tur_prof": "INTEGER",
    "qt_tur_eja": "INTEGER",
    "qt_mat_bas": "INTEGER",
    "qt_mat_inf": "INTEGER",
    "qt_mat_fund": "INTEGER",
    "qt_mat_med": "INTEGER",
    "qt_mat_prof": "INTEGER",
    "qt_mat_eja": "INTEGER",
}


# UPSERT: Raw → Silver

def _build_upsert_sql(table_name: str, config: dict) -> str:
    """
    Constrói a query de UPSERT (INSERT ... ON CONFLICT ... DO UPDATE).

    Usa chave composta para garantir não-duplicidade.
    Inclui CAST explícito para converter TEXT da raw para tipos da silver,
    usando NULLIF para tratar strings vazias.
    """
    raw = config["raw_table"]
    silver = config["silver_table"]
    conflict = config["conflict_key"]

    # Colunas de destino
    col_list = [c.lower() for c in config["columns"]]
    col_str = ", ".join(col_list)

    # SELECT com CAST para converter TEXT → tipo correto
    # Usa NULLIF(col, '') para converter strings vazias do CSV para NULL
    select_cols = []
    for c in col_list:
        if c in CAST_TYPES:
            select_cols.append(f"NULLIF({c}, '')::{CAST_TYPES[c]}")
        else:
            select_cols.append(f"NULLIF({c}, '')")
    select_str = ", ".join(select_cols)

    # SET clause para o UPDATE (exclui as colunas da chave)
    conflict_cols_lower = [c.lower() for c in config["conflict_columns"]]
    update_cols = [c for c in col_list if c not in conflict_cols_lower]
    set_clause = ", ".join([f"{c} = EXCLUDED.{c}" for c in update_cols])

    sql = f"""
    INSERT INTO {silver} ({col_str})
    SELECT {select_str}
    FROM {raw}
    ON CONFLICT {conflict}
    DO UPDATE SET
        {set_clause},
        _loaded_at = NOW()
    """

    return sql


def _upsert_raw_to_silver(engine) -> dict[str, int]:
    """
    Executa UPSERT de todas as tabelas: raw → silver.

    Returns:
        Dict com contagem de registros afetados por tabela.
    """
    logger.info("🔄 Executando UPSERT: raw → silver...")
    counts: dict[str, int] = {}

    with engine.connect() as conn:
        for table_name, config in TABLE_CONFIG.items():
            sql = _build_upsert_sql(table_name, config)
            logger.debug(f"   UPSERT {table_name}:\n{sql[:200]}...")

            result = conn.execute(text(sql))
            row_count = result.rowcount
            counts[table_name] = row_count
            logger.info(f"   ✅ {table_name}: {row_count:,} registros no silver")

        conn.commit()

    logger.info("✅ UPSERT concluído.")
    return counts


# Função principal de carga

def run(csv_paths: dict[str, str]) -> dict[str, dict[str, int]]:
    """
    Executa o pipeline completo de carga:
    1. Trunca raw
    2. Carrega CSVs na raw (em chunks, filtrado por SP)
    3. UPSERT raw → silver

    Args:
        csv_paths: Dict {'escolas': path, 'turmas': path, 'matriculas': path}

    Returns:
        Dict com estatísticas de carga por tabela.
    """
    logger.info("=" * 60)
    logger.info("ETAPA: CARGA DE DADOS (CSV → Raw → Silver)")
    logger.info("=" * 60)

    engine = get_engine()
    stats: dict[str, dict[str, int]] = {}

    # 1. Trunca raw
    _truncate_raw(engine)

    # 2. Carrega cada CSV na raw
    for table_name, csv_path in csv_paths.items():
        if table_name not in TABLE_CONFIG:
            logger.warning(f"⚠️  Tabela desconhecida: {table_name}. Ignorando.")
            continue

        config = TABLE_CONFIG[table_name]
        raw_count = _load_csv_to_raw(csv_path, table_name, config, engine)
        stats[table_name] = {"raw": raw_count}

    # 3. UPSERT raw → silver
    upsert_counts = _upsert_raw_to_silver(engine)
    for table_name, count in upsert_counts.items():
        if table_name in stats:
            stats[table_name]["silver"] = count

    logger.info("✅ Carga concluída.")
    logger.info(f"   Estatísticas: {stats}")
    return stats


if __name__ == "__main__":
    # Teste standalone (requer CSVs já extraídos)
    import sys

    if len(sys.argv) < 4:
        print(
            "Uso: python -m src.load <escolas.csv> <turmas.csv> <matriculas.csv>"
        )
        sys.exit(1)

    paths = {
        "escolas": sys.argv[1],
        "turmas": sys.argv[2],
        "matriculas": sys.argv[3],
    }
    run(paths)
