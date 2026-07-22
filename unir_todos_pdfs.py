import os
from pathlib import Path
from pypdf import PdfReader, PdfWriter


def unir_todos_pdfs(diretorio='.'):
    pdfs = sorted([p for p in Path(diretorio).glob('*.pdf') if p.name.lower() != 'unido.pdf'])
    if not pdfs:
        print('Nenhum arquivo PDF encontrado no diretório atual.')
        return

    escritor = PdfWriter()
    for caminho_pdf in pdfs:
        print(f'Adicionando: {caminho_pdf.name}')
        leitor = PdfReader(caminho_pdf)
        for pagina in leitor.pages:
            escritor.add_page(pagina)

    arquivo_saida = Path(diretorio) / 'unido.pdf'
    with open(arquivo_saida, 'wb') as f:
        escritor.write(f)

    print(f'PDFs unidos com sucesso em: {arquivo_saida.name}')


if __name__ == '__main__':
    unir_todos_pdfs('.')
