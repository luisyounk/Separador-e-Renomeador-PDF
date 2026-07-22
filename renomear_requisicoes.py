import os
import re
import csv
import argparse
import fitz  # PyMuPDF
import pytesseract
from PIL import Image
from concurrent.futures import ProcessPoolExecutor, as_completed

# ============================================================================
# CONFIGURAÇÕES DE AMBIENTE (WINDOWS)
# ============================================================================
import sys
if getattr(sys, 'frozen', False):
    base_dir = os.path.dirname(sys.executable)
else:
    base_dir = os.path.dirname(os.path.abspath(__file__))

tess_path_local = os.path.join(base_dir, 'Tesseract-OCR', 'tesseract.exe')
if os.path.exists(tess_path_local):
    pytesseract.pytesseract.tesseract_cmd = tess_path_local
    tessdata_dir = os.path.join(base_dir, 'Tesseract-OCR', 'tessdata')
else:
    pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR	esseract.exe'
    tessdata_dir = r'C:\Program Files\Tesseract-OCR	essdata'

if os.path.isdir(tessdata_dir):
    os.environ['TESSDATA_PREFIX'] = tessdata_dir



def extrair_identificador_documento(texto_ocr):
    """
    Analisa o texto do OCR e busca exclusivamente pelo número do protocolo (I04XXX/26).
    Como o usuário garantiu que TODOS os arquivos são protocolos dessa série,
    podemos usar uma "bala de prata" que busca diretamente por 04XXX no texto limpo.
    """
    texto_limpo = re.sub(r"\s+", "", texto_ocr)
    texto_limpo = texto_limpo.replace("04236548000196", "") # Filtra o CNPJ da Polícia Civil
    
    # Limpa o número de Processo Judicial (ex: 1502632-61) que pode conter um "0XXXX" no meio
    texto_limpo = re.sub(r"\d{7}[-.,_]\d{2}", "", texto_limpo)
    
    # BALA DE PRATA DEFINITIVA (Block Validation):
    # Procura blocos contíguos de dígitos para evitar pegar pedaços de números maiores (ex: 02632 dentro de 202632)
    for match in re.finditer(r"(\d+)(?:[/.\-Il1,|]+(25|26))?", texto_limpo):
        bloco = match.group(1)
        ano_encontrado = match.group(2)
        
        candidato = bloco
        # Ex: 2604521 -> 04521 (Ano grudado na frente)
        if len(candidato) == 7 and candidato.startswith(("25", "26")):
            candidato = candidato[2:]
        # Ex: 26104521 -> 104521 -> 04521 (Ano + '1' grudados na frente)
        elif len(candidato) == 8 and (candidato.startswith("251") or candidato.startswith("261")):
            candidato = candidato[3:]
        # Ex: 104484 -> 04484 (Letra I lida como 1)
        elif len(candidato) == 6 and candidato.startswith("1"):
            candidato = candidato[1:]
            
        if len(candidato) == 5 and candidato.startswith("0"):
            ano = ano_encontrado if ano_encontrado else "26"
            return f"I{candidato}_{ano}"

    return None


def processar_arquivo_renomear(caminho):
    """
    Lê a primeira página de um PDF, tenta extrair o protocolo por múltiplas abordagens 
    e retorna o novo nome sugerido.
    """
    try:
        doc = fitz.open(caminho)
        pagina = doc[0]
        protocolo = None
        
        # 1ª Tentativa: Texto puro embutido no PDF (Instantâneo)
        texto = pagina.get_text() or ""
        protocolo = extrair_identificador_documento(texto)
        
        # 2ª Tentativa: OCR focado no Topo da página (DPI 200)
        if not protocolo:
            w, h = pagina.rect.width, pagina.rect.height
            clip_rect = fitz.Rect(0, 0, w, h * 0.5) 
            pix = pagina.get_pixmap(dpi=200, clip=clip_rect)
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            texto_ocr_topo = pytesseract.image_to_string(img, lang='por')
            protocolo = extrair_identificador_documento(texto_ocr_topo)
            
        # 3ª Tentativa: OCR focado no Topo da página (DPI 300 - para carimbos fracos)
        if not protocolo:
            pix = pagina.get_pixmap(dpi=300, clip=clip_rect)
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            texto_ocr_topo_300 = pytesseract.image_to_string(img, lang='por')
            protocolo = extrair_identificador_documento(texto_ocr_topo_300)
            
        # 4ª Tentativa: OCR da página inteira (DPI 200)
        if not protocolo:
            pix = pagina.get_pixmap(dpi=200) 
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            texto_ocr_full = pytesseract.image_to_string(img, lang='por')
            protocolo = extrair_identificador_documento(texto_ocr_full)
            
        # 5ª Tentativa: OCR da página inteira (DPI 300)
        if not protocolo:
            pix = pagina.get_pixmap(dpi=300) 
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            texto_ocr_full_300 = pytesseract.image_to_string(img, lang='por')
            protocolo = extrair_identificador_documento(texto_ocr_full_300)
            
        doc.close()
        return caminho, protocolo
    except Exception as e:
        return caminho, None


def comprimir_pdf_se_necessario(caminho_arquivo, max_mb=14.0):
    tamanho_mb = os.path.getsize(caminho_arquivo) / (1024 * 1024)
    if tamanho_mb <= max_mb:
        return
        
    print(f"[{os.path.basename(caminho_arquivo)}] Tamanho original: {tamanho_mb:.2f}MB > limite de {max_mb}MB. Reduzindo qualidade...")
    try:
        caminho_temp = caminho_arquivo + ".tmp"
        doc = fitz.open(caminho_arquivo)
        
        # Itera sobre todas as imagens de todas as páginas para reduzir qualidade
        for page in doc:
            for img in page.get_images():
                xref = img[0]
                pix = fitz.Pixmap(doc, xref)
                # Garante que a imagem está em RGB sem transparência para virar JPEG
                if pix.n >= 4 or pix.alpha:
                    pix = fitz.Pixmap(fitz.csRGB if pix.n >= 3 else fitz.csGray, pix)
                
                # Determina o colorspace correto para o JPEG (RGB ou Gray)
                cspace = "/DeviceRGB" if pix.n >= 3 else "/DeviceGray"
                
                # Salva a imagem em qualidade JPEG 40 para garantir a redução do tamanho
                img_data = pix.tobytes("jpeg", 40)
                
                # Atualiza a stream SEM adicionar compressão ZLIB dupla
                doc.update_stream(xref, img_data, compress=0)
                
                # Atualiza o dicionário do PDF para que o leitor saiba que agora é um JPEG (DCTDecode)
                obj = f"<< /Type /XObject /Subtype /Image /Width {pix.width} /Height {pix.height} /ColorSpace {cspace} /BitsPerComponent 8 /Filter /DCTDecode >>"
                doc.update_object(xref, obj)
                
        # Salva o PDF com otimização (garbage collection e deflate)
        doc.save(caminho_temp, garbage=4, deflate=True)
        doc.close()
        
        # Substitui o arquivo original pelo comprimido
        os.remove(caminho_arquivo)
        os.rename(caminho_temp, caminho_arquivo)
        
        novo_tamanho = os.path.getsize(caminho_arquivo) / (1024 * 1024)
        print(f"[{os.path.basename(caminho_arquivo)}] Compressão finalizada! Novo tamanho: {novo_tamanho:.2f}MB")
    except Exception as e:
        print(f"[{os.path.basename(caminho_arquivo)}] Erro ao comprimir: {e}")

def renomear_lote(diretorio):
    if not os.path.isdir(diretorio):
        print(f"Erro: Diretório '{diretorio}' não encontrado.")
        return

    arquivos = sorted([f for f in os.listdir(diretorio) if f.lower().endswith('.pdf')])
    
    # MELHORIA 1: Filtro de Inteligência
    # Evita reprocessar arquivos que já possuem nome de protocolo válido (ex: I1234_26.pdf)
    arquivos_pendentes = []
    for f in arquivos:
        if not re.match(r"^(REQ_|BO_|I|PORTARIA_)\d+_\d+", f, re.IGNORECASE):
            arquivos_pendentes.append(f)
            
    total = len(arquivos_pendentes)
    if total == 0:
        print("Nenhum arquivo pendente precisando ser renomeado na pasta.")
        return

    print(f"Iniciando análise de OCR em {total} arquivos (multiprocessamento)...")
    caminhos = [os.path.join(diretorio, f) for f in arquivos_pendentes]
    
    resultados = []
    with ProcessPoolExecutor() as executor:
        futures = {executor.submit(processar_arquivo_renomear, caminho): caminho for caminho in caminhos}
        for count, future in enumerate(as_completed(futures), 1):
            resultados.append(future.result())
            # Imprime progresso na mesma linha (clean output)
            print(f"  > Analisado: {count}/{total} arquivos", end="\r")
            
    print("\n\nAplicando os novos nomes...\n")
    
    # MELHORIA 2: Auditoria e Log de Ações
    # Cria um relatório para você saber exatamente o que virou o que.
    log_file = os.path.join(diretorio, "relatorio_renomeacao.csv")
    
    with open(log_file, "w", newline='', encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["Arquivo Original", "Novo Arquivo", "Status"])
        
        for caminho, protocolo in resultados:
            nome_original = os.path.basename(caminho)
            
            if protocolo:
                novo_nome = f"{protocolo}.pdf"
                destino = os.path.join(diretorio, novo_nome)
                
                # MELHORIA 3: Prevenção de conflito
                # Se já existe um arquivo com esse nome (ex: 2 requerimentos do mesmo B.O.)
                if os.path.exists(destino) and os.path.abspath(caminho) != os.path.abspath(destino):
                    base, ext = os.path.splitext(novo_nome)
                    suf = 1
                    while os.path.exists(os.path.join(diretorio, f"{base}_{suf}{ext}")):
                        suf += 1
                    destino = os.path.join(diretorio, f"{base}_{suf}{ext}")

                try:
                    os.rename(caminho, destino)
                    nome_final = os.path.basename(destino)
                    print(f"[OK] {nome_original}  -->  {nome_final}")
                    
                    # Reduz a qualidade se o arquivo for maior que 14MB
                    comprimir_pdf_se_necessario(destino, max_mb=14.0)
                    
                    writer.writerow([nome_original, nome_final, "RENOMEADO"])
                except Exception as e:
                    print(f"[ERRO] Falha ao renomear {nome_original}: {e}")
                    writer.writerow([nome_original, "", f"ERRO: {e}"])
            else:
                print(f"[FALHA] {nome_original}  -->  (Protocolo não encontrado)")
                writer.writerow([nome_original, "", "NAO ENCONTRADO"])

    print(f"\nProcesso concluído! Relatório completo salvo em: {log_file}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Analisa a 1ª página de arquivos PDF e os renomeia com base no protocolo encontrado.")
    parser.add_argument("diretorio", nargs="?", default="documentos_separados", help="Pasta contendo os PDFs a serem renomeados.")
    
    args = parser.parse_args()
    renomear_lote(args.diretorio)
