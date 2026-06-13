# Walkthrough — Pipeline Censo Escolar (INEP)

## Resumo

Implementação completa do pipeline **one-shot** de Data Engineering para o desafio técnico da Arco Educação. O pipeline extrai dinamicamente os Microdados do Censo Escolar (INEP), carrega no PostgreSQL/Supabase e gera métricas analíticas via SQL.

## Arquivos Criados/Modificados

### Configuração do Projeto (3 arquivos)

| Arquivo | Ação | Descrição |
|---|---|---|
| [requirements.txt](file:///c:/Users/bruno/OneDrive/Documentos/Github/repositorios/arco_dataeng_platform_challenge/requirements.txt) | NOVO | 6 dependências com Python >= 3.10 |
| [.env.example](file:///c:/Users/bruno/OneDrive/Documentos/Github/repositorios/arco_dataeng_platform_challenge/.env.example) | NOVO | Template com SUPABASE_DB_URL + CHUNK_SIZE configurável |
| [.gitignore](file:///c:/Users/bruno/OneDrive/Documentos/Github/repositorios/arco_dataeng_platform_challenge/.gitignore) | MODIFICADO | Adicionado `tmp/` |

### Módulos Python (5 arquivos em `src/`)

| Arquivo | Descrição |
|---|---|
| [__init__.py](file:///c:/Users/bruno/OneDrive/Documentos/Github/repositorios/arco_dataeng_platform_challenge/src/__init__.py) | Package init com docstring |
| [config.py](file:///c:/Users/bruno/OneDrive/Documentos/Github/repositorios/arco_dataeng_platform_challenge/src/config.py) | Configs centralizadas: env vars, engine SQLAlchemy, colunas por tabela |
| [init_db.py](file:///c:/Users/bruno/OneDrive/Documentos/Github/repositorios/arco_dataeng_platform_challenge/src/init_db.py) | Executa DDL para criar schemas/tabelas |
| [extract.py](file:///c:/Users/bruno/OneDrive/Documentos/Github/repositorios/arco_dataeng_platform_challenge/src/extract.py) | Scraping + download streaming + extração ZIP com regex |
| [load.py](file:///c:/Users/bruno/OneDrive/Documentos/Github/repositorios/arco_dataeng_platform_challenge/src/load.py) | Chunks 50k → staging → UPSERT raw com chave composta |

### SQL (2 arquivos em `sql/`)

| Arquivo | Descrição |
|---|---|
| [ddl.sql](file:///c:/Users/bruno/OneDrive/Documentos/Github/repositorios/arco_dataeng_platform_challenge/sql/ddl.sql) | 3 schemas + 6 tabelas (staging TEXT + raw tipada) + 5 índices |
| [transformations.sql](file:///c:/Users/bruno/OneDrive/Documentos/Github/repositorios/arco_dataeng_platform_challenge/sql/transformations.sql) | 6 views analíticas com JOINs INEP |

### Orquestrador e Documentação

| Arquivo | Descrição |
|---|---|
| [main.py](file:///c:/Users/bruno/OneDrive/Documentos/Github/repositorios/arco_dataeng_platform_challenge/main.py) | Pipeline sequencial: Setup → Extract → Load → Transform → Cleanup |
| [README.md](file:///c:/Users/bruno/OneDrive/Documentos/Github/repositorios/arco_dataeng_platform_challenge/README.md) | Documentação completa com arquitetura, setup e perguntas conceituais |

---

## What was Tested

1. **Pipeline Completo End-to-End**: 
    - Extração automática da pasta no formato agregado (2025).
    - Carga `Staging` `->` `Raw` ajustada para o novo formato de dados (nível escola ao invés de nível turma/matrícula granular).
    - Tipagem correta ao fazer UPSERT para Postgres/Supabase.
    - Otimização do parser de SQL para as Views Analíticas.
2. **Correção de Bugs**:
    - Bug com falha de Constraints/Tipos no UPSERT resolvido (substituição por `QT_*` campos).
    - Erro Unicode (Trash Emoji) resolvido trocando `print()` por `logger.info()`.
    - Views analíticas que não eram criadas devido a falhas no parsing de comentários SQL, foram corrigidas.

## Validation Results

O pipeline `main.py` roda com sucesso completo:
1. **Setup do BD**: DDL recriado.
2. **Extração**: Dados de 2025 extraídos perfeitamente (3 CSVs).
3. **Carga**: Staging e UPSERT para RAW concluídos:
   - *escolas*: 33.616 carregadas
   - *matriculas*: 178.766 agregadas
   - *turmas*: 178.772 agregadas
4. **Transformação**: 6 views criadas corretamente usando o novo schema! 
5. **Logs**: Nenhum erro Unicode no término da execução.

Para verificar localmente:
```bash
python -c "import py_compile; [py_compile.compile(f) for f in ['main.py', 'src/config.py', 'src/init_db.py', 'src/extract.py', 'src/load.py']]; print('OK')"
```
