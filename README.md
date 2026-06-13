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
    Dinâmico          Streaming           Chunks + UPSERT       gold.*
```

### Decisões Técnicas

| Decisão | Justificativa |
|---|---|
| **Scraping dinâmico** | O INEP não fornece API REST; links mudam entre anos. O scraping garante que o pipeline sempre encontre o ZIP mais recente. Fallback com padrão de URL como segurança. |
| **Streaming download** | ZIPs de ~2GB+ não cabem na RAM. O download é feito via `requests.iter_content()`, gravando direto em disco. |
| **`tempfile.mkdtemp()`** | Diretório temporário portável entre Windows, Linux, macOS e WSL. Sem caminhos hardcoded. |
| **Chunks de 50k linhas** | Controla consumo de memória. Funciona em ambientes com apenas 4GB de RAM (ex: WSL). Configurável via `.env`. |
| **Escala Nacional** | O pipeline processa dados de todas as UF's do Brasil em uma única rodada (filtro desativado). |
| **Raw + Silver (3 camadas)** | Raw permite reprocessamento; Silver com UPSERT garante idempotência; Gold gera métricas limpas. |
| **UPSERT com chave composta** | `(CO_ENTIDADE, NU_ANO_CENSO)` garante que re-execuções não dupliquem dados. |
| **SQLAlchemy 2.0+** | API moderna com tipagem, connection pooling e compatibilidade com Supabase. |
| **Todas as colunas TEXT na raw** | Evita erros de parse em CSV com dados sujos. A conversão de tipos ocorre no UPSERT para silver. |

---

## 📊 Arquitetura de Dados

O banco segue uma arquitetura em **3 camadas**:

```
┌─────────────────────────────────────────────────────────┐
│                    PostgreSQL (Supabase)                 │
│                                                         │
│  ┌─────────────┐   ┌─────────────┐   ┌───────────────┐ │
│  │   raw    │──▶│     silver     │──▶│   gold   │ │
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
| `raw` | `escolas` | — | Dados brutos das escolas (TEXT) |
| `raw` | `turmas` | — | Dados brutos das turmas (TEXT) |
| `raw` | `matriculas` | — | Dados brutos das matrículas (TEXT) |
| `silver` | `escolas` | `(co_entidade, nu_ano_censo)` | Escolas com tipos corretos |
| `silver` | `turmas` | `(id_turma, nu_ano_censo)` | Turmas com tipos corretos |
| `silver` | `matriculas` | `(id_matricula, nu_ano_censo)` | Matrículas com tipos corretos |

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
3. ✅ Carga massiva em chunks (Nacional) com UPSERT para silver
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
│   └── load.py              # CSV → Raw (chunks) → Silver (UPSERT)
├── sql/
│   ├── ddl.sql              # CREATE SCHEMA + CREATE TABLE
│   └── transformations.sql  # Wide Table Analítica (Mestra)
├── main.py                  # Orquestrador principal
├── .env.example             # Template de variáveis de ambiente
├── requirements.txt         # Dependências (Python >= 3.10)
├── README.md                # Esta documentação
└── .gitignore               # Arquivos ignorados pelo Git
```

---

## 📈 Métricas Geradas

O pipeline consolida todos os dados do país em uma única **Wide Table** (View Mestra) no schema `gold`:

| View | Descrição |
|---|---|
| `vw_censo_escolar_agregado` | Consolida agrupamentos por Ano, UF, Dependência Administrativa e Localização. Calcula totais, % de infraestrutura exigidas, médias e razões bônus (como escolas conectadas e alunos/turma). |

### Amostra Visual no Terminal

Ao final do pipeline, o Python automaticamente puxa os **Top 3 resultados** do banco e imprime na tela. Exemplo de saída:

```text
📊 AMOSTRA DOS DADOS ANALÍTICOS (TOP 3):

🏆 RANK 1 ---
  nu_ano_censo             : 2025
  sg_uf                    : SP
  ds_dependencia           : Estadual
  ds_localizacao           : Urbana
  total_escolas            : 5320
  total_turmas             : 145890
  total_matriculas         : 4580000
  pct_com_internet         : 99.80
  pct_com_banda_larga      : 98.50
  pct_com_agua_potavel     : 100.00
  pct_com_energia          : 99.90
  pct_com_acessibilidade   : 75.40
  pct_escolas_conectadas   : 98.40
  media_turmas_escola      : 27.42
  media_alunos_escola      : 860.90
  razao_alunos_turma       : 31.39

🏆 RANK 2 ---
  ...
```

---

## 💡 Perguntas Conceituais

### 1. Como atualizar diariamente utilizando Terraform, GitHub Actions, Docker e Kubernetes?

Para transformar este pipeline *one-shot* em uma execução diária robusta, aderente às práticas de DevOps e Plataforma de Dados utilizadas em ambientes corporativos escaláveis (como na Arco):

**Arquitetura proposta:**

```text
Terraform (IaC)
    ├── Provisiona Banco de Dados (PostgreSQL)
    ├── Provisiona Container Registry (AWS ECR ou GCP Artifact Registry)
    └── Provisiona Cluster Kubernetes (EKS / GKE)

GitHub Actions (CI/CD)
    ├── Trigger: Push na branch 'main'
    ├── Build: Cria a imagem Docker do pipeline
    └── Deploy: Faz o push para o Registry e aplica o manifesto no Kubernetes

Kubernetes (Execução Diária)
    └──▶ K8s CronJob (ex: schedule: "0 6 * * *")
            └──▶ Instancia um Pod efêmero com a imagem do pipeline
                  └──▶ Executa `python main.py` e o Pod é finalizado
```

**Implementação:**

1. **Dockerização**: O código do pipeline (`main.py`, arquivos auxiliares e dependências) é encapsulado em uma imagem utilizando um `Dockerfile`.
2. **Terraform**: Ele provisiona o banco de dados, o cluster Kubernetes e as regras de acesso (IAM). Após a primeira criação, ele só é executado novamente se a infraestrutura precisar mudar (ex: dar "scale up" na memória do banco ou criar um ambiente de *raw*).
3. **GitHub Actions**: Pipeline de CI/CD automatizado. Ao detectar uma mudança no código (Python ou SQL), faz o *build* da nova imagem Docker e a entrega no K8s.
4. **Kubernetes**: É aqui que a **execução diária** acontece de fato. O Kubernetes levanta um *Pod* com o pipeline no horário agendado, ele processa os dados e desliga em seguida.
---

### 2. Como garantir não-duplicidade com chaves compostas e UPSERT?

**Mecanismo implementado:**

```sql
-- Chave composta garante unicidade por entidade + ano
CONSTRAINT pk_raw_escolas PRIMARY KEY (co_entidade, nu_ano_censo)

-- UPSERT: insere se novo, atualiza se já existe
INSERT INTO silver.escolas (...)
SELECT ... FROM raw.escolas
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

**Estratégia: OBT (One Big Table) com Dicionário de Dados**

Para garantir um consumo eficiente e facilitado por usuários de negócio no Metabase, a modelagem adotada na camada `gold` foi a de **OBT (One Big Table)**. Esta abordagem consolida todas as dimensões e métricas em uma única grande tabela/view desnormalizada.

```text
┌────────────────────────────────────────────────────────────────────────┐
│                   vw_censo_escolar_agregado (OBT)                      │
├──────────────────┬──────────────────┬─────────────────┬────────────────┤
│    Dimensões     │    Dimensões     │    Métricas     │    Métricas    │
│    Temporais     │   Geográficas    │     Gerais      │    Derivadas   │
├──────────────────┼──────────────────┼─────────────────┼────────────────┤
│ nu_ano_censo     │ sg_uf            │ total_escolas   │ razao_alunos_  │
│                  │ ds_localizacao   │ total_turmas    │ turma          │
│                  │                  │ total_matriculas│ media_turmas...│
└──────────────────┴──────────────────┴─────────────────┴────────────────┘
```

**Por que OBT (One Big Table)?**
- **Performance de Leitura:** Elimina a necessidade de múltiplos `JOINs` no momento da query, acelerando os relatórios do BI.
- **Usabilidade (Self-Service BI):** O usuário de negócios encontra todas as métricas e recortes disponíveis em uma única "tabela", não precisando entender os relacionamentos de um modelo relacional clássico.

**Boas práticas para o consumo no BI:**

1. **Dicionário de Dados**: Documentar a origem e a regra de negócio de cada métrica disponível na tabela, garantindo que o usuário de negócio saiba exatamente o que está analisando.
2. **Nomenclatura Amigável**: Renomear colunas no BI para termos claros e de negócio (ex: `sg_uf` vira "Estado"), facilitando a cultura de Self-Service BI.
3. **Criação de Filtros Globais**: Como todas as dimensões (`Ano`, `UF`, `Localização`) já estão na tabela, fica muito simples configurar painéis interativos onde o usuário filtra todo o dashboard sem necessidade de novas queries.
4. **Ocultação de Campos Técnicos**: Esconder do usuário final os campos de controle do banco de dados (como datas de processamento e IDs sistêmicos), mantendo a interface limpa e focada apenas nas métricas.

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
