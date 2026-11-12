"""Gera o Manual_MARX_SECRET.pdf (manual de instalação e utilização).

Uso: python tools/make_manual.py [arquivo_saida.pdf]
As capturas de tela vêm de docs/screenshots (geradas por tools/make_screenshots.py).
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from reportlab.lib import colors  # noqa: E402
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY  # noqa: E402
from reportlab.lib.pagesizes import A4  # noqa: E402
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet  # noqa: E402
from reportlab.lib.units import mm  # noqa: E402
from reportlab.platypus import (  # noqa: E402
    BaseDocTemplate,
    Frame,
    Image,
    KeepTogether,
    NextPageTemplate,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.platypus.tableofcontents import TableOfContents  # noqa: E402

from marx_secret import APP_COMMERCIAL_NAME, APP_NAME, APP_SLOGAN, __version__  # noqa: E402
from marx_secret.reports.pdf_report import (  # noqa: E402
    BLACK,
    EMERALD,
    EMERALD_DARK,
    GRAPHITE,
    LIGHT_ROW,
    MUTED,
    draw_logo,
)

SHOTS = ROOT / "docs" / "screenshots"

ss = getSampleStyleSheet()
H1 = ParagraphStyle("H1", parent=ss["Heading1"], fontSize=18, textColor=GRAPHITE, spaceBefore=4,
                    spaceAfter=8, keepWithNext=1)
H2 = ParagraphStyle("H2", parent=ss["Heading2"], fontSize=12.5, textColor=EMERALD_DARK,
                    spaceBefore=10, spaceAfter=4, keepWithNext=1)
BODY = ParagraphStyle("Body", parent=ss["BodyText"], fontSize=10, leading=14.5,
                      alignment=TA_JUSTIFY, spaceAfter=5)
BULLET = ParagraphStyle("Bullet", parent=BODY, leftIndent=14, bulletIndent=4, spaceAfter=2)
NOTE = ParagraphStyle("Note", parent=BODY, fontSize=9, textColor=colors.HexColor("#064E3B"),
                      backColor=colors.HexColor("#ECFDF5"), borderColor=EMERALD, borderWidth=0.6,
                      borderPadding=7, spaceBefore=6, spaceAfter=10, alignment=0)
WARN = ParagraphStyle("Warn", parent=NOTE, textColor=colors.HexColor("#7C2D12"),
                      backColor=colors.HexColor("#FFF7ED"), borderColor=colors.HexColor("#F59E0B"))
CAPTION = ParagraphStyle("Caption", parent=BODY, fontSize=8, textColor=MUTED,
                         alignment=TA_CENTER, spaceAfter=10)
CODE = ParagraphStyle("Code", parent=BODY, fontName="Courier", fontSize=8.5, leading=11,
                      backColor=colors.HexColor("#F1F5F3"), borderPadding=6, spaceBefore=4,
                      spaceAfter=8, alignment=0)


class ManualDoc(BaseDocTemplate):
    def __init__(self, filename: str):
        super().__init__(filename, pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm,
                         topMargin=26 * mm, bottomMargin=20 * mm,
                         title=f"Manual do {APP_NAME}", author=APP_NAME,
                         subject="Manual de instalação e utilização", creator=APP_COMMERCIAL_NAME)
        frame = Frame(self.leftMargin, self.bottomMargin, self.width, self.height, id="f")
        self.addPageTemplates([
            PageTemplate("capa", [frame], onPage=self._cover),
            PageTemplate("conteudo", [frame], onPage=self._page),
        ])

    def afterFlowable(self, flowable):  # noqa: N802
        if isinstance(flowable, Paragraph) and flowable.style.name in ("H1", "H2"):
            level = 0 if flowable.style.name == "H1" else 1
            text = flowable.getPlainText()
            key = f"h{id(flowable)}"
            self.canv.bookmarkPage(key)
            self.canv.addOutlineEntry(text, key, level=level, closed=level > 0)
            self.notify("TOCEntry", (level, text, self.page, key))

    @staticmethod
    def _cover(c, doc):
        w, h = A4
        c.saveState()
        c.setFillColor(BLACK)
        c.rect(0, 0, w, h, fill=1, stroke=0)
        c.setFillColor(colors.HexColor("#0C2A20"))
        for x in range(0, int(w), 24):
            for y in range(0, int(h), 24):
                central = 40 * mm < x < w - 40 * mm and 90 * mm < y < 125 * mm
                if (x * 7 + y * 13) % 5 == 0 and not central:
                    c.rect(x, y, 6, 6, fill=1, stroke=0)
        draw_logo(c, w / 2 - 45 * mm, h - 125 * mm, 90 * mm)
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 38)
        c.drawCentredString(w / 2, h - 148 * mm, APP_NAME)
        c.setFillColor(EMERALD)
        c.setFont("Helvetica-Bold", 12)
        c.drawCentredString(w / 2, h - 158 * mm, APP_SLOGAN)
        c.setFillColor(colors.white)
        c.setFont("Helvetica", 16)
        c.drawCentredString(w / 2, h - 185 * mm, "Manual de Instalação e Utilização")
        c.setFillColor(colors.HexColor("#9CA3AF"))
        c.setFont("Helvetica", 10)
        c.drawCentredString(w / 2, h - 194 * mm,
                            f"{APP_COMMERCIAL_NAME} · versão {__version__} · Windows 10 e 11 (64 bits)")
        c.drawCentredString(w / 2, 20 * mm, "Professional Steganography Suite")
        c.restoreState()

    @staticmethod
    def _page(c, doc):
        w, h = A4
        c.saveState()
        c.setFillColor(BLACK)
        c.rect(0, h - 16 * mm, w, 16 * mm, fill=1, stroke=0)
        c.setFillColor(EMERALD)
        c.rect(0, h - 16.6 * mm, w, 0.6 * mm, fill=1, stroke=0)
        draw_logo(c, 14 * mm, h - 14 * mm, 12 * mm)
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 11)
        c.drawString(28 * mm, h - 9.5 * mm, APP_NAME)
        c.setFont("Helvetica", 8)
        c.setFillColor(colors.HexColor("#9CA3AF"))
        c.drawRightString(w - 14 * mm, h - 9.5 * mm, "Manual de Instalação e Utilização")
        c.setFillColor(MUTED)
        c.drawString(20 * mm, 10 * mm, f"{APP_COMMERCIAL_NAME} v{__version__}")
        c.drawRightString(w - 20 * mm, 10 * mm, f"Página {doc.page}")
        c.restoreState()


def P(text: str, style=BODY) -> Paragraph:
    return Paragraph(text, style)


def bullets(items: list[str]) -> list[Paragraph]:
    return [Paragraph(i, BULLET, bulletText="•") for i in items]


def steps(items: list[str]) -> list[Paragraph]:
    return [Paragraph(i, BULLET, bulletText=f"{n}.") for n, i in enumerate(items, 1)]


def shot(name: str, caption: str, width_mm: float = 170) -> list:
    path = SHOTS / f"{name}.png"
    if not path.exists():
        return [P(f"<i>[captura {name} indisponível]</i>", CAPTION)]
    from PIL import Image as PILImage

    with PILImage.open(path) as im:
        ratio = im.height / im.width
    w = width_mm * mm
    return [KeepTogether([Image(str(path), width=w, height=w * ratio), P(caption, CAPTION)])]


_CELL = ParagraphStyle("c", parent=BODY, fontSize=8.5, leading=11, alignment=0)
_HEAD = ParagraphStyle("hc", parent=_CELL, textColor=colors.white, fontName="Helvetica-Bold")


def table(rows: list[list[str]], widths: list[float]) -> Table:
    data = [[Paragraph(str(c), _HEAD if i == 0 else _CELL) for c in r]
            for i, r in enumerate(rows)]
    t = Table(data, colWidths=[w * mm for w in widths], repeatRows=1)
    st = [("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#C9D1CD")),
          ("BACKGROUND", (0, 0), (-1, 0), GRAPHITE),
          ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
          ("VALIGN", (0, 0), (-1, -1), "TOP")]
    for i in range(2, len(rows), 2):
        st.append(("BACKGROUND", (0, i), (-1, i), LIGHT_ROW))
    t.setStyle(TableStyle(st))
    return t


def build_story() -> list:
    s: list = [NextPageTemplate("conteudo"), PageBreak()]
    toc = TableOfContents()
    toc.levelStyles = [
        ParagraphStyle("t0", fontName="Helvetica-Bold", fontSize=10.5, leading=16),
        ParagraphStyle("t1", fontName="Helvetica", fontSize=9, leading=12, leftIndent=14,
                       textColor=MUTED),
    ]
    s += [P("Sumário", ParagraphStyle("TocTitle", parent=H1)), toc, PageBreak()]

    # 1
    s += [P("1. Apresentação", H1),
          P(f"O <b>{APP_NAME}</b> é um software profissional de esteganografia digital, "
            "criptografia, ocultação e recuperação de mensagens e arquivos em imagens. Ele permite "
            "esconder informações dentro dos pixels de uma imagem de forma imperceptível ao olho "
            "humano, protegendo-as com criptografia de nível militar (AES-256-GCM) e senha."),
          P("Principais recursos:")]
    s += bullets([
        "Ocultação e extração de <b>mensagens de texto</b> em imagens.",
        "Ocultação e recuperação de <b>arquivos de qualquer tipo</b> (PDF, planilhas, ZIP…).",
        "Criptografia <b>AES-256-GCM</b> com chave derivada por <b>Argon2id</b>.",
        "Verificação de integridade <b>SHA-256</b> em toda recuperação.",
        "Distribuição <b>dispersa</b> dos bits guiada pela senha (dificulta a detecção).",
        "<b>Análise estatística</b> (histogramas, entropia, ataque qui-quadrado, plano LSB).",
        "<b>Comparação</b> entre imagem original e processada (PSNR, SSIM, MSE, mapa de diferenças).",
        "<b>Histórico</b> local de operações e <b>relatórios técnicos</b> em PDF e CSV.",
        "<b>Gerenciamento de arquivos</b> com exclusão segura e verificação de hashes.",
        "Criptografia independente de arquivos (<b>.mxs</b>) e gerador de senhas fortes.",
        "Funcionamento <b>100% local e offline</b>: nada é enviado à internet.",
    ])
    s += shot("00_abertura", "Tela de abertura do MARX SECRET", 120)

    # 2
    s += [PageBreak(), P("2. Requisitos do sistema", H1),
          table([["Item", "Requisito"],
                 ["Sistema operacional", "Windows 10 (versão 1809 ou superior) ou Windows 11, 64 bits"],
                 ["Processador", "x64, 2 núcleos ou mais"],
                 ["Memória", "4 GB de RAM (8 GB recomendados para imagens grandes)"],
                 ["Espaço em disco", "cerca de 250 MB"],
                 ["Tela", "resolução mínima de 1280 × 720"],
                 ["Internet", "não é necessária (funcionamento totalmente offline)"],
                 ["Dependências", "nenhuma: Python e bibliotecas já estão incluídos"]],
                [45, 125])]

    # 3
    s += [P("3. Formas de distribuição", H1),
          P("O MARX SECRET é distribuído em quatro pacotes:"),
          table([["Pacote", "Arquivo", "Uso"],
                 ["Marx Secret - Instalação tradicional no Windows", "MARX_SECRET_Setup.exe",
                  "Instala o programa, cria atalhos e permite desinstalação completa."],
                 ["Marx Secret - Executar sem instalação tradicional", "MARX_SECRET_Portable.zip",
                  "Versão portátil: basta extrair e executar (inclusive em pendrive)."],
                 ["Marx Secret - Projeto completo e código-fonte", "MARX_SECRET_Source.zip",
                  "Código-fonte, testes, scripts de build e documentação técnica."],
                 ["Marx Secret - Manual de instalação e utilização", "Manual_MARX_SECRET.pdf",
                  "Este manual."]], [62, 46, 62])]

    # 4
    s += [P("4. Instalação tradicional (MARX_SECRET_Setup.exe)", H1)]
    s += steps([
        "Execute <b>MARX_SECRET_Setup.exe</b>. Se o Windows SmartScreen exibir um aviso, clique em "
        "<b>Mais informações</b> e depois em <b>Executar assim mesmo</b> (o aviso ocorre com "
        "executáveis ainda sem assinatura digital comercial).",
        "Escolha se deseja instalar <b>para todos os usuários</b> (requer administrador) ou "
        "<b>somente para você</b>.",
        "Leia e aceite os <b>Termos de Uso</b>.",
        "Escolha o <b>diretório de instalação</b> (padrão: <i>C:\\Program Files\\MARX SECRET</i>).",
        "Escolha a pasta do <b>Menu Iniciar</b>.",
        "Mantenha marcada a opção <b>Criar um atalho na Área de Trabalho</b>.",
        "Clique em <b>Instalar</b> e, ao final, em <b>Concluir</b> para abrir o programa.",
    ])
    s += [P("Atalhos criados: <b>Menu Iniciar › MARX SECRET</b> (programa, manual e desinstalador) e "
            "<b>Área de Trabalho › MARX SECRET</b>.", NOTE),
          P("Instalação silenciosa (para administradores de TI):", H2),
          P("MARX_SECRET_Setup.exe /VERYSILENT /SUPPRESSMSGBOXES /DIR=\"C:\\Apps\\MARX SECRET\" "
            "/TASKS=desktopicon", CODE)]

    # 5
    s += [P("5. Execução sem instalação (versão portátil)", H1)]
    s += steps([
        "Extraia <b>MARX_SECRET_Portable.zip</b> para qualquer pasta ou pendrive "
        "(clique com o botão direito › <b>Extrair tudo…</b>).",
        "Abra a pasta extraída e execute <b>MARX_SECRET.exe</b>.",
    ])
    s += [P("Na versão portátil, o arquivo <b>portable.flag</b> faz com que todos os dados "
            "(histórico, configurações e banco de dados) fiquem na subpasta <b>dados</b>, e as "
            "imagens geradas na subpasta <b>saida</b>, ao lado do executável. Nada é gravado no "
            "registro do Windows nem na pasta do usuário.", NOTE)]

    # 6
    s += [P("6. Primeiros passos e navegação", H1),
          P("A janela principal possui uma barra lateral com os módulos agrupados em "
            "<b>Visão geral</b>, <b>Esteganografia</b>, <b>Proteção</b>, <b>Inteligência</b>, "
            "<b>Gestão</b> e <b>Sistema</b>. Atalhos de teclado: <b>Ctrl+1</b> (Dashboard) até "
            "<b>Ctrl+9</b> (Histórico), na ordem da barra lateral."),
          P("Todas as telas de seleção de imagem aceitam <b>arrastar e soltar</b>.")]
    s += [P("6.1 Dashboard", H2),
          P("Mostra indicadores (operações, ocultações, extrações e taxa de sucesso), a atividade "
            "dos últimos 7 dias, o estado de segurança e as operações recentes, além de atalhos "
            "rápidos para as funções principais.")]
    s += shot("01_dashboard", "Dashboard (tema escuro)")

    # 7
    s += [PageBreak(), P("7. Ocultar mensagem", H1)]
    s += steps([
        "Selecione (ou arraste) a <b>imagem portadora</b>. Formatos aceitos: PNG, BMP, TIFF, JPEG, "
        "WEBP e GIF.",
        "Digite a <b>mensagem</b>.",
        "Informe e confirme a <b>senha</b> (o botão de dado gera uma senha forte). O medidor indica "
        "a força da senha.",
        "Escolha a <b>densidade</b> (1, 2 ou 3 bits por canal), a <b>distribuição dispersa</b> e a "
        "<b>compressão</b>.",
        "Confira o <b>arquivo de saída</b> (sugerido automaticamente) e a barra de "
        "<b>uso da capacidade</b>.",
        "Clique em <b>Ocultar mensagem</b>.",
    ])
    s += [P("A imagem de saída é sempre gravada em formato <b>sem perdas</b> (PNG, BMP ou TIFF). "
            "Após a gravação, o MARX SECRET relê o arquivo e confirma que o conteúdo pode ser "
            "recuperado (verificação pós-gravação).", NOTE)]
    s += shot("02_ocultar_mensagem", "Ocultar mensagem")
    s += [table([["Densidade", "Capacidade", "Discrição"],
                 ["1 bit/canal", "0,375 byte por pixel (ex.: 1920×1080 = aprox. 759 KB)", "Máxima"],
                 ["2 bits/canal", "dobro da anterior (aprox. 1,5 MB em Full HD)", "Alta"],
                 ["3 bits/canal", "triplo (aprox. 2,2 MB em Full HD)", "Moderada"]], [32, 98, 40])]

    # 8
    s += [PageBreak(), P("8. Extrair mensagem", H1)]
    s += steps([
        "Selecione a imagem que contém a mensagem. Um selo informa se a assinatura MARX SECRET "
        "foi detectada, o tamanho do conteúdo e se a distribuição é dispersa.",
        "Digite a senha e clique em <b>Extrair mensagem</b> (ou tecle Enter).",
        "A mensagem é exibida após a verificação de autenticidade (AES-GCM) e integridade "
        "(SHA-256). Use <b>Copiar</b>, <b>Salvar como .txt</b> ou <b>Limpar da tela</b>.",
    ])
    s += [P("Por segurança, a área de transferência é limpa automaticamente após o tempo definido "
            "em Configurações (padrão: 30 segundos).", NOTE)]
    s += shot("03_extrair_mensagem", "Extrair mensagem")

    # 9-10
    s += [PageBreak(), P("9. Ocultar arquivo", H1),
          P("Funciona como a ocultação de mensagens, mas o conteúdo é um arquivo. O nome original "
            "do arquivo é preservado (dentro do conteúdo criptografado) para a recuperação. "
            "O limite padrão é de 64 MB por arquivo (configurável até 256 MB), sujeito à capacidade "
            "da imagem.")]
    s += shot("04_ocultar_arquivo", "Ocultar arquivo")
    s += [P("10. Recuperar arquivo", H1)]
    s += steps([
        "Selecione a imagem e informe a senha.",
        "Clique em <b>Recuperar arquivo</b>; nome, tamanho e SHA-256 são exibidos.",
        "Escolha a pasta de destino e clique em <b>Salvar arquivo</b>. Arquivos existentes "
        "nunca são sobrescritos: um sufixo numérico é adicionado.",
    ])
    s += shot("05_recuperar_arquivo", "Recuperar arquivo")

    # 11
    s += [PageBreak(), P("11. Criptografia e senhas", H1),
          P("Este módulo oferece quatro ferramentas:")]
    s += bullets([
        "<b>Criptografar arquivo</b>: gera um arquivo <b>.mxs</b> protegido com AES-256-GCM. "
        "Opcionalmente, exclui o original com segurança.",
        "<b>Descriptografar arquivo</b>: restaura o arquivo original a partir do .mxs, com "
        "verificação SHA-256.",
        "<b>Gerador de senhas</b>: cria senhas fortes (8 a 128 caracteres) com o gerador "
        "criptográfico do sistema e avalia senhas existentes.",
        "<b>Hash SHA-256</b>: calcula o hash de um arquivo e compara com um valor esperado.",
    ])
    s += shot("06_criptografia", "Criptografia e senhas")

    # 12-13
    s += [PageBreak(), P("12. Análise estatística", H1),
          P("Analisa qualquer imagem sem descriptografar conteúdo. São exibidos: dimensões, "
            "formato, SHA-256, capacidade, estatísticas por canal (média, desvio padrão, entropia, "
            "proporção de bits LSB), histograma RGB, <b>ataque qui-quadrado</b> global e sequencial, "
            "<b>plano de bits LSB</b> e a detecção da assinatura MARX SECRET. O diagnóstico "
            "classifica a suspeita como <b>Baixa</b>, <b>Moderada</b> ou <b>Alta</b>. "
            "Os resultados podem ser exportados em PDF e CSV.")]
    s += shot("07_analise", "Análise estatística")
    s += [P("13. Comparação de imagens", H1),
          P("Compara a imagem original com a processada e calcula PSNR, SSIM, MSE (global e por "
            "canal), pixels e valores alterados e diferença máxima/média, além de exibir um "
            "<b>mapa de diferenças</b> amplificado. Valores de PSNR acima de 50 dB indicam "
            "alteração imperceptível. Após uma ocultação, o botão <b>Comparar com original</b> "
            "abre esta tela já preenchida.")]
    s += shot("08_comparacao", "Comparação de imagens")

    # 14-16
    s += [PageBreak(), P("14. Histórico de operações", H1),
          P("Lista todas as operações com data, tipo, status, arquivos, tamanho, criptografia, "
            "duração e observações. Permite pesquisar, filtrar, ordenar, excluir registros, limpar "
            "o histórico e exportar em CSV ou PDF. O registro pode ser desativado em Configurações.")]
    s += [P("<b>Privacidade:</b> o histórico guarda somente metadados técnicos. Senhas, chaves, "
            "mensagens e nomes de arquivos ocultos <b>nunca</b> são registrados.", NOTE)]
    s += shot("09_historico", "Histórico de operações")
    s += [P("15. Relatórios", H1),
          P("Gera relatórios técnicos de operações por período e tipo, em <b>PDF</b> (com a "
            "identidade visual MARX SECRET, resumo estatístico e tabela detalhada) e <b>CSV</b> "
            "(UTF-8, separador ponto e vírgula, compatível com o Excel em português). "
            "Relatórios de análise e de comparação são gerados nas respectivas telas.")]
    s += shot("10_relatorios", "Relatórios")
    s += [P("16. Gerenciamento de arquivos", H1),
          P("Navega pelos arquivos de uma pasta (por padrão, a pasta de saída), indicando quais "
            "imagens contêm conteúdo MARX SECRET e quais arquivos são .mxs. Permite abrir, "
            "analisar, copiar o SHA-256 e realizar <b>exclusão segura</b> (sobrescrita com dados "
            "aleatórios e zeros, renomeação e remoção).")]
    s += [P("Em SSDs, sistemas com journaling, cópias de sombra ou pastas sincronizadas na nuvem, "
            "a eliminação física de todas as cópias não pode ser garantida pelo sistema "
            "operacional. Para máxima proteção, utilize criptografia de disco (BitLocker).", WARN)]
    s += shot("11_arquivos", "Gerenciamento de arquivos")

    # 17
    s += [PageBreak(), P("17. Configurações", H1)]
    s += [table([["Opção", "Descrição", "Padrão"],
                 ["Tema", "Escuro ou claro", "Escuro"],
                 ["Animações", "Transições discretas entre telas", "Ativadas"],
                 ["Derivação de chave", "Perfil do Argon2id: Rápido, Padrão ou Alto", "Padrão (64 MiB)"],
                 ["Exigir senha", "Impede ocultar conteúdo sem criptografia", "Sim"],
                 ["Tamanho mínimo da senha", "Número mínimo de caracteres", "8"],
                 ["Limpar área de transferência", "Tempo até limpar texto copiado", "30 s"],
                 ["Passagens da exclusão segura", "Número de sobrescritas", "3"],
                 ["Densidade padrão", "Bits por canal", "1"],
                 ["Distribuição dispersa", "Posições pseudoaleatórias derivadas da senha", "Sim"],
                 ["Comprimir conteúdos", "Compressão zlib antes de criptografar", "Sim"],
                 ["Tamanho máximo do conteúdo", "Limite por mensagem/arquivo", "64 MB"],
                 ["Pasta de saída padrão", "Onde as imagens e relatórios são sugeridos",
                  "Documentos\\MARX SECRET"],
                 ["Histórico", "Registrar operações (somente metadados)", "Sim"]], [48, 82, 40])]
    s += shot("12_configuracoes", "Configurações")
    s += shot("01_dashboard_claro", "Tema claro opcional")

    # 18
    s += [PageBreak(), P("18. Como o MARX SECRET protege seus dados", H1)]
    s += bullets([
        "<b>Esteganografia LSB</b>: os bits do conteúdo substituem os bits menos significativos "
        "dos canais vermelho, verde e azul. Cada valor muda no máximo 1 (a 1 bit/canal), o que é "
        "invisível. O canal alfa (transparência) nunca é alterado.",
        "<b>Distribuição dispersa</b>: as posições usadas são sorteadas a partir de "
        "SHA-256(senha + semente aleatória), espalhando as alterações por toda a imagem.",
        "<b>AES-256-GCM</b>: criptografia autenticada; qualquer alteração no conteúdo ou no "
        "cabeçalho é detectada. Um nonce aleatório de 96 bits é gerado a cada operação.",
        "<b>Argon2id</b>: derivação de chave resistente a ataques por GPU, com sal aleatório de "
        "128 bits e parâmetros gravados junto ao conteúdo.",
        "<b>SHA-256</b>: o hash do conteúdo original é verificado após a recuperação.",
        "<b>Validação</b> rigorosa de imagens (formato, tamanho, limite de 100 megapixels e "
        "proteção contra imagens maliciosas) e de nomes de arquivos recuperados.",
        "<b>Privacidade</b>: processamento local e offline, sem telemetria; senhas nunca são "
        "armazenadas; histórico e relatórios sem conteúdo secreto; banco SQLite com "
        "<i>secure_delete</i>; limpeza automática de temporários.",
    ])
    s += [P("Boas práticas", H2)]
    s += bullets([
        "Use senhas longas (12+ caracteres) e únicas; guarde-as em um gerenciador de senhas. "
        "<b>Não há recuperação de senha.</b>",
        "Prefira imagens próprias, com muitos detalhes (fotos), e 1 bit por canal.",
        "Não publique a imagem original e a processada juntas.",
        "Envie a imagem como <b>arquivo/documento</b>. Redes sociais e mensageiros recomprimem "
        "imagens e destroem o conteúdo oculto.",
        "Não edite, redimensione nem converta a imagem processada para JPEG.",
    ])

    # 19
    s += [P("19. Solução de problemas", H1),
          table([["Mensagem", "Causa e solução"],
                 ["Nenhum conteúdo MARX SECRET foi encontrado",
                  "A imagem não contém conteúdo ou foi recomprimida/editada. Use o arquivo original "
                  "recebido como documento."],
                 ["Senha incorreta ou conteúdo adulterado",
                  "Verifique a senha (maiúsculas/minúsculas). Se estiver correta, a imagem foi "
                  "modificada após a ocultação."],
                 ["Falha na verificação de integridade SHA-256",
                  "O conteúdo foi corrompido. Obtenha novamente a imagem original."],
                 ["A imagem não possui capacidade suficiente",
                  "Use uma imagem maior, aumente a densidade (bits por canal) ou ative a compressão."],
                 ["A imagem está corrompida ou não pôde ser lida",
                  "O arquivo está danificado ou não é uma imagem suportada."],
                 ["Aviso do Windows SmartScreen",
                  "Clique em Mais informações › Executar assim mesmo."],
                 ["Antivírus bloqueou o programa",
                  "Falso positivo comum em aplicativos empacotados; adicione uma exceção para a "
                  "pasta de instalação."]], [60, 110])]

    # 20
    s += [PageBreak(), P("20. Autodiagnóstico", H1),
          P("O MARX SECRET possui um autodiagnóstico offline que valida criptografia, "
            "esteganografia, integridade, banco de dados, análise, comparação, relatórios e "
            "interface. Para executá-lo, abra o Prompt de Comando na pasta do programa:"),
          P("MARX_SECRET.exe --self-test --report \"%USERPROFILE%\\Desktop\\diagnostico.txt\"", CODE),
          P("O resultado (APROVADO/REPROVADO, com o tempo de cada etapa) é gravado no arquivo "
            "indicado. Outras opções: <b>--version</b> e <b>--no-splash</b>. Também é possível "
            "abrir uma imagem diretamente na análise: <i>MARX_SECRET.exe caminho\\imagem.png</i>.")]

    # 21
    s += [P("21. Desinstalação", H1)]
    s += steps([
        "Abra <b>Configurações do Windows › Aplicativos › Aplicativos instalados</b> (ou "
        "Menu Iniciar › MARX SECRET › Desinstalar MARX SECRET).",
        "Selecione <b>MARX SECRET Professional</b> e clique em <b>Desinstalar</b>.",
        "Ao final, escolha se deseja remover também o histórico, as configurações e o banco de "
        "dados local (pasta <i>%APPDATA%\\MARX SECRET</i>). Imagens e relatórios que você criou "
        "não são apagados.",
    ])
    s += [P("Desinstalação silenciosa e completa: <i>unins000.exe /VERYSILENT /PURGE=1</i>.", NOTE),
          P("A versão portátil é removida simplesmente apagando a pasta extraída.")]

    # 22
    s += [P("22. Informações técnicas", H1),
          table([["Componente", "Detalhe"],
                 ["Linguagem / interface", "Python 3.12 · PySide6 (Qt 6)"],
                 ["Imagem / cálculo", "Pillow · NumPy"],
                 ["Criptografia", "cryptography (AES-256-GCM) · argon2-cffi (Argon2id)"],
                 ["Banco de dados", "SQLite (histórico e configurações)"],
                 ["Relatórios", "ReportLab (PDF) · CSV UTF-8"],
                 ["Empacotamento", "PyInstaller · Inno Setup 6"],
                 ["Dados do usuário", "%APPDATA%\\MARX SECRET (instalado) ou .\\dados (portátil)"],
                 ["Formato do contêiner", "versão · flags · [Argon2id t/m/p · sal 16 B · nonce 12 B] · "
                  "AES-GCM(tipo · nome · tamanho · SHA-256 · dados)"],
                 ["Cabeçalho na imagem", "17 bytes a 1 bit/canal: assinatura, layout, tamanho, semente"]],
                [45, 125]),
          Spacer(0, 10),
          P(f"{APP_COMMERCIAL_NAME} · {APP_SLOGAN}", CAPTION)]
    return s


def build(output: Path) -> Path:
    output.parent.mkdir(parents=True, exist_ok=True)
    doc = ManualDoc(str(output))
    doc.multiBuild(build_story())
    return output


if __name__ == "__main__":
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "docs" / "Manual_MARX_SECRET.pdf"
    print(f"Manual gerado: {build(out)}")
