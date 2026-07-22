import os
import re
import sys
import argparse
import pytesseract
import fitz  # PyMuPDF
from PIL import Image
from concurrent.futures import ProcessPoolExecutor, as_completed

# ============================================================================
# CONFIGURAÇÕES DE AMBIENTE (WINDOWS)
# Ajuste os caminhos abaixo conforme a sua instalação.
# ============================================================================
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

# Configure o diretório de tessdata para o Tesseract.
# Prioriza a pasta local do workspace, depois a instalação padrão.
tessdata_padrao = r'C:\Program Files\Tesseract-OCR\tessdata'
tessdata_local = os.path.join(os.path.dirname(__file__), 'tessdata')
TESSDATA_DIR = None
if os.path.isdir(tessdata_local):
    TESSDATA_DIR = tessdata_local
elif os.path.isdir(tessdata_padrao):
    TESSDATA_DIR = tessdata_padrao

if TESSDATA_DIR:
    os.environ['TESSDATA_PREFIX'] = TESSDATA_DIR
    print(f'Usando tessdata em: {TESSDATA_DIR}')
else:
    print('Aviso: tessdata não encontrado. A OCR pode falhar se o idioma não estiver instalado.')

def extrair_identificador_documento(texto_ocr):
    """
    Analisa o texto do OCR e busca por padrões de identificação do caso.
    """
    # Padrão 1: Requisição de Perícia (Ex: REQUISIÇÃO DE PERÍCIA Nº 1234/2026)
    padrao_req = re.search(r"REQUISI[CÇ][AÃ]O.*?N[°ºO0.]?\s*(\d{2,6})\s*[/.-]\s*(\d{4})", texto_ocr, re.IGNORECASE)
    if padrao_req:
        return f"REQ_{padrao_req.group(1)}_{padrao_req.group(2)}"

    # Padrão 2: Boletim de Ocorrência / RDO
    padrao_bo = re.search(r"(?:B\.?O\.?|R\.?D\.?O\.?).*?N[°ºO0.]?\s*(\d{2,6})\s*[/.-]\s*(\d{4})", texto_ocr, re.IGNORECASE)
    if padrao_bo:
        return f"BO_{padrao_bo.group(1)}_{padrao_bo.group(2)}"
        
    # Padrão 3: protocolo no formato I04319/26, procurando primeiro por contexto.
    padrao_protocolo = re.compile(r"[,IIl1]?\s*(\d{4,6})\s*[/.-]\s*(\d{2})")

    def ano_valido(ano_str):
        ano = int(ano_str)
        return 20 <= ano <= 30

    linhas = texto_ocr.splitlines()
    for idx, linha in enumerate(linhas):
        if re.search(r"protocolo", linha, re.IGNORECASE):
            janela = linhas[idx:idx + 4]
            for texto_janela in janela:
                match = padrao_protocolo.search(texto_janela)
                if match and ano_valido(match.group(2)):
                    return f"I{match.group(1)}_{match.group(2)}"

    # Caso não haja linha de contexto explícita, buscar protocolo geral com ano plausível.
    match_geral = padrao_protocolo.search(texto_ocr)
    if match_geral and ano_valido(match_geral.group(2)):
        return f"I{match_geral.group(1)}_{match_geral.group(2)}"

    # Padrão 4: Portaria
    padrao_portaria = re.search(r"PORTARIA.*?N[°ºO0.]?\s*(\d{2,6})\s*[/.-]\s*(\d{4})", texto_ocr, re.IGNORECASE)
    if padrao_portaria:
        return f"PORTARIA_{padrao_portaria.group(1)}_{padrao_portaria.group(2)}"

    return None


def processar_pagina(pdf_bytes, num_pagina):
    """
    Função auxiliar para processamento via multiprocessamento.
    """
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    pagina = doc[num_pagina]
    
    texto_pagina = pagina.get_text() or ""
    texto_norm = re.sub(r"\s+", " ", texto_pagina.strip().lower())
    
    if not texto_norm:
        # OCR na imagem inteira apenas se não houver texto
        pix = pagina.get_pixmap(dpi=200)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        texto_pagina = pytesseract.image_to_string(img, lang='por') or ""
        texto_norm = re.sub(r"\s+", " ", texto_pagina.strip().lower())
        
    identificador = None
    is_blank = not texto_norm
    has_marker = "final final final final final" in texto_norm
    
    if not is_blank and not has_marker:
        # OCR do cabeçalho (quadrante superior direito)
        w, h = pagina.rect.width, pagina.rect.height
        clip_rect = fitz.Rect(w * 0.5, 0, w, h * 0.5)
        pix_topo = pagina.get_pixmap(dpi=200, clip=clip_rect)
        img_topo = Image.frombytes("RGB", [pix_topo.width, pix_topo.height], pix_topo.samples)
        texto_topo = pytesseract.image_to_string(img_topo, lang='por')
        identificador = extrair_identificador_documento(texto_topo)
        
    doc.close()
    
    return {
        "num_pagina": num_pagina,
        "is_blank": is_blank,
        "has_marker": has_marker,
        "identificador": identificador
    }


def processar_lote_requisicoes(caminho_pdf_entrada, diretorio_saida="documentos_separados"):
    if not os.path.exists(diretorio_saida):
        os.makedirs(diretorio_saida)

    print(f"Iniciando leitura do lote: {caminho_pdf_entrada}")
    
    with open(caminho_pdf_entrada, "rb") as f:
        pdf_bytes = f.read()
        
    doc_original = fitz.open(stream=pdf_bytes, filetype="pdf")
    total_paginas = len(doc_original)
    
    print(f"Analisando {total_paginas} páginas com multiprocessamento (aguarde)...")
    
    resultados_paginas = [None] * total_paginas
    
    with ProcessPoolExecutor() as executor:
        futures = {executor.submit(processar_pagina, pdf_bytes, i): i for i in range(total_paginas)}
        for future in as_completed(futures):
            resultado = future.result()
            resultados_paginas[resultado["num_pagina"]] = resultado
            print(f"Página {resultado['num_pagina'] + 1}/{total_paginas} analisada.")
            
    print("\nMontando os novos documentos separados...")
    
    doc_atual = fitz.open()
    nome_arquivo_atual = "000_documento_desconhecido_inicio.pdf"
    
    for resultado in resultados_paginas:
        if resultado["is_blank"] or resultado["has_marker"]:
            continue
            
        identificador = resultado["identificador"]
        
        if identificador:
            novo_nome_esperado = f"{identificador}.pdf"
            
            # Só separa se o cabeçalho encontrado for diferente do arquivo que já está aberto!
            # Isso evita que páginas da mesma requisição que repetem o cabeçalho quebrem o documento.
            if novo_nome_esperado != nome_arquivo_atual:
                # Salva o PDF atual antes de criar um novo
                if len(doc_atual) > 0:
                    doc_atual.save(os.path.join(diretorio_saida, nome_arquivo_atual))
                    print(f" -> Salvo: {nome_arquivo_atual}")
                    doc_atual.close()
                    doc_atual = fitz.open()
                    
                nome_arquivo_atual = novo_nome_esperado
                print(f"*** Novo cabeçalho detectado: {nome_arquivo_atual} ***")
            
        doc_atual.insert_pdf(doc_original, from_page=resultado["num_pagina"], to_page=resultado["num_pagina"])
        
    if len(doc_atual) > 0:
        doc_atual.save(os.path.join(diretorio_saida, nome_arquivo_atual))
        print(f" -> Salvo: {nome_arquivo_atual}")
        doc_atual.close()
        
    doc_original.close()
    print("Processamento concluído com sucesso!")


def processar_pagina_marcador(pdf_bytes, num_pagina, marcador_norm):
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    pagina = doc[num_pagina]
    
    texto_pagina = pagina.get_text() or ""
    texto_norm = re.sub(r"\s+", " ", texto_pagina.strip().lower())
    
    if not texto_norm:
        pix = pagina.get_pixmap(dpi=200)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        texto_pagina = pytesseract.image_to_string(img, lang='por') or ""
        texto_norm = re.sub(r"\s+", " ", texto_pagina.strip().lower())
        
    is_blank = not texto_norm
    has_marker = marcador_norm in texto_norm
    doc.close()
    
    return {
        "num_pagina": num_pagina,
        "is_blank": is_blank,
        "has_marker": has_marker
    }


def separar_por_marcador(caminho_pdf_entrada, marcador="final final final final final", diretorio_saida="documentos_separados"):
    if not os.path.exists(diretorio_saida):
        os.makedirs(diretorio_saida)
    
    marcador_norm = re.sub(r"\s+", " ", marcador.strip().lower())
    print(f"Iniciando separação por marcador no arquivo: {caminho_pdf_entrada}")
    
    with open(caminho_pdf_entrada, "rb") as f:
        pdf_bytes = f.read()
        
    doc_original = fitz.open(stream=pdf_bytes, filetype="pdf")
    total_paginas = len(doc_original)
    
    print(f"Analisando {total_paginas} páginas com multiprocessamento...")
    
    resultados_paginas = [None] * total_paginas
    
    with ProcessPoolExecutor() as executor:
        futures = {executor.submit(processar_pagina_marcador, pdf_bytes, i, marcador_norm): i for i in range(total_paginas)}
        for future in as_completed(futures):
            resultado = future.result()
            resultados_paginas[resultado["num_pagina"]] = resultado
            print(f"Página {resultado['num_pagina'] + 1}/{total_paginas} analisada.")
            
    print("\nMontando os novos documentos...")
    
    doc_atual = fitz.open()
    parte_idx = 1
    
    for resultado in resultados_paginas:
        if resultado["is_blank"]:
            continue
            
        if resultado["has_marker"]:
            if len(doc_atual) > 0:
                nome_saida = os.path.join(diretorio_saida, f"requisicoes_part_{parte_idx:03d}.pdf")
                doc_atual.save(nome_saida)
                print(f" -> Salvo: {nome_saida}")
                doc_atual.close()
                doc_atual = fitz.open()
                parte_idx += 1
            continue
            
        doc_atual.insert_pdf(doc_original, from_page=resultado["num_pagina"], to_page=resultado["num_pagina"])
        
    if len(doc_atual) > 0:
        nome_saida = os.path.join(diretorio_saida, f"requisicoes_part_{parte_idx:03d}.pdf")
        doc_atual.save(nome_saida)
        print(f" -> Salvo: {nome_saida}")
        doc_atual.close()
        
    doc_original.close()
    print("Separação por marcador concluída.")


def _normalizar_protocolo_from_text(texto):
    """
    Tenta localizar e normalizar um protocolo no formato I#####/YY na string de texto.
    Retorna string normalizada como 'I<numero>_<ano>' (underscore para usar em nome de arquivo), ou None.
    """
    if not texto:
        return None

    # busca padrão com letra I (pode ser l/1 incorretos na OCR), número e ano com 2 dígitos
    m = re.search(r'([Ii1l])\s*(0*\d{3,6})\s*[/.-]\s*(\d{2})', texto)
    if not m:
        # fallback: apenas número/ano sem o I explícito, mas com contexto de 'I' próximo
        m2 = re.search(r'(\d{3,6})\s*[/.-]\s*(\d{2})', texto)
        if m2:
            num = m2.group(1)
            ano = m2.group(2)
            try:
                ano_val = int(ano)
                if 0 <= ano_val <= 99 and 20 <= ano_val <= 26:
                    return f'I{num}_{ano}'
            except Exception:
                return None
        return None

    letra = m.group(1)
    num = m.group(2)
    ano = m.group(3)
    letra_norm = 'I'

    try:
        ano_val = int(ano)
        if not (20 <= ano_val <= 26):
            return None
    except Exception:
        return None

    return f"{letra_norm}{num}_{ano}"


def processar_arquivo_renomear(caminho):
    """Função isolada para renomear, usada no multiprocessing."""
    try:
        doc = fitz.open(caminho)
        pagina = doc[0]
        texto = pagina.get_text() or ""
        protocolo = _normalizar_protocolo_from_text(texto)
        
        if not protocolo:
            # Tentar OCR na região maior do topo
            w, h = pagina.rect.width, pagina.rect.height
            clip_rect = fitz.Rect(0, 0, w, h * 0.35)
            pix = pagina.get_pixmap(dpi=200, clip=clip_rect)
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            texto_ocr = pytesseract.image_to_string(img, lang='por')
            protocolo = _normalizar_protocolo_from_text(texto_ocr)
            
        doc.close()
        return caminho, protocolo
    except Exception as e:
        return caminho, None


def renomear_por_ocr(diretorio_saida='documentos_separados'):
    """
    Percorre os PDFs, extrai protocolo da primeira página usando PyMuPDF/OCR e renomeia.
    """
    if not os.path.isdir(diretorio_saida):
        print(f"Diretório não encontrado: {diretorio_saida}")
        return

    arquivos = sorted([f for f in os.listdir(diretorio_saida) if f.lower().endswith('.pdf')])
    if not arquivos:
        print("Nenhum PDF encontrado para renomear.")
        return

    caminhos = [os.path.join(diretorio_saida, f) for f in arquivos]
    
    print(f"Lendo cabeçalhos de {len(caminhos)} arquivos em paralelo...")
    
    resultados = []
    with ProcessPoolExecutor() as executor:
        futures = {executor.submit(processar_arquivo_renomear, caminho): caminho for caminho in caminhos}
        for future in as_completed(futures):
            resultados.append(future.result())

    # Renomeação de fato (sequencial para evitar conflitos de sistema de arquivos)
    for caminho, protocolo in resultados:
        if protocolo:
            novo_nome = f"{protocolo}.pdf"
            destino = os.path.join(diretorio_saida, novo_nome)
            
            # Se for o mesmo arquivo (já está com o nome certo), apenas pula
            if os.path.abspath(caminho) == os.path.abspath(destino):
                print(f"[{os.path.basename(caminho)}] -> Nome já correto.")
                continue
                
            # Evitar sobrescrever: adiciona sufixo
            if os.path.exists(destino):
                base, ext = os.path.splitext(novo_nome)
                suf = 1
                while os.path.exists(os.path.join(diretorio_saida, f"{base}_{suf}{ext}")):
                    suf += 1
                destino = os.path.join(diretorio_saida, f"{base}_{suf}{ext}")

            os.rename(caminho, destino)
            print(f"[{os.path.basename(caminho)}] -> Renomeado para: {os.path.basename(destino)}")
        else:
            print(f"[{os.path.basename(caminho)}] -> Protocolo não encontrado; pulando.")

    print("Renomeação concluída.")


# ==============================================================================
# PONTO DE EXECUÇÃO
# ==============================================================================
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Separar requisições de um arquivo PDF em documentos individuais (Otimizado com PyMuPDF e Multiprocessing)."
    )
    parser.add_argument(
        "arquivo_entrada",
        nargs="?",
        default="lote_da_semana.pdf",
        help="Arquivo PDF de entrada (default: lote_da_semana.pdf)."
    )
    parser.add_argument(
        "-o",
        "--saida",
        default="documentos_separados",
        help="Diretório de saída onde os PDFs separados serão salvos."
    )
    parser.add_argument(
        "--marker",
        default=None,
        help="Se informado, separa o PDF sempre que a página contiver este marcador (ex: 'final final final final final')."
    )
    parser.add_argument(
        "--renomear",
        action="store_true",
        help="Renomeia arquivos em --saida usando OCR no canto superior direito da primeira página."
    )
    args = parser.parse_args()
    
    if args.renomear:
        try:
            renomear_por_ocr(args.saida)
        except Exception as e:
            print('Erro durante renomeação:', e)
        sys.exit(0)

    if os.path.exists(args.arquivo_entrada):
        if args.marker:
            separar_por_marcador(args.arquivo_entrada, marcador=args.marker, diretorio_saida=args.saida)
        else:
            processar_lote_requisicoes(args.arquivo_entrada, args.saida)
    else:
        print(f"Arquivo não encontrado: {args.arquivo_entrada}")
        print("Coloque o PDF na mesma pasta ou informe o caminho completo.")