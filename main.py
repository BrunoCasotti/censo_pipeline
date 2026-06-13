# =============================================================================
# main.py — Orquestrador do Pipeline de Microdados do Censo Escolar
# =============================================================================
"""
Orquestrador do Pipeline: Setup DB -> Extract -> Load -> Transform -> Cleanup.
Uso: python main.py
"""

import os
import sys
import time
import shutil

from sqlalchemy import text


def main() -> None:
    """Executa o pipeline completo."""

    # Importações dentro da função para garantir que o .env já foi carregado
    from src.config import get_engine, logger
    from src import init_db, extract, load, data_quality
    from src.dashboard import generate_dashboard

    start_time = time.time()

    logger.info("=" * 60)
    logger.info("🚀 PIPELINE DE MICRODADOS DO CENSO ESCOLAR (INEP)")
    logger.info("=" * 60)
    logger.info(f"   Python: {sys.version}")
    logger.info(f"   CWD: {os.getcwd()}")
    logger.info("")

    temp_dir = None

    try:
        # ETAPA 1: Setup do Banco de Dados
        logger.info("▶ ETAPA 1/6: Setup do banco de dados...")
        init_db.setup()
        logger.info("")

        # ETAPA 2: Extração dos Microdados
        logger.info("▶ ETAPA 2/6: Extração dos microdados do INEP...")
        csv_paths, temp_dir, year = extract.run()
        logger.info(f"   Ano do Censo: {year}")
        logger.info(f"   Arquivos extraídos: {list(csv_paths.keys())}")
        logger.info("")

        # ETAPA 3: Carga de Dados
        logger.info("▶ ETAPA 3/6: Carga de dados...")
        stats = load.run(csv_paths)
        logger.info("")

        # ETAPA 4: Data Quality Validation
        logger.info("▶ ETAPA 4/6: Validação de Qualidade de Dados (Great Expectations)...")
        data_quality.run(stats)
        logger.info("")

        # ETAPA 5: Transformações SQL
        logger.info("▶ ETAPA 5/6: Criando views analíticas...")
        _run_transformations(get_engine(), logger)
        logger.info("")

        # ETAPA 6: Geração do Dashboard HTML
        logger.info("▶ ETAPA 6/6: Gerando Dashboard HTML...")
        generate_dashboard()
        logger.info("")

    except KeyboardInterrupt:
        logger.warning("⚠️  Pipeline interrompido pelo usuário (Ctrl+C).")
        sys.exit(1)

    except Exception as e:
        logger.error(f"❌ Erro no pipeline: {e}", exc_info=True)
        sys.exit(1)

    finally:
        # CLEANUP: Remove diretório temporário
        if temp_dir and os.path.exists(temp_dir):
            try:
                shutil.rmtree(temp_dir)
                logger.info(f"🗑️  Diretório temporário removido: {temp_dir}")
            except OSError as e:
                logger.warning(f"⚠️  Não foi possível remover {temp_dir}: {e}")

    # RESUMO FINAL
    elapsed = time.time() - start_time
    minutes = int(elapsed // 60)
    seconds = int(elapsed % 60)

    logger.info("=" * 60)
    logger.info("✅ PIPELINE CONCLUÍDO COM SUCESSO!")
    logger.info(f"   Tempo total: {minutes}m {seconds}s")
    logger.info("=" * 60)
    
    # AMOSTRA DOS DADOS
    try:
        import pandas as pd
        logger.info("📊 AMOSTRA DOS DADOS ANALÍTICOS (TOP 3):")
        df_top3 = pd.read_sql(
            "SELECT * FROM gold.vw_censo_escolar_agregado LIMIT 3", 
            get_engine()
        )
        records = df_top3.to_dict(orient="records")
        for i, row in enumerate(records, 1):
            print(f"\n🏆 RANK {i} ---")
            for k, v in row.items():
                print(f"  {k:25}: {v}")
        print()
        logger.info("=" * 60)
    except Exception as e:
        logger.warning(f"Não foi possível exibir a amostra: {e}")


def _run_transformations(engine, logger) -> None:
    """Lê e executa o arquivo sql/transformations.sql."""

    sql_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "sql",
        "transformations.sql",
    )
    logger.info(f"   Lendo transformações de: {sql_path}")

    with open(sql_path, "r", encoding="utf-8") as f:
        sql_content = f.read()

    # Divide em statements individuais e executa cada uma
    statements = []
    for stmt in sql_content.split(";"):
        stmt = stmt.strip()
        if stmt:
            statements.append(stmt)

    logger.info(f"   Executando {len(statements)} transformações...")

    with engine.connect() as conn:
        for i, stmt in enumerate(statements, 1):
            try:
                conn.execute(text(stmt))
                # Extrai o nome da view para log legível
                view_name = ""
                if "CREATE OR REPLACE VIEW" in stmt.upper():
                    parts = stmt.split()
                    idx = [
                        j for j, p in enumerate(parts)
                        if p.upper() == "VIEW"
                    ]
                    if idx:
                        view_name = parts[idx[0] + 1]
                logger.info(f"   ✅ [{i}/{len(statements)}] {view_name}")
            except Exception as e:
                logger.error(f"   ❌ [{i}/{len(statements)}] Erro: {e}")
                raise
        conn.commit()

    logger.info("   ✅ Todas as views criadas com sucesso.")


if __name__ == "__main__":
    main()
