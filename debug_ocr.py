import os
import re
from pdf2image import convert_from_path
import pytesseract

CAMINHO_POPPLER = r'C:\Users\Luis\AppData\Local\Microsoft\WinGet\Packages\oschwartz10612.Poppler_Microsoft.Winget.Source_8wekyb3d8bbwe\poppler-25.07.0\Library\bin'

pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
local_tessdata = os.path.join(os.path.dirname(__file__), 'tessdata')
if os.path.isdir(local_tessdata):
    os.environ['TESSDATA_PREFIX'] = local_tessdata

imgs = convert_from_path('unido.pdf', dpi=200, poppler_path=CAMINHO_POPPLER)
print(f'pages: {len(imgs)}')
for i, img in enumerate(imgs[:5], 1):
    w, h = img.size
    top = img.crop((0, 0, w, int(h * 0.35)))
    txt = pytesseract.image_to_string(top, lang='por')
    print('--- page', i, '---')
    print(txt)
    print('MATCH PROTOCOLO:', bool(re.search(r'\b(I\d{4,6}/\d{2})\b', txt, re.IGNORECASE)))
    print('MATCH PORTARIA:', bool(re.search(r'PORTARIA.*?N[°ºO0.]?\s*\d{2,6}\s*[/.-]\s*\d{4}', txt, re.IGNORECASE)))
    print('---')
