# Pipeline de Microdados do Censo Escolar — Arco Educação

Pipeline **one-shot** que extrai dinamicamente os Microdados do Censo Escolar (INEP), estrutura o banco PostgreSQL/Supabase, carrega dados filtrados para SP, realiza UPSERT anual e gera métricas analíticas via SQL. Compatível com **Python 3.10+**.

## User Review Required

> [!IMPORTANT]
> **Supabase Connection**: O pipeline assume que a variável `SUPABASE_DB_URL` no `.env` contém a connection string completa do PostgreSQL (formato: `postgresql://user:password@host:port/dbname`). Confirme se já possui acesso a um projeto Supabase.

> [!WARNING]
> **Tamanho dos dados**: Os microdados do Censo Escolar são volumosos (~2GB+ compactados). O download + extração + carga pode levar de 15min a 1h+ dependendo da banda de internet e velocidade do Supabase. Filtraremos apenas SP para reduzir o volume.

## Proposed Changes

### Estrutura de Pastas Final

```
arco_dataeng_platform_challenge/
├── .github/skills/          # (existente)
├── src/
│   ├── __init__.py
│   ├── config.py            # Configurações centralizadas (env vars)
│   ├── init_db.py           # Setup automático do banco (DDL)
│   ├── extract.py           # Extração dinâmica do INEP via scraping
│   └── load.py              # Carga em chunks + filtro SP + UPSERT
├── sql/
│   ├── ddl.sql              # CREATE SCHEMA + CREATE TABLE
│   └── transformations.sql  # Views analíticas (schema analytics)
├── main.py                  # Orquestrador principal
├── .env.example             # Template de variáveis de ambiente
├── requirements.txt         # Dependências do projeto (python_requires >= 3.10)
├── README.md                # Documentação completa
└── .gitignore               # (existente, será atualizado)
```

---

### Componente 1: Configuração do Projeto

#### [NEW] [requirements.txt](file:///c:/Users/bruno/OneDrive/Documentos/Github/repositorios/arco_dataeng_platform_challenge/requirements.txt)
- Cabeçalho com comentário: `# Requires Python >= 3.10`
- Dependências:
  - `requests` — HTTP requests para download
  - `beautifulsoup4` — Scraping da página INEP
  - `pandas` — Leitura e manipulação de dados em chunks
  - `sqlalchemy>=2.0` — ORM compatível com SQLAlchemy 2.0+
  - `psycopg2-binary` — Driver PostgreSQL
  - `python-dotenv` — Carregamento de `.env`

#### [NEW] [.env.example](file:///c:/Users/bruno/OneDrive/Documentos/Github/repositorios/arco_dataeng_platform_challenge/.env.example)
- Template com:
  - `SUPABASE_DB_URL=postgresql://...`
  - `CHUNK_SIZE=50000` — Configurável. Default seguro para ambientes com ≥4GB RAM. Pode ser aumentado para 100000+ em máquinas com mais memória.

#### [MODIFY] [.gitignore](file:///c:/Users/bruno/OneDrive/Documentos/Github/repositorios/arco_dataeng_platform_challenge/.gitignore)
- Adicionar `tmp/` para os downloads temporários

---

### Componente 2: Módulo de Configuração (`src/config.py`)

#### [NEW] [config.py](file:///c:/Users/bruno/OneDrive/Documentos/Github/repositorios/arco_dataeng_platform_challenge/src/config.py)
- Carrega variáveis do `.env` via `python-dotenv`
- Centraliza `SUPABASE_DB_URL`, `INEP_URL`, `CHUNK_SIZE`, `TARGET_UF`
- Cria engine SQLAlchemy com pool e configurações otimizadas
- Constantes de nomes de schemas (`staging`, `raw`, `analytics`)

---

### Componente 3: Setup Automático do Banco (`src/init_db.py`)

#### [NEW] [init_db.py](file:///c:/Users/bruno/OneDrive/Documentos/Github/repositorios/arco_dataeng_platform_challenge/src/init_db.py)
- Conecta no Supabase via SQLAlchemy engine
- Executa DDL a partir de `sql/ddl.sql`
- Cria schemas: `staging`, `raw`, `analytics`
- Cria tabelas:
  - `staging.escolas`, `staging.turmas`, `staging.matriculas`
  - `raw.escolas`, `raw.turmas`, `raw.matriculas`
- Tabelas raw com constraint UNIQUE em `(CO_ENTIDADE, NU_ANO_CENSO)` para turmas e escolas, `(ID_MATRICULA, NU_ANO_CENSO)` para matrículas

#### [NEW] [ddl.sql](file:///c:/Users/bruno/OneDrive/Documentos/Github/repositorios/arco_dataeng_platform_challenge/sql/ddl.sql)
- `CREATE SCHEMA IF NOT EXISTS staging/raw/analytics`
- Tabelas staging espelham colunas-chave dos CSVs + metadados (`_loaded_at`)
- Tabelas raw incluem constraint `ON CONFLICT` para UPSERT

**Colunas-chave das tabelas** (baseadas no dicionário de dados oficial do INEP):

| Tabela | Colunas Principais |
|---|---|
| `escolas` | `NU_ANO_CENSO`, `CO_ENTIDADE`, `NO_ENTIDADE`, `CO_UF`, `SG_UF`, `CO_MUNICIPIO`, `TP_DEPENDENCIA`, `TP_LOCALIZACAO`, `IN_AGUA_POTAVEL`, `IN_ENERGIA_INEXISTENTE`, `IN_INTERNET`, `IN_ACESSIBILIDADE` + diversas colunas de infraestrutura |
| `turmas` | `NU_ANO_CENSO`, `CO_ENTIDADE`, `ID_TURMA`, `CO_UF`, `SG_UF`, `TP_TIPO_TURMA`, `NU_MATRICULAS` |
| `matriculas` | `NU_ANO_CENSO`, `CO_ENTIDADE`, `ID_MATRICULA`, `CO_UF`, `SG_UF`, `TP_DEPENDENCIA`, `ID_TURMA` |

> [!NOTE]
> As tabelas serão criadas com `TEXT` para todas as colunas na staging para evitar erros de parse. Na raw, os tipos serão convertidos (INTEGER, VARCHAR) para melhor performance.

---

### Componente 4: Extração Dinâmica (`src/extract.py`)

#### [NEW] [extract.py](file:///c:/Users/bruno/OneDrive/Documentos/Github/repositorios/arco_dataeng_platform_challenge/src/extract.py)

**Fluxo**:
1. Faz `GET` na página `https://www.gov.br/inep/pt-br/acesso-a-informacao/dados-abertos/microdados/censo-escolar`
2. Usa BeautifulSoup para parsear HTML e encontrar todos os links (`<a href>`)
3. Filtra links que contenham `microdados_censo_escolar` ou padrão similar via regex
4. Seleciona o link do **ano mais recente** (extrai ano do URL/texto via regex)
5. **Fallback robusto**: Se o scraping falhar (a página usa JS dinâmico), usa padrão de URL conhecido: `https://download.inep.gov.br/dados_abertos/microdados_censo_escolar_{ano}.zip`
6. Baixa o ZIP com `requests` (streaming, com progress bar)
7. Salva em diretório temporário criado via `tempfile.mkdtemp()` — **portável entre OS**, sem caminhos hardcoded
8. Extrai via `zipfile`:
   - Busca recursivamente por `*ed_basica_*.CSV` → escolas
   - `*turmas_*.CSV` → turmas
   - `*matricula_sudeste_*.CSV` → matrículas (apenas Sudeste)
9. Retorna dict com paths dos CSVs extraídos
10. Limpeza automática do ZIP após extração

**Boas práticas aplicadas** (da skill `data-engineering-data-pipeline`):
- Retry com exponential backoff no download
- Timeout configurável
- Logging estruturado
- Metadados de extração (`_extracted_at`, `_source`)

---

### Componente 5: Carga de Dados (`src/load.py`)

#### [NEW] [load.py](file:///c:/Users/bruno/OneDrive/Documentos/Github/repositorios/arco_dataeng_platform_challenge/src/load.py)

**Fluxo**:
1. Recebe dict de paths dos CSVs
2. Para cada CSV:
   - `TRUNCATE staging.{tabela}` antes de inserir
   - Lê com `pd.read_csv()` em **chunks de 100.000 linhas**, encoding `latin-1`, sep `;`
   - Filtra `SG_UF == 'SP'` para reduzir volume
   - Seleciona apenas colunas relevantes (definidas em config)
   - Insere na staging via `df.to_sql()` com SQLAlchemy 2.0+ (`engine.connect()`)
3. Após carga completa da staging, executa **UPSERT** (staging → raw):
   - `INSERT INTO raw.escolas SELECT * FROM staging.escolas ON CONFLICT (CO_ENTIDADE, NU_ANO_CENSO) DO UPDATE SET ...`
   - Idem para turmas e matrículas
4. Logging de contagem de registros inseridos/atualizados

**Boas práticas aplicadas** (da skill `python-performance-optimization`):
- Chunks para controlar memória
- `method='multi'` no `to_sql()` para batch inserts
- Apenas colunas necessárias para economizar banda e memória

---

### Componente 6: Transformações SQL (`sql/transformations.sql`)

#### [NEW] [transformations.sql](file:///c:/Users/bruno/OneDrive/Documentos/Github/repositorios/arco_dataeng_platform_challenge/sql/transformations.sql)

**Views no schema `analytics`** (todas leem da camada `raw`):

| View | Descrição | Join/Agregação |
|---|---|---|
| `vw_escolas_por_uf_dependencia` | Escolas por UF e dependência administrativa | `GROUP BY SG_UF, TP_DEPENDENCIA` |
| `vw_escolas_por_localizacao` | Escolas por localização (Urbana/Rural) por UF | `GROUP BY SG_UF, TP_LOCALIZACAO` com CASE |
| `vw_escolas_infraestrutura` | % com internet, água, energia e acessibilidade | `AVG()` / `ROUND()` sobre `IN_*` |
| `vw_turmas_por_escola_uf` | Total de turmas e média por escola por UF | `COUNT(*) + AVG()` via subquery |
| `vw_matriculas_por_dependencia` | Total matrículas por dependência administrativa (bônus) | `JOIN escolas + turmas + matriculas` via `CO_ENTIDADE, NU_ANO_CENSO` |
| `vw_razao_alunos_turma` | Razão alunos/turma (bônus) | `SUM(matriculas) / COUNT(turmas)` |

**Diretriz de modelagem**: Todos os JOINs usam `CO_ENTIDADE` e `NU_ANO_CENSO` conforme padrão oficial do INEP.

---

### Componente 7: Orquestrador (`main.py`)

#### [NEW] [main.py](file:///c:/Users/bruno/OneDrive/Documentos/Github/repositorios/arco_dataeng_platform_challenge/main.py)

**Pipeline sequencial**:
```
1. Setup DB      → init_db.setup()
2. Extract       → extract.run()  → retorna paths dos CSVs (em tempdir do OS)
3. Load          → load.run(paths) → staging + UPSERT para raw
4. Transform     → Executa sql/transformations.sql
5. Cleanup       → shutil.rmtree(tempdir) — limpeza automática
```

- Logging estruturado com timestamp
- Tratamento de erros com mensagens claras
- Tempo total de execução

---

### Componente 8: Documentação (`README.md`)

#### [MODIFY] [README.md](file:///c:/Users/bruno/OneDrive/Documentos/Github/repositorios/arco_dataeng_platform_challenge/README.md)

**Seções**:
1. **Visão Geral e Arquitetura**: Diagrama de fluxo, decisões técnicas, requisito Python >= 3.10
2. **Arquitetura de Dados**: Diagrama das 3 camadas (staging → raw → analytics)
3. **Requisitos**: Python >= 3.10, Supabase, dependências
4. **Setup e Execução**: `.env`, `pip install`, `python main.py`
5. **Perguntas Conceituais**:
   - Atualização diária com GCP/Cloud Composer (DAG Airflow)
   - Garantia de não-duplicidade via chaves compostas + UPSERT
   - Consumo no Metabase via Modelagem Dimensional (Star Schema) + Dicionário de Dados
6. **Uso de IA**: Placeholder para relato

---

## Verification Plan

### Automated Tests
- `python -c "import sys; assert sys.version_info >= (3, 10), 'Python >= 3.10 required'; print('Python OK')"` — Verifica versão mínima
- `python -c "from src.config import get_engine; print('Config OK')"` — Verifica imports
- `python -c "import sqlalchemy; print(sqlalchemy.__version__)"` — Verifica SQLAlchemy 2.0+

### Manual Verification
- Execução do `python main.py` completo (requer `.env` com credenciais reais do Supabase)
- Verificação de que as views no schema `analytics` retornam dados corretos
- Confirmação de que o UPSERT não gera duplicatas em re-execuções

> [!NOTE]
> O pipeline completo não será executado automaticamente pois depende de credenciais reais do Supabase e download de ~2GB de dados. A verificação será focada em validação de sintaxe, imports e estrutura do código.
