import os
import sys
import threading
import customtkinter as ctk
from tkinter import filedialog, messagebox

# Importa as lógicas dos nossos scripts
import separar_por_marcador
import renomear_requisicoes

# Configuração do tema
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")


class PrintRedirector:
    """
    Classe para redirecionar o sys.stdout (os prints do terminal) 
    para o widget de texto do CustomTkinter.
    """
    def __init__(self, textbox):
        self.textbox = textbox

    def write(self, text):
        # Usar string_var.set ou insert funciona na maioria das vezes,
        # porém insert direto na textbox precisa estar habilitado.
        self.textbox.configure(state="normal")
        self.textbox.insert(ctk.END, text)
        self.textbox.see(ctk.END)
        self.textbox.configure(state="disabled")

    def flush(self):
        pass


class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Separador e Renomeador de Requisições")
        self.geometry("800x650")
        self.minsize(700, 600)

        # Configura o grid principal
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # TABVIEW
        self.tabview = ctk.CTkTabview(self)
        self.tabview.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="nsew")
        
        self.tab_separar = self.tabview.add("Separar PDFs")
        self.tab_renomear = self.tabview.add("Renomear PDFs")

        self.setup_separar_tab()
        self.setup_renomear_tab()

        # CONSOLE DE LOGS
        self.console_frame = ctk.CTkFrame(self)
        self.console_frame.grid(row=1, column=0, padx=20, pady=(10, 20), sticky="nsew")
        self.console_frame.grid_columnconfigure(0, weight=1)
        self.console_frame.grid_rowconfigure(1, weight=1)

        self.console_label = ctk.CTkLabel(self.console_frame, text="Log de Execução", font=("Roboto", 14, "bold"))
        self.console_label.grid(row=0, column=0, padx=10, pady=(10, 5), sticky="w")

        self.console_textbox = ctk.CTkTextbox(self.console_frame, wrap="word", font=("Consolas", 12))
        self.console_textbox.grid(row=1, column=0, padx=10, pady=(0, 10), sticky="nsew")
        self.console_textbox.configure(state="disabled")

        # Redireciona o print() para o console
        sys.stdout = PrintRedirector(self.console_textbox)


    def setup_separar_tab(self):
        self.tab_separar.grid_columnconfigure(1, weight=1)

        # Input Arquivo
        self.lbl_pdf_entrada = ctk.CTkLabel(self.tab_separar, text="PDF Unificado:")
        self.lbl_pdf_entrada.grid(row=0, column=0, padx=10, pady=(20, 10), sticky="e")
        
        self.var_pdf_entrada = ctk.StringVar(value=os.path.join(os.getcwd(), "requisicoes_unidas.pdf"))
        self.entry_pdf_entrada = ctk.CTkEntry(self.tab_separar, textvariable=self.var_pdf_entrada, state="disabled")
        self.entry_pdf_entrada.grid(row=0, column=1, padx=(0, 10), pady=(20, 10), sticky="ew")
        
        self.btn_procurar_pdf = ctk.CTkButton(self.tab_separar, text="Procurar", command=self.procurar_pdf)
        self.btn_procurar_pdf.grid(row=0, column=2, padx=(0, 10), pady=(20, 10))

        # Output Pasta
        self.lbl_pasta_saida = ctk.CTkLabel(self.tab_separar, text="Pasta de Saída:")
        self.lbl_pasta_saida.grid(row=1, column=0, padx=10, pady=10, sticky="e")
        
        self.var_pasta_saida = ctk.StringVar(value=os.path.join(os.getcwd(), "documentos_separados_marcador"))
        self.entry_pasta_saida = ctk.CTkEntry(self.tab_separar, textvariable=self.var_pasta_saida, state="disabled")
        self.entry_pasta_saida.grid(row=1, column=1, padx=(0, 10), pady=10, sticky="ew")
        
        self.btn_procurar_saida = ctk.CTkButton(self.tab_separar, text="Procurar", command=self.procurar_pasta_saida)
        self.btn_procurar_saida.grid(row=1, column=2, padx=(0, 10), pady=10)

        # Marcador
        self.lbl_marcador = ctk.CTkLabel(self.tab_separar, text="Marcador (Texto):")
        self.lbl_marcador.grid(row=2, column=0, padx=10, pady=10, sticky="e")
        
        self.var_marcador = ctk.StringVar(value="final final final final final")
        self.entry_marcador = ctk.CTkEntry(self.tab_separar, textvariable=self.var_marcador)
        self.entry_marcador.grid(row=2, column=1, columnspan=2, padx=(0, 10), pady=10, sticky="ew")

        # Botão Ação
        self.btn_separar = ctk.CTkButton(self.tab_separar, text="Iniciar Separação", fg_color="#2b9e4a", hover_color="#207a38", command=self.executar_separacao)
        self.btn_separar.grid(row=3, column=0, columnspan=3, padx=10, pady=(30, 10))

    def setup_renomear_tab(self):
        self.tab_renomear.grid_columnconfigure(1, weight=1)

        # Input Pasta
        self.lbl_pasta_renomear = ctk.CTkLabel(self.tab_renomear, text="Pasta com PDFs:")
        self.lbl_pasta_renomear.grid(row=0, column=0, padx=10, pady=(40, 10), sticky="e")
        
        self.var_pasta_renomear = ctk.StringVar(value=os.path.join(os.getcwd(), "documentos_separados_marcador"))
        self.entry_pasta_renomear = ctk.CTkEntry(self.tab_renomear, textvariable=self.var_pasta_renomear, state="disabled")
        self.entry_pasta_renomear.grid(row=0, column=1, padx=(0, 10), pady=(40, 10), sticky="ew")
        
        self.btn_procurar_renomear = ctk.CTkButton(self.tab_renomear, text="Procurar", command=self.procurar_pasta_renomear)
        self.btn_procurar_renomear.grid(row=0, column=2, padx=(0, 10), pady=(40, 10))

        # Botão Ação
        self.btn_renomear = ctk.CTkButton(self.tab_renomear, text="Iniciar Renomeação (OCR)", fg_color="#b86b1c", hover_color="#915211", command=self.executar_renomeacao)
        self.btn_renomear.grid(row=1, column=0, columnspan=3, padx=10, pady=(40, 10))


    # --- DIALOGS ---
    def procurar_pdf(self):
        arquivo = filedialog.askopenfilename(filetypes=[("PDF Files", "*.pdf")])
        if arquivo:
            self.var_pdf_entrada.set(arquivo)

    def procurar_pasta_saida(self):
        pasta = filedialog.askdirectory()
        if pasta:
            self.var_pasta_saida.set(pasta)

    def procurar_pasta_renomear(self):
        pasta = filedialog.askdirectory()
        if pasta:
            self.var_pasta_renomear.set(pasta)

    # --- EXECUÇÕES EM THREAD ---
    def executar_separacao(self):
        arq_entrada = self.var_pdf_entrada.get()
        dir_saida = self.var_pasta_saida.get()
        marcador = self.var_marcador.get()

        if not arq_entrada or not os.path.exists(arq_entrada):
            messagebox.showerror("Erro", "Selecione um arquivo PDF de entrada válido.")
            return

        self.btn_separar.configure(state="disabled", text="Processando...")
        print("\n" + "="*50)
        
        # Executa em uma thread separada para não congelar a UI
        thread = threading.Thread(target=self._thread_separacao, args=(arq_entrada, dir_saida, marcador))
        thread.daemon = True
        thread.start()

    def _thread_separacao(self, arq_entrada, dir_saida, marcador):
        try:
            separar_por_marcador.separar_lote(arq_entrada, dir_saida, marcador)
        except Exception as e:
            print(f"\n[ERRO FATAL] {e}")
        finally:
            self.btn_separar.configure(state="normal", text="Iniciar Separação")

    def executar_renomeacao(self):
        dir_alvo = self.var_pasta_renomear.get()

        if not dir_alvo or not os.path.exists(dir_alvo):
            messagebox.showerror("Erro", "Selecione uma pasta válida contendo os PDFs.")
            return

        self.btn_renomear.configure(state="disabled", text="Processando OCR...")
        print("\n" + "="*50)
        
        thread = threading.Thread(target=self._thread_renomeacao, args=(dir_alvo,))
        thread.daemon = True
        thread.start()

    def _thread_renomeacao(self, dir_alvo):
        try:
            renomear_requisicoes.renomear_lote(dir_alvo)
        except Exception as e:
            print(f"\n[ERRO FATAL] {e}")
        finally:
            self.btn_renomear.configure(state="normal", text="Iniciar Renomeação (OCR)")


if __name__ == "__main__":
    # Importante para o ProcessPoolExecutor no Windows quando usado fora do terminal
    import multiprocessing
    multiprocessing.freeze_support()
    
    app = App()
    app.mainloop()
