import os
import sys
from pypdf import PdfReader, PdfWriter


def unir_pdfs(arquivos_entrada, arquivo_saida):
    """Une vários arquivos PDF em um único PDF de saída."""
    escritor = PdfWriter()

    for caminho in arquivos_entrada:
        if not os.path.exists(caminho):
            raise FileNotFoundError(f"Arquivo não encontrado: {caminho}")

        leitor = PdfReader(caminho)
        for pagina in leitor.pages:
            escritor.add_page(pagina)

    with open(arquivo_saida, "wb") as f:
        escritor.write(f)

    print(f"PDFs unidos com sucesso em: {arquivo_saida}")


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Uso: python unir_pdfs.py saida.pdf entrada1.pdf entrada2.pdf [...]")
        sys.exit(1)

    arquivo_saida = sys.argv[1]
    arquivos_entrada = sys.argv[2:]
    unir_pdfs(arquivos_entrada, arquivo_saida)
