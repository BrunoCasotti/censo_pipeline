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
| **Raw/Silver/Gold** | Raw permite reprocessamento; Silver com Delete+Insert garante consistência; Gold gera métricas limpas. |
| **Chave composta** | `(CO_ENTIDADE, NU_ANO_CENSO)` na deleção e inserção garante que re-execuções não dupliquem dados. |
| **SQLAlchemy 2.0+** | API moderna com tipagem, connection pooling e compatibilidade com Supabase. |
| **Todas as colunas TEXT na raw** | Evita erros de parse em CSV com dados sujos. A conversão de tipos ocorre no insert para silver. |

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
│  │  Temporário  │   │  PK exata)  │   │  Métricas     │ │
│  └─────────────┘   └─────────────┘   └───────────────┘ │
│    TRUNCATE/cada     Histórico          Derivado        │
│    execução          Consistente        Somente leitura │
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
3. ✅ Carga massiva em chunks (Nacional) com deleção e inserção na silver
4. ✅ Validação de Data Quality via Great Expectations (Completeness, Validity, Integrity)
5. ✅ Criação das views analíticas na camada gold
6. ✅ Geração automática do Dashboard HTML com indicadores finais

---

## 📁 Estrutura do Projeto

```
arco_dataeng_platform_challenge/
├── src/
│   ├── __init__.py          # Package init
│   ├── config.py            # Configurações centralizadas (env vars)
│   ├── init_db.py           # Setup automático do banco (DDL)
│   ├── extract.py           # Scraping + download + extração
│   ├── load.py              # CSV → Raw (chunks) → Silver (Delete+Insert)
│   └── data_quality.py      # Bateria de testes usando Great Expectations
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

## 📈 Amostra do Dashboard Analítico (Gold)

![Amostra do Dashboard Analítico Gerado](./assets/dashboard_preview.png)
*Visualização estática em HTML construída a partir dos dados agregados da Wide Table.*

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

### 2. Como garantir não-duplicidade e consistência nas cargas da camada Silver?

A modelagem de banco de dados prevê ingestões incrementais ou re-processamentos sem gerar redundância, aplicando a técnica de deleção prévia combinada com dedreplicação ativa.

**Lógica Aplicada:**

```sql
-- 1. Deleção prévia de registros já existentes
DELETE FROM silver.turmas 
WHERE (co_entidade, nu_ano_censo) IN (SELECT co_entidade, nu_ano_censo FROM raw.turmas);

-- 2. Inserção direta
INSERT INTO silver.turmas (...)
SELECT ... 
FROM raw.turmas;
```

**Benefícios:**
- **Chave Conceitual:** A combinação (`CO_ENTIDADE` e `NU_ANO_CENSO`) atua como nossa chave de agrupamento lógico, permitindo limpeza segmentada sem engessar a tabela com restrições rígidas (Primary Keys).
- **Consistência (Delete + Insert):** A exclusão prévia limpa os dados defasados para aquelas chaves específicas. Logo em seguida, o `INSERT` transfere os dados atualizados idênticos à origem (raw), garantindo fidelidade de 100% ao arquivo CSV do INEP. O pipeline pode ser executado *n* vezes sem acumular registros fantasmas.

---

### 3. Garantia de Qualidade de Dados (Great Expectations)

Para elevar a resiliência e a confiabilidade do pipeline, integramos o **Great Expectations** rodando via *Ephemeral Data Context* na Etapa 4 do pipeline.

Assim que a carga para a camada `silver` termina, o script `src/data_quality.py` dispara as seguintes expectativas diretamente no banco PostgreSQL para cada tabela alvo:
- **Completeness (Volume de Dados):** O volume de registros da `silver` deve ser matematicamente igual aos carregados na `raw`.
- **Integrity (Chaves Não-Nulas):** A chave entidade (`co_entidade`) nunca pode estar em branco.
- **Validity (Domínio de Tempo):** A variável do ano (`nu_ano_censo`) deve pertencer à década atual (entre 2020 e 2030).

Se as validações passarem, o pipeline prossegue para as agregações da `gold`. Caso algo reprove, logs críticos apontando as anomalias são gerados imediatamente para o analista atuar!

---

### 4. Como garantir o consumo correto no Metabase?

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

**Onde você usou IA e com qual objetivo?**

Eu basicamente dividi o uso da IA em 4 etapas no meu fluxo de trabalho:

1. **Arquitetura inicial:** Utilizei o Gemini (chat) para elaborar o prompt inicial baseado em todos os pontos trazidos no texto do case.
2. **Planejamento de código:** A partir desse escopo inicial, fui para o Antigravity para criar o plano de implementação. Nesse ponto, já utilizando algumas *skills* para deixar o planejamento mais específico possível e gerar um bom primeiro projeto.
3. **Coding:** Criação, edição do código e interação para correções de bugs.
4. **Documentação e Visualização:** Criar uma documentação bem explicativa sobre o passo a passo para executar o projeto e como ele funciona. E criar um dashboard de exemplo das métricas para demonstrar de forma mais visual o resultado do pipeline.

**O que funcionou bem?**

Funcionou super bem fazer esse planejamento da arquitetura inicial do projeto visando o que o case pedia, pois na implementação não precisei verbalizar tantos detalhes específicos para tudo funcionar. E também a utilização de *skills* e *knowledges* como base de conhecimento para que o modelo entendesse bem o contexto e o que precisava ser feito.

**Onde a saída da IA estava errada ou incompleta e como você percebeu, validou e corrigiu?**

Ao lidar com cenários reais de engenharia de dados, é comum a IA gerar saídas genéricas que precisam de correção técnica. Tive dois exemplos diretos disso no projeto:

* **Exemplo 1 (Upsert e Chaves Primárias):** A IA sugeriu usar `PRIMARY KEY` restrita na camada Silver e `ON CONFLICT DO UPDATE`. Porém, a granularidade dos dados do INEP possui duplicidades naturais na mesma chave (`co_entidade`, `nu_ano_censo`). Ao testar, o pipeline quebrou com *UniqueViolation*. Validei na raw e corrigi a IA instruindo a remoção da restrição física e o uso da abordagem de `DELETE` (pela chave) + `INSERT` total, garantindo 100% de fidelidade ao CSV original sem perda de dados.
* **Exemplo 2 (Performance de Validação):** Ao configurar o Great Expectations, a primeira saída da IA foi puxar a tabela inteira do PostgreSQL para a memória (Pandas) usando `SELECT *`. Como são muitas linhas, isso facilmente causaria estouro de memória (Out of Memory). Instruí a IA a refazer a lógica para o banco (fazendo as métricas direto no SQL via `COUNT` e `SUM(CASE)`). Com isso, o banco processa os dados e envia apenas 1 linha consolidada para a validação do Great Expectations.

---

## 📄 Licença

Projeto desenvolvido como teste técnico para a **Arco Educação**.
Dados públicos do [INEP/MEC](https://www.gov.br/inep).
