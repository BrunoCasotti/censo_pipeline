import os
import pandas as pd
from src.config import get_engine, logger

viewport_css = """
/* 1. Lock html/body to viewport */
html, body { height: 100%; overflow-x: hidden; }
html { scroll-snap-type: y mandatory; scroll-behavior: smooth; }
.slide { width: 100vw; height: 100vh; height: 100dvh; overflow: hidden; scroll-snap-align: start; display: flex; flex-direction: column; position: relative; }
.slide-content { flex: 1; display: flex; flex-direction: column; justify-content: flex-start; max-height: 100%; overflow: hidden; padding: var(--slide-padding); }
:root {
    --title-size: clamp(1.2rem, 4vw, 2.5rem);
    --h2-size: clamp(1rem, 2.5vw, 1.8rem);
    --h3-size: clamp(0.9rem, 2vw, 1.4rem);
    --body-size: clamp(0.7rem, 1.2vw, 1rem);
    --small-size: clamp(0.6rem, 1vw, 0.75rem);
    --slide-padding: clamp(1rem, 3vw, 2rem);
    --content-gap: clamp(0.5rem, 1.5vw, 1.5rem);
    --element-gap: clamp(0.25rem, 1vw, 0.75rem);
}
.card, .container, .content-box { max-width: min(95vw, 1200px); }
.grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 250px), 1fr)); gap: clamp(0.5rem, 1vw, 1.5rem); }
@media (max-width: 600px) { :root { --title-size: clamp(1.2rem, 6vw, 2rem); } .grid { grid-template-columns: 1fr; } }
@media (prefers-reduced-motion: reduce) { *, *::before, *::after { animation-duration: 0.01ms !important; transition-duration: 0.2s !important; } html { scroll-behavior: auto; } }

/* Table Styles */
.analytical-table-container {
    width: 100%;
    max-height: 30vh;
    overflow-y: auto;
    overflow-x: auto;
    margin-top: 1.5rem;
    border-radius: 8px;
    background: rgba(255,255,255,0.05);
    border: 1px solid rgba(255,255,255,0.1);
    box-shadow: 0 10px 30px rgba(0,0,0,0.2);
}
.analytical-table {
    width: 100%;
    border-collapse: collapse;
    font-size: var(--small-size);
    color: #fff;
    white-space: nowrap;
}
.analytical-table th {
    background: rgba(0,28,70,0.9);
    padding: 0.8rem 1rem;
    text-align: left;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    position: sticky;
    top: 0;
    z-index: 10;
    border-bottom: 2px solid var(--accent-red);
}
.analytical-table td {
    padding: 0.6rem 1rem;
    border-bottom: 1px solid rgba(255,255,255,0.05);
}
.analytical-table tbody tr:hover {
    background: rgba(255,255,255,0.1);
}
/* Scrollbar */
::-webkit-scrollbar { width: 8px; height: 8px; }
::-webkit-scrollbar-track { background: rgba(0,0,0,0.1); border-radius: 4px; }
::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.2); border-radius: 4px; }
::-webkit-scrollbar-thumb:hover { background: rgba(255,255,255,0.4); }

/* Tooltip Informativo 'i' */
.tooltip-container { display: inline-block; position: relative; cursor: help; margin-left: 10px; vertical-align: middle; }
.tooltip-icon { display: inline-flex; align-items: center; justify-content: center; width: 24px; height: 24px; border-radius: 50%; background-color: var(--accent-blue); color: white; font-size: 14px; font-weight: bold; font-family: var(--font-body); box-shadow: 0 4px 10px rgba(47,116,208,0.2); transition: transform 0.2s ease; }
.tooltip-container:hover .tooltip-icon { transform: scale(1.1); }
.tooltip-content { visibility: hidden; opacity: 0; position: absolute; top: 130%; left: 50%; transform: translateX(-50%) translateY(-10px); background-color: #FFFFFF; color: #4A5568; text-align: left; padding: 1rem; border-radius: 8px; border: 1px solid rgba(0,28,70,0.1); width: max-content; max-width: 400px; font-size: 0.8rem; line-height: 1.4; box-shadow: 0 10px 30px rgba(0,28,70,0.15); transition: all 0.3s cubic-bezier(0.25, 1, 0.5, 1); z-index: 1000; }
.tooltip-content::after { content: ""; position: absolute; bottom: 100%; left: 50%; margin-left: -8px; border-width: 8px; border-style: solid; border-color: transparent transparent #FFFFFF transparent; }
.tooltip-container:hover .tooltip-content { visibility: visible; opacity: 1; transform: translateX(-50%) translateY(0); }
.tooltip-content strong { color: var(--text-on-card); font-family: var(--font-display); letter-spacing: 0; font-size: 0.85rem; }
.tooltip-content .t-item { margin-bottom: 0.4rem; display: block; font-family: var(--font-body); font-weight: 500; color: #4A5568 !important; }
"""

arco_svg = """
<div style="font-family: 'Archivo Black', sans-serif; font-size: 55px; font-weight: 900; color: #FFFFFF; letter-spacing: -2px; line-height: 1; margin-bottom: -5px;">arco</div>
"""

col_mapping = {
    'nu_ano_censo': 'Ano',
    'sg_uf': 'UF',
    'ds_dependencia': 'Dependência',
    'ds_localizacao': 'Localização',
    'total_escolas': 'Total Escolas',
    'total_turmas': 'Total Turmas',
    'total_matriculas': 'Total Matrículas',
    'pct_com_internet': '% Internet',
    'pct_com_banda_larga': '% Banda Larga',
    'pct_com_agua_potavel': '% Água',
    'pct_com_energia': '% Energia',
    'pct_com_acessibilidade': '% Acessibilidade',
    'pct_escolas_conectadas': '% Conectadas',
    'media_turmas_escola': 'Turmas/Escola',
    'media_alunos_escola': 'Alunos/Escola',
    'razao_alunos_turma': 'Alunos/Turma'
}

def generate_cards_html(df):
    cards = []
    # Evitar erro de NoneType em métricas nulas
    df_clean = df.fillna(0)
    for i, row in df_clean.iterrows():
        d = row.to_dict()
        
        # Formatar números
        total_escolas = f"{int(d.get('total_escolas', 0)):,}".replace(',', '.')
        matriculas = f"{int(d.get('total_matriculas', 0)):,}".replace(',', '.')
        superlotacao = f"{float(d.get('razao_alunos_turma', 0)):.1f}"
        
        acessibilidade = float(d.get('pct_com_acessibilidade', 0))
        conectadas = float(d.get('pct_escolas_conectadas', 0))
        
        acess_bar = f'<div style="width: 100%; background: #eee; height: 5px; border-radius: 3px; margin-top: 4px;"><div style="width: {acessibilidade}%; background: var(--accent-blue); height: 100%; border-radius: 3px;"></div></div>'
        conect_bar = f'<div style="width: 100%; background: #eee; height: 5px; border-radius: 3px; margin-top: 4px;"><div style="width: {conectadas}%; background: var(--accent-red); height: 100%; border-radius: 3px;"></div></div>'
        
        cards.append(f"""
        <div class="card reveal delay-{i+3}" style="background: var(--card-bg); border-radius: 12px; padding: 1.2rem; position: relative; box-shadow: 0 10px 20px rgba(0,0,0,0.3);">
            <div style="position: absolute; top: -15px; right: 15px; background: var(--accent-red); color: #fff; width: 35px; height: 35px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-family: var(--font-display); font-size: 1.1rem; box-shadow: 0 4px 10px rgba(230,28,20,0.4);">#{i+1}</div>
            
            <h3 style="color: var(--text-on-card); font-family: var(--font-display); margin-bottom: 0.1rem; font-size: var(--h2-size);">{d.get('sg_uf', '')}</h3>
            <p style="color: var(--accent-blue); font-size: var(--small-size); margin-bottom: 0.8rem; text-transform: uppercase; font-weight: 800; letter-spacing: 0.5px;">{d.get('ds_dependencia', '')} • {d.get('ds_localizacao', '')}</p>
            
            <div style="display: grid; grid-template-columns: 1fr; gap: 0.8rem; border-top: 1px solid rgba(0,0,0,0.1); padding-top: 1rem;">
                <!-- Row 1 -->
                <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 0.5rem;">
                    <div>
                        <strong style="color: var(--text-on-card); display: block; font-size: var(--h3-size); line-height: 1;">{total_escolas}</strong>
                        <span style="font-size: var(--small-size); color: rgba(0,0,0,0.6); font-weight: 700; text-transform: uppercase;">Escolas</span>
                    </div>
                    <div>
                        <strong style="color: var(--text-on-card); display: block; font-size: var(--h3-size); line-height: 1;">{matriculas}</strong>
                        <span style="font-size: var(--small-size); color: rgba(0,0,0,0.6); font-weight: 700; text-transform: uppercase;">Matrículas</span>
                    </div>
                    <div>
                        <strong style="color: var(--accent-red); display: block; font-size: var(--h3-size); line-height: 1;">{superlotacao}</strong>
                        <span style="font-size: var(--small-size); color: rgba(0,0,0,0.6); font-weight: 700; text-transform: uppercase;">Alunos/Turma</span>
                    </div>
                </div>
                <!-- Row 2 -->
                <div style="margin-top: 0.2rem;">
                    <div style="display: flex; justify-content: space-between; align-items: flex-end;">
                        <span style="font-size: var(--small-size); color: var(--text-on-card); font-weight: 700;">% de escola com acessibilidade</span>
                        <strong style="color: var(--accent-blue); font-size: var(--body-size);">{acessibilidade}%</strong>
                    </div>
                    {acess_bar}
                </div>
                <!-- Row 3 -->
                <div style="margin-top: 0.1rem;">
                    <div style="display: flex; justify-content: space-between; align-items: flex-end;">
                        <span style="font-size: var(--small-size); color: var(--text-on-card); font-weight: 700;">% de escolas conectadas</span>
                        <strong style="color: var(--accent-red); font-size: var(--body-size);">{conectadas}%</strong>
                    </div>
                    {conect_bar}
                </div>
            </div>
        </div>
        """)
    return "\n".join(cards)

def generate_table_html(df):
    # Renomear colunas
    df_table = df.rename(columns=col_mapping)
    
    # Gerar HTML da tabela
    thead = "<tr>" + "".join(f"<th>{col}</th>" for col in df_table.columns) + "</tr>"
    
    tbody = ""
    for _, row in df_table.iterrows():
        tr = "<tr>"
        for val in row:
            # Formatação simples para exibição
            if isinstance(val, float):
                display_val = f"{val:.2f}".rstrip('0').rstrip('.') if val % 1 != 0 else f"{int(val)}"
            else:
                display_val = str(val)
            tr += f"<td>{display_val}</td>"
        tr += "</tr>"
        tbody += tr
        
    html = f"""
    <div class="analytical-table-container reveal delay-5">
        <table class="analytical-table">
            <thead>
                {thead}
            </thead>
            <tbody>
                {tbody}
            </tbody>
        </table>
    </div>
    """
    return html

def generate_dashboard():
    logger.info("Iniciando geração do Dashboard Analítico (HTML)...")
    try:
        engine = get_engine()
        query = "SELECT * FROM gold.vw_censo_escolar_agregado ORDER BY media_alunos_escola DESC NULLS LAST LIMIT 3;"
        df = pd.read_sql(query, engine)
        df = df.fillna(0)
        logger.info(f"Dados da view carregados com sucesso. Linhas: {len(df)}")
    except Exception as e:
        logger.error(f"Erro ao consultar a view gold.vw_censo_escolar_agregado: {e}")
        return

    cards_html = generate_cards_html(df)
    table_html = generate_table_html(df)

    arco_html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Censo Escolar - Arco Educação</title>
    <link href="https://fonts.googleapis.com/css2?family=Archivo+Black&family=Space+Grotesk:wght@400;500;700&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg-primary: #001C46;
            --bg-gradient: linear-gradient(145deg, #001C46 0%, #002D62 100%);
            --card-bg: #FFFFFF;
            --text-primary: #FFFFFF;
            --text-on-card: #001C46;
            --accent-red: #E61C14;
            --accent-blue: #2F74D0;
            --font-display: 'Archivo Black', sans-serif;
            --font-body: 'Space Grotesk', sans-serif;
            --duration-normal: 0.6s;
            --ease-out-expo: cubic-bezier(0.16, 1, 0.3, 1);
        }}
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        {viewport_css}
        body {{ font-family: var(--font-body); background: var(--bg-gradient); color: var(--text-primary); }}
        .reveal {{ opacity: 0; transform: translateY(20px); transition: opacity var(--duration-normal) var(--ease-out-expo), transform var(--duration-normal) var(--ease-out-expo); }}
        .slide.visible .reveal {{ opacity: 1; transform: translateY(0); }}
        
        .reveal.delay-1 {{ transition-delay: 0.1s; }}
        .reveal.delay-2 {{ transition-delay: 0.2s; }}
        .reveal.delay-3 {{ transition-delay: 0.3s; }}
        .reveal.delay-4 {{ transition-delay: 0.4s; }}
        .reveal.delay-5 {{ transition-delay: 0.5s; }}
    </style>
</head>
<body>
    <section class="slide visible">
        <div class="slide-content" style="max-width: 1300px; margin: 0 auto; width: 100%;">
            
            <!-- Header Section -->
            <div style="margin-bottom: 1.5rem; display: flex; align-items: flex-end; justify-content: space-between; border-bottom: 1px solid rgba(255,255,255,0.1); padding-bottom: 1rem; position: relative; z-index: 1000;">
                <div>
                    <h1 class="reveal delay-1" style="font-family: var(--font-display); font-size: var(--title-size); text-transform: uppercase; letter-spacing: -1px; line-height: 1;">CENSO ESCOLAR <span style="color: var(--accent-red);">2025</span></h1>
                    <div class="reveal delay-2" style="font-size: var(--h3-size); margin-top: 0.3rem; font-weight: 500; display: flex; align-items: center; position: relative; z-index: 50;">
                        <span style="opacity: 0.8;">Destaques de Infraestrutura (Top 3)</span>
                        <div class="tooltip-container">
                            <span class="tooltip-icon">i</span>
                            <div class="tooltip-content">
                                <strong>Critérios & Métricas:</strong><br><br>
                                <span class="t-item"><strong>Filtro Base:</strong> Apenas escolas em atividade.</span>
                                <span class="t-item"><strong>Ordenação (Top 3):</strong> Maiores médias de alunos por escola (media_alunos_escola DESC).</span>
                                <span class="t-item"><strong>% Acessibilidade:</strong> Escolas com pelo menos 1 item de acessibilidade.</span>
                                <span class="t-item"><strong>% Conectadas:</strong> Escolas com Internet, Banda Larga e Energia simultaneamente.</span>
                            </div>
                        </div>
                    </div>
                </div>
                <div class="reveal delay-2">
                    {arco_svg}
                </div>
            </div>

            <!-- Cards Grid -->
            <div class="grid" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 1.5rem;">
                {cards_html}
            </div>

            <!-- Analytical Table -->
            {table_html}

        </div>
    </section>
</body>
</html>"""

    # Salva na raiz do projeto
    output_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'dashboard_arco.html')
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(arco_html)
        
    logger.info(f"Dashboard gerado com sucesso em: {output_path}")

if __name__ == "__main__":
    generate_dashboard()
