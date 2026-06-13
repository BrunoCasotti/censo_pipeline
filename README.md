# 🎓 Pipeline de Microdados do Censo Escolar — Arco Educação

> **Data Engineering Platform Challenge**
> Pipeline *one-shot* que extrai, carrega e transforma os Microdados do Censo Escolar (INEP) em um PostgreSQL hospedado no Supabase.

---

## 📋 Índice

- [Visão Geral e Arquitetura](#-visão-geral-e-arquitetura)
- [Arquitetura de Dados](#-arquitetura-de-dados)
- [Requisitos](#-requisitos)
- [Setup e Execução](#-setup-e-execução)
- [Estrutura do Projeto](#-estrutura-do-projeto)
- [Métricas Geradas](#-métricas-geradas)
- [Perguntas Conceituais](#-perguntas-conceituais)
- [Uso de IA](#-uso-de-ia)

---

## 🏗️ Visão Geral e Arquitetura

### O que faz?

Este pipeline automatiza o processo completo de **ELT (Extract, Load, Transform)** dos Microdados do Censo Escolar publicados pelo INEP/MEC:

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   INEP Web   │────▶│   Download   │────▶│   Load to    │────▶│  Transform   │
│  (Scraping)  │     │  ZIP + CSV   │     │  PostgreSQL  │     │  (SQL Views) │
└──────────────┘     └──────────────┘     └──────────────┘     └──────────────┘
    Dinâmico          Streaming           Chunks + UPSERT       analytics.*
```

### Decisões Técnicas

| Decisão | Justificativa |
|---|---|
| **Scraping dinâmico** | O INEP não fornece API REST; links mudam entre anos. O scraping garante que o pipeline sempre encontre o ZIP mais recente. Fallback com padrão de URL como segurança. |
| **Streaming download** | ZIPs de ~2GB+ não cabem na RAM. O download é feito via `requests.iter_content()`, gravando direto em disco. |
| **`tempfile.mkdtemp()`** | Diretório temporário portável entre Windows, Linux, macOS e WSL. Sem caminhos hardcoded. |
| **Chunks de 50k linhas** | Controla consumo de memória. Funciona em ambientes com apenas 4GB de RAM (ex: WSL). Configurável via `.env`. |
| **Filtro por UF (SP)** | Reduz volume de dados em ~95%. Os microdados completos têm 50M+ de matrículas; SP tem ~10M. |
| **Staging + Raw (3 camadas)** | Staging permite reprocessamento; Raw com UPSERT garante idempotência; Analytics gera métricas limpas. |
| **UPSERT com chave composta** | `(CO_ENTIDADE, NU_ANO_CENSO)` garante que re-execuções não dupliquem dados. |
| **SQLAlchemy 2.0+** | API moderna com tipagem, connection pooling e compatibilidade com Supabase. |
| **Todas as colunas TEXT na staging** | Evita erros de parse em CSV com dados sujos. A conversão de tipos ocorre no UPSERT para raw. |

---

## 📊 Arquitetura de Dados

O banco segue uma arquitetura em **3 camadas**:

```
┌─────────────────────────────────────────────────────────┐
│                    PostgreSQL (Supabase)                 │
│                                                         │
│  ┌─────────────┐   ┌─────────────┐   ┌───────────────┐ │
│  │   staging    │──▶│     raw     │──▶│   analytics   │ │
│  │  (TEXT cols) │   │ (Typed +    │   │  (SQL Views)  │ │
│  │  Temporário  │   │  UPSERT PK) │   │  Métricas     │ │
│  └─────────────┘   └─────────────┘   └───────────────┘ │
│    TRUNCATE/cada     Histórico          Derivado        │
│    execução          Idempotente        Somente leitura │
└─────────────────────────────────────────────────────────┘
```

### Tabelas

| Schema | Tabela | Chave Primária | Descrição |
|---|---|---|---|
| `staging` | `escolas` | — | Dados brutos das escolas (TEXT) |
| `staging` | `turmas` | — | Dados brutos das turmas (TEXT) |
| `staging` | `matriculas` | — | Dados brutos das matrículas (TEXT) |
| `raw` | `escolas` | `(co_entidade, nu_ano_censo)` | Escolas com tipos corretos |
| `raw` | `turmas` | `(id_turma, nu_ano_censo)` | Turmas com tipos corretos |
| `raw` | `matriculas` | `(id_matricula, nu_ano_censo)` | Matrículas com tipos corretos |

### Chaves Relacionais (Diretriz INEP)

```
escolas.CO_ENTIDADE ←──── turmas.CO_ENTIDADE
escolas.NU_ANO_CENSO ←──── turmas.NU_ANO_CENSO

escolas.CO_ENTIDADE ←──── matriculas.CO_ENTIDADE
escolas.NU_ANO_CENSO ←──── matriculas.NU_ANO_CENSO

turmas.ID_TURMA ←──── matriculas.ID_TURMA
turmas.NU_ANO_CENSO ←──── matriculas.NU_ANO_CENSO
```

---

## ⚙️ Requisitos

- **Python**: >= 3.10 (testado com 3.10, 3.11, 3.12, 3.13)
- **PostgreSQL**: Supabase (ou qualquer PostgreSQL 14+)
- **Espaço em disco**: ~3GB temporário para download e extração
- **RAM**: Mínimo 4GB (chunk size configurável)
- **Internet**: Necessária para download dos microdados (~2GB)

---

## 🚀 Setup e Execução

### 1. Clone o repositório

```bash
git clone https://github.com/seu-usuario/arco_dataeng_platform_challenge.git
cd arco_dataeng_platform_challenge
```

### 2. Crie o ambiente virtual (recomendado)

```bash
python -m venv .venv

# Linux / macOS / WSL
source .venv/bin/activate

# Windows
.venv\Scripts\activate
```

### 3. Instale as dependências

```bash
pip install -r requirements.txt
```

### 4. Configure as variáveis de ambiente

```bash
cp .env.example .env
```

Edite o `.env` com suas credenciais do Supabase:

```env
# Connection string do Supabase (Settings → Database → Connection string → URI)
SUPABASE_DB_URL=postgresql://postgres.xxxx:sua_senha@aws-0-sa-east-1.pooler.supabase.com:6543/postgres

# Tamanho do chunk (ajuste conforme sua RAM disponível)
CHUNK_SIZE=50000
```

### 5. Execute o pipeline

```bash
python main.py
```

O pipeline executará automaticamente:
1. ✅ Criação de schemas e tabelas no Supabase
2. ✅ Download dos microdados mais recentes do INEP
3. ✅ Carga em chunks, filtro SP, UPSERT para raw
4. ✅ Criação das views analíticas

---

## 📁 Estrutura do Projeto

```
arco_dataeng_platform_challenge/
├── src/
│   ├── __init__.py          # Package init
│   ├── config.py            # Configurações centralizadas (env vars)
│   ├── init_db.py           # Setup automático do banco (DDL)
│   ├── extract.py           # Scraping + download + extração
│   └── load.py              # CSV → Staging (chunks) → Raw (UPSERT)
├── sql/
│   ├── ddl.sql              # CREATE SCHEMA + CREATE TABLE
│   └── transformations.sql  # Views analíticas (6 views)
├── main.py                  # Orquestrador principal
├── .env.example             # Template de variáveis de ambiente
├── requirements.txt         # Dependências (Python >= 3.10)
├── README.md                # Esta documentação
└── .gitignore               # Arquivos ignorados pelo Git
```

---

## 📈 Métricas Geradas

As seguintes views são criadas no schema `analytics`:

| View | Descrição |
|---|---|
| `vw_escolas_por_uf_dependencia` | Escolas por UF e dependência administrativa (Federal, Estadual, Municipal, Privada) |
| `vw_escolas_por_localizacao` | Escolas por localização (Urbana/Rural) por UF |
| `vw_escolas_infraestrutura` | % de escolas com internet, água, energia e acessibilidade |
| `vw_turmas_por_escola_uf` | Total de turmas e média de turmas por escola, por UF |
| `vw_matriculas_por_dependencia` | **[Bônus]** Total de matrículas por dependência administrativa |
| `vw_razao_alunos_turma` | **[Bônus]** Razão alunos por turma |

### Exemplo de consulta

```sql
-- Top UFs por % de escolas com internet
SELECT sg_uf, pct_internet, pct_agua_potavel, pct_energia, pct_acessibilidade
FROM analytics.vw_escolas_infraestrutura
ORDER BY pct_internet DESC;
```

---

## 💡 Perguntas Conceituais

### 1. Como atualizar diariamente usando GCP/Cloud Composer?

Para transformar este pipeline *one-shot* em uma execução diária na GCP:

**Arquitetura proposta:**

```
Cloud Scheduler (cron diário)
    └──▶ Cloud Composer (Airflow)
            └──▶ DAG com 4 Tasks:
                  ├── setup_db_task      (PythonOperator → init_db.setup())
                  ├── extract_task       (PythonOperator → extract.run())
                  ├── load_task          (PythonOperator → load.run())
                  └── transform_task     (PostgresOperator → transformations.sql)
```

**Implementação:**

1. **Cloud Composer**: Criar um ambiente Composer (Airflow gerenciado) na GCP.
2. **DAG Airflow**: Converter `main.py` em uma DAG com tasks encadeadas via `>>`.
3. **Secrets**: Mover `SUPABASE_DB_URL` para o Secret Manager da GCP, referenciado via `Variable.get()`.
4. **Schedule**: `schedule_interval="0 6 * * *"` (todo dia às 6h UTC).
5. **Alertas**: Configurar SLA com `sla=timedelta(hours=2)` e notificação via e-mail/Slack no `on_failure_callback`.
6. **Idempotência**: O UPSERT com chave composta garante que re-execuções não dupliquem dados — essencial para retries automáticos do Airflow.

**Alternativa serverless**: Cloud Functions (trigger via Cloud Scheduler) ou Cloud Run Jobs para pipelines mais leves.

---

### 2. Como garantir não-duplicidade com chaves compostas e UPSERT?

**Mecanismo implementado:**

```sql
-- Chave composta garante unicidade por entidade + ano
CONSTRAINT pk_raw_escolas PRIMARY KEY (co_entidade, nu_ano_censo)

-- UPSERT: insere se novo, atualiza se já existe
INSERT INTO raw.escolas (...)
SELECT ... FROM staging.escolas
ON CONFLICT (co_entidade, nu_ano_censo)
DO UPDATE SET
    no_entidade = EXCLUDED.no_entidade,
    ...
    _loaded_at = NOW();
```

**Por que funciona:**

- A **Primary Key composta** `(CO_ENTIDADE, NU_ANO_CENSO)` cria um índice único no PostgreSQL.
- O `INSERT ... ON CONFLICT ... DO UPDATE` (UPSERT) tem dois comportamentos:
  - **Registro novo**: INSERT normal.
  - **Registro existente**: UPDATE dos campos (mantém a mesma PK).
- O campo `_loaded_at = NOW()` registra quando o dado foi atualizado pela última vez.
- **Resultado**: Não importa quantas vezes o pipeline execute — os dados nunca serão duplicados.

---

### 3. Como garantir o consumo correto no Metabase?

**Estratégia: Modelagem Dimensional (Star Schema) + Dicionário de Dados**

Para consumo eficiente no Metabase, recomenda-se evoluir a camada `analytics` para um **Star Schema**:

```
                    ┌─────────────┐
                    │ dim_escola  │
                    │ (dimensão)  │
                    └──────┬──────┘
                           │
┌──────────────┐   ┌──────┴──────┐   ┌──────────────┐
│ dim_tempo     │───│ fato_censo  │───│ dim_municipio │
│ (ano, mês)   │   │ (métricas)  │   │ (UF, cidade) │
└──────────────┘   └──────┬──────┘   └──────────────┘
                           │
                    ┌──────┴──────┐
                    │ dim_turma   │
                    │ (dimensão)  │
                    └─────────────┘
```

**Implementação prática:**

1. **Dimensões**: Criar tabelas `dim_escola`, `dim_tempo`, `dim_municipio` com atributos descritivos (nomes por extenso, labels amigáveis).
2. **Fato**: Tabela `fato_censo` com métricas numéricas (`total_alunos`, `total_turmas`) e foreign keys para as dimensões.
3. **Dicionário de Dados**: Documentar cada campo no Metabase (Settings → Admin → Table Metadata), incluindo:
   - Descrição humana de cada coluna
   - Tipo semântico (category, quantity, location, etc.)
   - Valores possíveis (ex: `TP_DEPENDENCIA: 1=Federal, 2=Estadual, 3=Municipal, 4=Privada`)
4. **Metabase Models**: Usar a feature *Models* do Metabase para criar entidades semânticas a partir das views do `analytics`, facilitando perguntas ad-hoc por não-técnicos.
5. **Cache**: Configurar cache do Metabase por view/question para evitar sobrecarga no banco.

---

## 🤖 Uso de IA

*[Espaço reservado para relato do uso de ferramentas de IA durante o desenvolvimento]*

<!-- 
Descreva aqui como ferramentas de IA foram utilizadas no desenvolvimento:
- Quais ferramentas (ChatGPT, Copilot, Claude, etc.)
- Em quais etapas (design, código, documentação, debug)
- Como você validou e ajustou o output gerado
- Decisões que foram tomadas por você vs. sugeridas pela IA
-->

---

## 📄 Licença

Projeto desenvolvido como teste técnico para a **Arco Educação**.
Dados públicos do [INEP/MEC](https://www.gov.br/inep).
