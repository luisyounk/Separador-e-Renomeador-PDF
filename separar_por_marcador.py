import os
import re
import argparse
import fitz  # PyMuPDF
import pytesseract
from PIL import Image
from concurrent.futures import ProcessPoolExecutor, as_completed

# ============================================================================
# CONFIGURAÇÕES DO TESSERACT (Para OCR caso o PDF seja imagem)
# ============================================================================
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

tessdata_padrao = r'C:\Program Files\Tesseract-OCR\tessdata'
tessdata_local = os.path.join(os.path.dirname(__file__), 'tessdata')
TESSDATA_DIR = None
if os.path.isdir(tessdata_local):
    TESSDATA_DIR = tessdata_local
elif os.path.isdir(tessdata_padrao):
    TESSDATA_DIR = tessdata_padrao

if TESSDATA_DIR:
    os.environ['TESSDATA_PREFIX'] = TESSDATA_DIR
else:
    print('Aviso: tessdata não encontrado. A OCR pode falhar se o idioma não estiver instalado.')


def analisar_pagina_marcador(pdf_bytes, num_pagina, marcador_norm):
    """
    Lê a página de forma independente via Multiprocessamento.
    Verifica se a página está em branco ou se contém o marcador exato.
    """
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    pagina = doc[num_pagina]
    
    # Tenta ler o texto diretamente do PDF
    texto = pagina.get_text() or ""
    texto_norm = re.sub(r"\s+", " ", texto.strip().lower())
    
    if not texto_norm:
        # Se não há texto selecionável, apela para o OCR (lento, mas necessário para scans)
        pix = pagina.get_pixmap(dpi=200)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        texto = pytesseract.image_to_string(img, lang='por') or ""
        texto_norm = re.sub(r"\s+", " ", texto.strip().lower())
        
    is_blank = not texto_norm
    has_marker = marcador_norm in texto_norm
    doc.close()
    
    return {
        "num_pagina": num_pagina,
        "is_blank": is_blank,
        "has_marker": has_marker
    }


def separar_lote(caminho_entrada, diretorio_saida, marcador):
    if not os.path.exists(diretorio_saida):
        os.makedirs(diretorio_saida)
    
    # Normaliza o marcador removendo espaços extras e deixando em minúsculo
    marcador_norm = re.sub(r"\s+", " ", marcador.strip().lower())
    print(f"Iniciando separação por marcador '{marcador}' no arquivo: {caminho_entrada}")
    
    # Carrega todo o PDF em bytes para a RAM (agiliza o multiprocessamento)
    with open(caminho_entrada, "rb") as f:
        pdf_bytes = f.read()
        
    doc_original = fitz.open(stream=pdf_bytes, filetype="pdf")
    total_paginas = len(doc_original)
    
    print(f"Analisando as {total_paginas} páginas com multiprocessamento...")
    
    resultados_paginas = [None] * total_paginas
    
    with ProcessPoolExecutor() as executor:
        futures = {executor.submit(analisar_pagina_marcador, pdf_bytes, i, marcador_norm): i for i in range(total_paginas)}
        for count, future in enumerate(as_completed(futures), 1):
            res = future.result()
            resultados_paginas[res["num_pagina"]] = res
            # Imprime progresso a cada 10 páginas para não poluir muito o terminal
            if count % 10 == 0 or count == total_paginas:
                print(f"  > Progresso da análise: {count}/{total_paginas} páginas")
    
    print("\nMontando os novos documentos fatiados...")
    
    doc_atual = fitz.open()
    parte_idx = 1
    
    for res in resultados_paginas:
        # Ignora páginas sumariamente brancas
        if res["is_blank"]:
            continue
            
        # Se for o marcador, salva o que acumulou até agora e zera o documento
        if res["has_marker"]:
            if len(doc_atual) > 0:
                nome_saida = os.path.join(diretorio_saida, f"parte_{parte_idx:03d}.pdf")
                doc_atual.save(nome_saida)
                print(f" -> Salvo: {nome_saida}")
                doc_atual.close()
                doc_atual = fitz.open()
                parte_idx += 1
            continue
            
        # Adiciona a página normal ao documento
        doc_atual.insert_pdf(doc_original, from_page=res["num_pagina"], to_page=res["num_pagina"])
        
    # Salva as páginas finais que ficaram acumuladas sem marcador no final
    if len(doc_atual) > 0:
        nome_saida = os.path.join(diretorio_saida, f"parte_{parte_idx:03d}.pdf")
        doc_atual.save(nome_saida)
        print(f" -> Salvo: {nome_saida}")
        doc_atual.close()
        
    doc_original.close()
    print("Sucesso! Separação por marcador concluída.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Separa um arquivo PDF longo usando uma página marcadora de texto.")
    parser.add_argument("arquivo_entrada", help="Caminho do arquivo PDF de entrada.")
    parser.add_argument("-m", "--marcador", default="final final final final final", help="O texto exato na página que indica onde cortar (default: 5 'final').")
    parser.add_argument("-o", "--saida", default="documentos_separados", help="Diretório onde os arquivos fatiados serão salvos.")
    
    args = parser.parse_args()
    
    if os.path.exists(args.arquivo_entrada):
        separar_lote(args.arquivo_entrada, args.saida, args.marcador)
    else:
        print(f"Erro: Arquivo '{args.arquivo_entrada}' não encontrado.")
