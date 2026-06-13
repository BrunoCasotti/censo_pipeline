-- 1. Criação dos Schemas
CREATE SCHEMA IF NOT EXISTS staging;
CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS analytics;

-- 2. Tabelas STAGING (dados temporários)

DROP TABLE IF EXISTS staging.escolas CASCADE;
CREATE TABLE staging.escolas (
    nu_ano_censo        TEXT,
    co_entidade         TEXT,
    no_entidade         TEXT,
    co_uf               TEXT,
    sg_uf               TEXT,
    co_municipio        TEXT,
    no_municipio        TEXT,
    tp_dependencia      TEXT,
    tp_localizacao      TEXT,
    tp_situacao_funcionamento TEXT,
    in_agua_potavel     TEXT,
    in_agua_rede_publica TEXT,
    in_energia_inexistente TEXT,
    in_energia_rede_publica TEXT,
    in_internet         TEXT,
    in_banda_larga      TEXT,
    in_acessibilidade_corrimao TEXT,
    in_acessibilidade_elevador TEXT,
    in_acessibilidade_pisos_tateis TEXT,
    in_acessibilidade_rampas TEXT,
    in_acessibilidade_vao_livre TEXT,
    in_acessibilidade_sinalizacao_tatil TEXT,
    _loaded_at          TIMESTAMP DEFAULT NOW()
);

DROP TABLE IF EXISTS staging.turmas CASCADE;
CREATE TABLE staging.turmas (
    nu_ano_censo        TEXT,
    co_entidade         TEXT,
    qt_tur_bas          TEXT,
    qt_tur_inf          TEXT,
    qt_tur_fund         TEXT,
    qt_tur_med          TEXT,
    qt_tur_prof         TEXT,
    qt_tur_eja          TEXT,
    _loaded_at          TIMESTAMP DEFAULT NOW()
);

DROP TABLE IF EXISTS staging.matriculas CASCADE;
CREATE TABLE staging.matriculas (
    nu_ano_censo        TEXT,
    co_entidade         TEXT,
    qt_mat_bas          TEXT,
    qt_mat_inf          TEXT,
    qt_mat_fund         TEXT,
    qt_mat_med          TEXT,
    qt_mat_prof         TEXT,
    qt_mat_eja          TEXT,
    _loaded_at          TIMESTAMP DEFAULT NOW()
);

-- 3. Tabelas RAW (dados históricos tipados)

DROP TABLE IF EXISTS raw.escolas CASCADE;
CREATE TABLE raw.escolas (
    nu_ano_censo        INTEGER     NOT NULL,
    co_entidade         BIGINT      NOT NULL,
    no_entidade         VARCHAR(200),
    co_uf               INTEGER,
    sg_uf               VARCHAR(2),
    co_municipio        INTEGER,
    no_municipio        VARCHAR(150),
    tp_dependencia      SMALLINT,
    tp_localizacao      SMALLINT,
    tp_situacao_funcionamento SMALLINT,
    in_agua_potavel     SMALLINT,
    in_agua_rede_publica SMALLINT,
    in_energia_inexistente SMALLINT,
    in_energia_rede_publica SMALLINT,
    in_internet         SMALLINT,
    in_banda_larga      SMALLINT,
    in_acessibilidade_corrimao SMALLINT,
    in_acessibilidade_elevador SMALLINT,
    in_acessibilidade_pisos_tateis SMALLINT,
    in_acessibilidade_rampas SMALLINT,
    in_acessibilidade_vao_livre SMALLINT,
    in_acessibilidade_sinalizacao_tatil SMALLINT,
    _loaded_at          TIMESTAMP DEFAULT NOW(),
    CONSTRAINT pk_raw_escolas PRIMARY KEY (co_entidade, nu_ano_censo)
);

DROP TABLE IF EXISTS raw.turmas CASCADE;
CREATE TABLE IF NOT EXISTS raw.turmas (
    nu_ano_censo INTEGER,
    co_entidade BIGINT,
    qt_tur_bas INTEGER,
    qt_tur_inf INTEGER,
    qt_tur_fund INTEGER,
    qt_tur_med INTEGER,
    qt_tur_prof INTEGER,
    qt_tur_eja INTEGER,
    _loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_raw_turmas PRIMARY KEY (co_entidade, nu_ano_censo)
);


DROP TABLE IF EXISTS raw.matriculas CASCADE;
CREATE TABLE IF NOT EXISTS raw.matriculas (
    nu_ano_censo INTEGER,
    co_entidade BIGINT,
    qt_mat_bas INTEGER,
    qt_mat_inf INTEGER,
    qt_mat_fund INTEGER,
    qt_mat_med INTEGER,
    qt_mat_prof INTEGER,
    qt_mat_eja INTEGER,
    _loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_raw_matriculas PRIMARY KEY (co_entidade, nu_ano_censo)
);

-- 4. Índices para performance nas queries analíticas
CREATE INDEX IF NOT EXISTS idx_raw_escolas_uf
    ON raw.escolas (sg_uf);

CREATE INDEX IF NOT EXISTS idx_raw_escolas_dependencia
    ON raw.escolas (tp_dependencia);

CREATE INDEX IF NOT EXISTS idx_raw_turmas_entidade_ano
    ON raw.turmas (co_entidade, nu_ano_censo);

CREATE INDEX IF NOT EXISTS idx_raw_matriculas_entidade_ano
    ON raw.matriculas (co_entidade, nu_ano_censo);


