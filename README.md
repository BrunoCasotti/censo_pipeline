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
| **Raw/Silver/Gold** | Raw permite reprocessamento; Silver com UPSERT garante idempotência; Gold gera métricas limpas. |
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

## 💡 Perguntas Conceituais

Esta seção detalha as estratégias adotadas no desenho da solução, abordando orquestração, consistência de dados e consumo analítico.

### 1. Como atualizar diariamente utilizando Terraform, GitHub Actions, Docker e Kubernetes?

O projeto foi desenhado para suportar transição fluida de execuções manuais (*one-shot*) para processos diários automatizados, utilizando o seguinte ecossistema:

**Topologia de Implantação:**

```text
Terraform (IaC)
    ├── Banco de Dados (PostgreSQL)
    ├── Container Registry (AWS ECR / GCP Artifact Registry)
    └── Cluster Kubernetes (EKS / GKE)

GitHub Actions (CI/CD)
    ├── Trigger: Evento de 'push' na branch 'main'
    ├── Build: Empacotamento do container via Dockerfile
    └── Deploy: Publicação da imagem e aplicação do manifesto no K8s

Kubernetes (Agendamento e Computação)
    └──▶ K8s CronJob (Ex: schedule: "0 6 * * *")
            └──▶ Pod Efêmero (Processamento Data pipeline)
                  └──▶ `python main.py` -> Finalização do container
```

**Componentes:**
- **Docker**: Encapsulamento da aplicação e dependências para garantir reprodutibilidade.
- **Terraform**: Gerenciamento do ciclo de vida da infraestrutura em nuvem, garantindo versionamento dos recursos base.
- **GitHub Actions**: Pipeline de integração contínua encarregado de testar e gerar a imagem do container a cada nova versão do repositório.
- **Kubernetes (CronJob)**: Orquestrador da carga horária que instancia o pipeline, realiza o processamento e destrói o Pod em seguida, otimizando o uso de computação.

---

### 2. Como garantir não-duplicidade com chaves compostas e UPSERT?

A modelagem de banco de dados prevê ingestões incrementais ou re-processamentos sem gerar redundância, aplicando a técnica de **UPSERT**.

**Lógica Aplicada:**

```sql
-- Definição de chave composta como garantia de unicidade
CONSTRAINT pk_silver_escolas PRIMARY KEY (co_entidade, nu_ano_censo)

-- Operação UPSERT
INSERT INTO silver.escolas (...)
SELECT ... FROM raw.escolas
ON CONFLICT (co_entidade, nu_ano_censo)
DO UPDATE SET
    no_entidade = EXCLUDED.no_entidade,
    ...
    _loaded_at = NOW();
```

**Benefícios:**
- **Restrição de Banco:** A constraint de *Primary Key* combinada (`CO_ENTIDADE` e `NU_ANO_CENSO`) bloqueia fisicamente duplicações.
- **Idempotência:** A instrução `ON CONFLICT DO UPDATE` valida o registro: se for inédito, realiza o `INSERT`; se já existir, sobrescreve os dados defasados por meio do `UPDATE`. O pipeline pode ser executado *n* vezes sem corromper a base.
- **Rastreabilidade:** A coluna `_loaded_at` registra o *timestamp* da última alteração.

---

### 3. Como garantir o consumo correto no Metabase?

A interface final para ferramentas de visualização (ex: Metabase) baseia-se em uma modelagem do tipo **OBT (One Big Table)** disponibilizada na camada `gold`.

**Estrutura Lógica (OBT):**

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

**Diretrizes de Implementação e Boas Práticas:**
- **Desempenho de Leitura:** A desnormalização suprime a necessidade de processamento massivo de `JOINs` no banco transacional no momento da leitura, diminuindo a latência para o usuário.
- **Self-Service BI:** Simplifica a exploração. Usuários sem domínio de SQL compreendem a visão linear sem depender da engenharia de dados para montar consultas relacionais.
- **Semântica e Dicionário de Dados:** O catálogo do BI deve traduzir campos técnicos para o jargão de negócio (ex: `sg_uf` -> "Estado da Federação"), provendo descrições formais sobre o cálculo de métricas derivadas.
- **Filtros Globais:** A consolidação de dimensões possibilita a aplicação de filtros em nível de painel que interagem diretamente com o dataset base sem *subqueries* complexas.
- **Governança:** Metadados como chaves primárias numéricas ou datas de controle de carga (`_loaded_at`) não são expostos aos painéis dos usuários finais, reduzindo ruído visual.

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
