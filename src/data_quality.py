import great_expectations as gx
import pandas as pd
from sqlalchemy import text
from src.config import get_engine, logger

def run_table_dq(table_name: str, engine, raw_count: int, silver_count: int) -> bool:
    """Roda bateria de testes de uma tabela usando Ephemeral Data Context."""
    logger.info(f"   🔎 Testando tabela: silver.{table_name} (Raw: {raw_count} | Silver: {silver_count})")
    
    # Busca as métricas pré-agregadas via SQL para otimizar memória e I/O.
    # O PostgreSQL fará o trabalho pesado e retornará apenas 1 linha.
    try:
        query = f"""
        SELECT 
            COUNT(*) as total_rows,
            SUM(CASE WHEN co_entidade IS NULL THEN 1 ELSE 0 END) as null_co_entidade,
            SUM(CASE WHEN nu_ano_censo < 2020 OR nu_ano_censo > 2030 THEN 1 ELSE 0 END) as invalid_ano
        FROM silver.{table_name}
        """
        df = pd.read_sql(query, engine)
    except Exception as e:
        logger.error(f"      ❌ Falha ao consultar as métricas da tabela: {e}")
        return False
        
    # Inicializa o Great Expectations com o DataFrame de métricas (1 linha)
    dataset = gx.from_pandas(df)
    
    all_passed = True
    
    # 1. Expectativa: Volume de Dados (Completeness)
    res_count = dataset.expect_column_values_to_be_between("total_rows", min_value=raw_count, max_value=raw_count)
    if _log_result("1. Volume: A tabela silver possui a mesma quantidade de registros da raw?", res_count):
        pass
    else:
        all_passed = False

    # 2. Expectativa: Chave Não Nula (Completeness)
    # Esperamos que a contagem de nulos seja exatamente 0.
    res_null = dataset.expect_column_values_to_be_between("null_co_entidade", min_value=0, max_value=0)
    if not _log_result("2. Integridade: A coluna 'co_entidade' não contém nulos?", res_null):
        all_passed = False

    # 3. Expectativa: Domínio de Ano (Validity)
    # Esperamos que a contagem de anos inválidos seja exatamente 0.
    res_ano = dataset.expect_column_values_to_be_between("invalid_ano", min_value=0, max_value=0)
    if not _log_result("3. Domínio: O 'nu_ano_censo' é um ano válido (2020 a 2030)?", res_ano):
        all_passed = False
        
    return all_passed


def _log_result(question: str, result_obj) -> bool:
    """Imprime de forma amigável o resultado de uma expectativa."""
    success = result_obj.success
    if success:
        logger.info(f"      ✅ PASS | {question}")
    else:
        logger.error(f"      ❌ FAIL | {question}")
        # Extrai detalhes do erro de forma segura
        res_dict = result_obj.result
        if 'observed_value' in res_dict:
            logger.error(f"         [!] Valor observado: {res_dict['observed_value']}")
        if 'unexpected_count' in res_dict:
            logger.error(f"         [!] Registros anômalos: {res_dict['unexpected_count']}")
    return success


def run(stats: dict[str, dict[str, int]]) -> None:
    """
    Orquestra a execução das expectativas de qualidade de dados.
    """
    logger.info("=" * 60)
    logger.info("🛡️  ETAPA: DATA QUALITY VALIDATION (Great Expectations)")
    logger.info("=" * 60)

    engine = get_engine()
    
    all_tables_passed = True
    
    for table_name, counts in stats.items():
        raw_count = counts.get("raw", 0)
        silver_count = counts.get("silver", 0)
        
        passed = run_table_dq(table_name, engine, raw_count, silver_count)
        if not passed:
            all_tables_passed = False
        logger.info("")

    if all_tables_passed:
        logger.info("✨ Todas as validações de Data Quality passaram com sucesso!")
    else:
        logger.warning("⚠️  Atenção: Alguns testes de qualidade falharam. Revise os logs acima.")

if __name__ == "__main__":
    # Teste unitário mockado
    mock_stats = {"escolas": {"raw": 100, "silver": 100}}
    run(mock_stats)
