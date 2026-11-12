import csv

from marx_secret.core import analysis, compare, imageio
from marx_secret.data.database import OperationRecord
from marx_secret.reports import csv_report, pdf_report
from marx_secret.services.operations import HideOptions

from .conftest import PASSWORD


def _records(db):
    db.add_operation(OperationRecord("ocultar_mensagem", "sucesso", input_path="C:/fotos/praia.png",
                                     output_path="C:/saida/praia_marx.png", payload_kind="Mensagem",
                                     payload_size=321, encrypted=True, bits_per_channel=1,
                                     output_sha256="ab" * 32, message="ok"))
    db.add_operation(OperationRecord("extrair_mensagem", "falha", input_path="=HYPERLINK(\"x\")",
                                     message="Senha incorreta ou conteúdo adulterado."))
    return db.list_operations()


def test_history_pdf_and_csv(db, tmp_path):
    recs = _records(db)
    pdf = pdf_report.history_report_pdf(recs, db.statistics(), tmp_path / "hist.pdf")
    data = pdf.read_bytes()
    assert data.startswith(b"%PDF") and len(data) > 2000
    assert b"MARX SECRET" in data
    c = csv_report.export_history_csv(recs, tmp_path / "hist.csv")
    with open(c, encoding="utf-8-sig") as fh:
        rows = list(csv.reader(fh, delimiter=";"))
    assert rows[0][0] == "ID" and len(rows) == 3
    assert rows[1][4].startswith("'=")  # proteção contra injeção de fórmulas


def test_empty_history_pdf(db, tmp_path):
    pdf = pdf_report.history_report_pdf([], db.statistics(), tmp_path / "vazio.pdf")
    assert pdf.read_bytes().startswith(b"%PDF")


def test_analysis_and_comparison_reports(service, big_cover, tmp_path):
    out = str(tmp_path / "s.png")
    service.hide_message(big_cover, out, "segredo-do-relatorio",
                         HideOptions(password=PASSWORD, kdf_profile="rapido"))
    r = analysis.analyze_image(out)
    lsb = analysis.lsb_plane(imageio.load_image(out))
    p = pdf_report.analysis_report_pdf(r, tmp_path / "analise.pdf", lsb)
    assert p.read_bytes().startswith(b"%PDF")
    csv_report.export_analysis_csv(r, tmp_path / "analise.csv")
    cr = compare.compare_images(big_cover, out)
    p2 = pdf_report.comparison_report_pdf(
        cr, tmp_path / "comp.pdf", imageio.load_image(big_cover), imageio.load_image(out),
        compare.difference_image(big_cover, out))
    assert p2.read_bytes().startswith(b"%PDF")
    csv_report.export_comparison_csv(cr, tmp_path / "comp.csv")
    for f in tmp_path.glob("*.csv"):
        assert "segredo-do-relatorio" not in f.read_text(encoding="utf-8-sig")
        assert PASSWORD not in f.read_text(encoding="utf-8-sig")
