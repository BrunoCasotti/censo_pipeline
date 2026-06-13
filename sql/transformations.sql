-- View Mestra: Censo Escolar Agregado (Wide Table)
CREATE OR REPLACE VIEW gold.vw_censo_escolar_agregado AS
SELECT
    e.nu_ano_censo,
    e.sg_uf,
    CASE e.tp_dependencia
        WHEN 1 THEN 'Federal'
        WHEN 2 THEN 'Estadual'
        WHEN 3 THEN 'Municipal'
        WHEN 4 THEN 'Privada'
        ELSE 'Não Informado'
    END AS ds_dependencia,
    CASE e.tp_localizacao
        WHEN 1 THEN 'Urbana'
        WHEN 2 THEN 'Rural'
        ELSE 'Não Informado'
    END AS ds_localizacao,

    COUNT(DISTINCT e.co_entidade) AS total_escolas,
    SUM(t.qt_tur_bas) AS total_turmas,
    SUM(m.qt_mat_bas) AS total_matriculas,

    ROUND(100.0 * SUM(CASE WHEN e.in_internet = 1 THEN 1 ELSE 0 END) / NULLIF(COUNT(DISTINCT e.co_entidade), 0), 2) AS pct_com_internet,
    ROUND(100.0 * SUM(CASE WHEN e.in_banda_larga = 1 THEN 1 ELSE 0 END) / NULLIF(COUNT(DISTINCT e.co_entidade), 0), 2) AS pct_com_banda_larga,
    ROUND(100.0 * SUM(CASE WHEN e.in_agua_potavel = 1 THEN 1 ELSE 0 END) / NULLIF(COUNT(DISTINCT e.co_entidade), 0), 2) AS pct_com_agua_potavel,
    ROUND(100.0 * SUM(CASE WHEN e.in_energia_inexistente = 0 THEN 1 ELSE 0 END) / NULLIF(COUNT(DISTINCT e.co_entidade), 0), 2) AS pct_com_energia,
    ROUND(100.0 * SUM(
        CASE WHEN (
            COALESCE(e.in_acessibilidade_corrimao, 0) = 1
            OR COALESCE(e.in_acessibilidade_elevador, 0) = 1
            OR COALESCE(e.in_acessibilidade_pisos_tateis, 0) = 1
            OR COALESCE(e.in_acessibilidade_rampas, 0) = 1
            OR COALESCE(e.in_acessibilidade_vao_livre, 0) = 1
            OR COALESCE(e.in_acessibilidade_sinalizacao_tatil, 0) = 1
        ) THEN 1 ELSE 0 END
    ) / NULLIF(COUNT(DISTINCT e.co_entidade), 0), 2) AS pct_com_acessibilidade,

    ROUND(100.0 * SUM(
        CASE WHEN e.in_internet = 1 AND e.in_banda_larga = 1 AND e.in_energia_inexistente = 0 
        THEN 1 ELSE 0 END
    ) / NULLIF(COUNT(DISTINCT e.co_entidade), 0), 2) AS pct_escolas_conectadas,

    ROUND(SUM(t.qt_tur_bas)::NUMERIC / NULLIF(COUNT(DISTINCT e.co_entidade), 0), 2) AS media_turmas_escola,
    ROUND(SUM(m.qt_mat_bas)::NUMERIC / NULLIF(COUNT(DISTINCT e.co_entidade), 0), 2) AS media_alunos_escola,
    ROUND(SUM(m.qt_mat_bas)::NUMERIC / NULLIF(SUM(t.qt_tur_bas), 0), 2) AS razao_alunos_turma

FROM silver.escolas e
LEFT JOIN silver.turmas t 
    ON e.co_entidade = t.co_entidade AND e.nu_ano_censo = t.nu_ano_censo
LEFT JOIN silver.matriculas m 
    ON e.co_entidade = m.co_entidade AND e.nu_ano_censo = m.nu_ano_censo
-- Filtro para trazer apenas escolas em funcionamento (status = Em Atividade)
WHERE e.tp_situacao_funcionamento = 1
GROUP BY 
    e.nu_ano_censo, 
    e.sg_uf, 
    e.tp_dependencia, 
    e.tp_localizacao
ORDER BY 
    e.nu_ano_censo,
    media_alunos_escola DESC NULLS LAST,
    pct_escolas_conectadas DESC NULLS LAST,
    pct_com_acessibilidade DESC NULLS LAST;
