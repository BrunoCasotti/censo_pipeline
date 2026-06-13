# =============================================================================
# src/extract.py — Extração dinâmica dos Microdados do Censo Escolar (INEP)
# =============================================================================
"""Extração dinâmica dos Microdados do Censo Escolar (INEP) via web scraping."""

import os
import re
import time
import tempfile
import zipfile
from datetime import datetime

import requests
import urllib3
from bs4 import BeautifulSoup

from src.config import INEP_BASE_URL, INEP_DOWNLOAD_PATTERN, logger

# Sites .gov.br frequentemente têm cadeia SSL incompleta.
# Desabilita o aviso de verificação SSL para esses domínios.
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Constantes internas
_TIMEOUT = 30  # Timeout para requisições HTTP (segundos)
_DOWNLOAD_TIMEOUT = 1800  # Timeout para download do ZIP (30 minutos)
_MAX_RETRIES = 3
_RETRY_BACKOFF = 2  # Fator de backoff exponencial
_STREAM_CHUNK_SIZE = 8192  # 8KB por iteração de download


# Funções de Scraping

def _find_latest_zip_url() -> tuple[str, int]:
    """
    Faz scraping da página do INEP e retorna (url_do_zip, ano).

    Estratégia:
    1. Parseia HTML da página de microdados
    2. Busca links (<a href>) que contenham 'microdados' e '.zip'
    3. Extrai o ano do link/texto e seleciona o mais recente

    Returns:
        Tupla (url, ano) do ZIP mais recente encontrado.

    Raises:
        RuntimeError: Se nenhum link de download for encontrado.
    """
    logger.info(f"Buscando links de download em: {INEP_BASE_URL}")

    try:
        response = requests.get(INEP_BASE_URL, timeout=_TIMEOUT, verify=False)
        response.raise_for_status()
    except requests.RequestException as e:
        logger.warning(f"Falha ao acessar página do INEP: {e}")
        raise RuntimeError(f"Não foi possível acessar a página do INEP: {e}")

    soup = BeautifulSoup(response.text, "html.parser")

    # Busca todos os links que parecem ser downloads de microdados
    candidates: list[tuple[str, int]] = []

    for link in soup.find_all("a", href=True):
        href = link["href"]
        text = link.get_text(strip=True)

        # Verifica se o link é um ZIP de microdados do censo escolar
        if not re.search(r"microdados.*censo|censo.*microdados", href + text, re.I):
            continue

        # Tenta extrair o ano do link ou texto
        year_match = re.search(r"(20[1-2]\d)", href + text)
        if year_match:
            year = int(year_match.group(1))
            # Normaliza URL absoluta
            url = href if href.startswith("http") else f"https://www.gov.br{href}"
            candidates.append((url, year))
            logger.debug(f"  Candidato encontrado: ano={year}, url={url[:80]}...")

    if not candidates:
        raise RuntimeError(
            "Nenhum link de microdados encontrado na página do INEP. "
            "A estrutura da página pode ter mudado."
        )

    # Seleciona o mais recente
    candidates.sort(key=lambda x: x[1], reverse=True)
    url, year = candidates[0]
    
    logger.info(f"📋 Ano mais recente encontrado: {year}")
    logger.info(f"📋 URL do ZIP: {url}")

    return url, year


def _get_download_url() -> tuple[str, int]:
    """
    Tenta obter a URL de download via scraping.
    Em caso de falha, usa fallback com padrão de URL conhecido.

    Returns:
        Tupla (url, ano).
    """
    try:
        return _find_latest_zip_url()
    except RuntimeError as e:
        logger.warning(f"Scraping falhou: {e}")
        logger.info("Usando fallback: tentando anos recentes em ordem decrescente...")

        current_year = datetime.now().year
        for year in range(current_year, current_year - 5, -1):
            url = INEP_DOWNLOAD_PATTERN.format(year=year)
            try:
                resp = requests.head(
                    url, timeout=_TIMEOUT, allow_redirects=True, verify=False
                )
                if resp.status_code == 200:
                    logger.info(f"✅ Fallback encontrou ZIP para {year}: {url}")
                    return url, year
            except requests.RequestException:
                continue

        raise RuntimeError(
            "Não foi possível encontrar os microdados nem via scraping, "
            "nem via fallback. Verifique sua conexão com a internet."
        )


# Download com retry e progress

def _download_zip(url: str, dest_dir: str) -> str:
    """
    Baixa o ZIP via streaming com retry e exponential backoff.

    Args:
        url: URL do arquivo ZIP.
        dest_dir: Diretório de destino para salvar o arquivo.

    Returns:
        Caminho completo do arquivo ZIP baixado.
    """
    zip_filename = os.path.join(dest_dir, "microdados_censo_escolar.zip")

    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            logger.info(
                f"⬇️  Iniciando download (tentativa {attempt}/{_MAX_RETRIES})..."
            )
            logger.info(f"   URL: {url}")

            response = requests.get(
                url, stream=True, timeout=_DOWNLOAD_TIMEOUT, verify=False
            )
            response.raise_for_status()

            # Tamanho total (se disponível)
            total_size = int(response.headers.get("content-length", 0))
            if total_size:
                logger.info(
                    f"   Tamanho: {total_size / (1024**2):.1f} MB"
                )

            # Download com streaming (não carrega tudo em memória)
            downloaded = 0
            with open(zip_filename, "wb") as f:
                for chunk in response.iter_content(chunk_size=_STREAM_CHUNK_SIZE):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)

                        # Log de progresso a cada 100MB
                        if total_size and downloaded % (100 * 1024**2) < _STREAM_CHUNK_SIZE:
                            pct = (downloaded / total_size) * 100
                            logger.info(
                                f"   Progresso: {downloaded / (1024**2):.0f}MB "
                                f"/ {total_size / (1024**2):.0f}MB ({pct:.1f}%)"
                            )

            logger.info(
                f"✅ Download concluído: {downloaded / (1024**2):.1f} MB"
            )
            return zip_filename

        except requests.RequestException as e:
            logger.warning(f"   Erro no download: {e}")
            if attempt < _MAX_RETRIES:
                wait = _RETRY_BACKOFF ** attempt
                logger.info(f"   Aguardando {wait}s antes de tentar novamente...")
                time.sleep(wait)
            else:
                raise RuntimeError(
                    f"Download falhou após {_MAX_RETRIES} tentativas: {e}"
                )

    # Nunca deveria chegar aqui, mas type checker exige
    raise RuntimeError("Falha inesperada no download.")


# Extração dos CSVs relevantes

def _extract_csvs(zip_path: str, dest_dir: str) -> dict[str, str]:
    """
    Extrai do ZIP apenas os CSVs relevantes usando regex:
    - Escolas:    *ed_basica*.CSV (case-insensitive)
    - Turmas:     *turmas*.CSV
    - Matrículas: *matricula_sudeste*.CSV (apenas Sudeste)

    Args:
        zip_path: Caminho do arquivo ZIP.
        dest_dir: Diretório de destino para os CSVs extraídos.

    Returns:
        Dict com chaves 'escolas', 'turmas', 'matriculas' e paths dos CSVs.
    """
    logger.info("📦 Extraindo CSVs do ZIP...")

    # Padrões regex para identificar os arquivos dentro do ZIP
    # Suporta nomenclatura antiga (microdados_*escolas*) e nova (Tabela_Escola_*)
    patterns = {
        "escolas": re.compile(
            r"(microdados.*escolas|tabela_escola|ed_basica).*\.csv$", re.IGNORECASE
        ),
        "turmas": re.compile(
            r"(microdados.*turmas|tabela_turma|turmas).*\.csv$", re.IGNORECASE
        ),
        "matriculas": re.compile(
            r"(microdados.*matricula|tabela_matricula|matricula).*\.csv$", re.IGNORECASE
        ),
    }

    found: dict[str, str] = {}

    with zipfile.ZipFile(zip_path, "r") as zf:
        all_files = zf.namelist()
        logger.info(f"   Total de arquivos no ZIP: {len(all_files)}")

        # Lista apenas CSVs para debug
        csv_files = [f for f in all_files if f.lower().endswith(".csv")]
        logger.info(f"   CSVs encontrados: {[os.path.basename(f) for f in csv_files]}")

        for name in all_files:
            for key, pattern in patterns.items():
                if key not in found and pattern.search(name):
                    # Extrai o arquivo para dest_dir
                    extracted_path = zf.extract(name, dest_dir)
                    found[key] = extracted_path
                    logger.info(f"   ✅ {key}: {os.path.basename(name)}")

    # Valida que todos os arquivos foram encontrados
    missing = set(patterns.keys()) - set(found.keys())
    if missing:
        logger.warning(
            f"⚠️  Arquivos não encontrados no ZIP: {missing}. "
            f"CSVs disponíveis: {[os.path.basename(f) for f in csv_files]}"
        )
        raise RuntimeError(
            f"Não foi possível encontrar os seguintes CSVs no ZIP: {missing}. "
            f"CSVs disponíveis: {[os.path.basename(f) for f in csv_files]}. "
            f"Verifique se o formato dos microdados mudou."
        )

    return found


# Função principal de extração

def run() -> tuple[dict[str, str], str, int]:
    """
    Executa o pipeline completo de extração:
    1. Encontra URL do ZIP mais recente
    2. Baixa o ZIP em diretório temporário
    3. Extrai CSVs relevantes
    4. Remove o ZIP (mantém apenas os CSVs)

    Returns:
        Tupla (csv_paths, temp_dir, ano):
        - csv_paths: Dict {'escolas': path, 'turmas': path, 'matriculas': path}
        - temp_dir: Caminho do diretório temporário (para limpeza posterior)
        - ano: Ano do censo extraído
    """
    logger.info("=" * 60)
    logger.info("ETAPA: EXTRAÇÃO DOS MICRODADOS DO INEP")
    logger.info("=" * 60)

    # 1. Encontrar URL de download
    url, year = _get_download_url()

    # 2. Criar diretório temporário (portável entre OS)
    temp_dir = tempfile.mkdtemp(prefix="censo_escolar_")
    logger.info(f"📁 Diretório temporário: {temp_dir}")

    try:
        # 3. Download do ZIP
        zip_path = _download_zip(url, temp_dir)

        # 4. Extração dos CSVs
        csv_paths = _extract_csvs(zip_path, temp_dir)

        # 5. Remove o ZIP (mantém CSVs para a carga)
        os.remove(zip_path)
        logger.info("🗑️  ZIP removido após extração.")

    except Exception:
        # Em caso de erro, tenta limpar o temp_dir
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise

    logger.info(f"✅ Extração concluída. {len(csv_paths)} CSVs prontos para carga.")
    return csv_paths, temp_dir, year


if __name__ == "__main__":
    paths, tmp, yr = run()
    print(f"Ano: {yr}")
    print(f"Temp dir: {tmp}")
    for k, v in paths.items():
        print(f"  {k}: {v}")
