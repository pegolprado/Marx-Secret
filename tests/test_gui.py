"""Testes da interface gráfica (executados em modo offscreen)."""

import os

import pytest

os.environ["MARX_SECRET_NO_DIALOGS"] = "1"

from PySide6.QtWidgets import QApplication  # noqa: E402

from marx_secret.ui import worker  # noqa: E402
from marx_secret.ui.context import AppContext  # noqa: E402
from marx_secret.ui.main_window import NAV, MainWindow, apply_theme  # noqa: E402

from .conftest import PASSWORD, make_image  # noqa: E402


@pytest.fixture
def win(qtbot, db):
    db.set_setting("kdf_profile", "rapido")
    db.set_setting("animations", False)
    ctx = AppContext(db)
    apply_theme(QApplication.instance(), ctx.palette)
    w = MainWindow(ctx)
    qtbot.addWidget(w)
    w.show()
    return w


def _wait(qtbot):
    worker.wait_all()
    qtbot.wait(50)
    QApplication.processEvents()


def test_title_and_navigation(win):
    assert "MARX SECRET" in win.windowTitle()
    keys = [cls.key for _, classes in NAV for cls in classes]
    assert len(keys) == 13
    for k in keys:
        win.go(k)
        assert win.current_key() == k
        assert k in win.windowTitle() or win.pages[k].title in win.windowTitle()


def test_all_buttons_are_connected(win):
    """Nenhum botão sem função: todo QPushButton visível precisa de um receptor."""
    from PySide6.QtWidgets import QPushButton

    for page in win.pages.values():
        for b in page.findChildren(QPushButton):
            if b.objectName() == "Ghost" and b.isCheckable():
                continue  # botão de alternância de visibilidade usa toggled
            assert b.receivers("2clicked(bool)") > 0 or b.receivers("2clicked()") > 0, b.text()


def test_hide_extract_message_flow(win, qtbot, tmp_path):
    cover = make_image(tmp_path / "capa.png", size=(300, 200))
    win.go("hide_message")
    p = win.pages["hide_message"]
    p.cover.set_path(cover)
    p.message.setPlainText("Olá do teste de interface")
    p.password.edit.setText(PASSWORD)
    p.password.confirm.setText(PASSWORD)
    p.output.set_path(str(tmp_path / "saida.png"))
    assert p.meter.bar.value() > 0
    p.run()
    _wait(qtbot)
    assert not p.result.isHidden() and os.path.exists(tmp_path / "saida.png")
    assert p.password.password() == "" and p.message.toPlainText() == ""

    win.go("extract_message")
    e = win.pages["extract_message"]
    e.image.set_path(str(tmp_path / "saida.png"))
    assert "detectada" in e.signature.text()
    e.password.edit.setText(PASSWORD)
    e.run()
    _wait(qtbot)
    assert e.text_view.toPlainText() == "Olá do teste de interface"
    e._clear_result()
    assert e.text_view.toPlainText() == ""


def test_wrong_password_shows_error(win, qtbot, tmp_path):
    cover = make_image(tmp_path / "capa.png", size=(300, 200))
    p = win.pages["hide_message"]
    p.cover.set_path(cover)
    p.message.setPlainText("segredo")
    p.password.edit.setText(PASSWORD)
    p.password.confirm.setText(PASSWORD)
    p.output.set_path(str(tmp_path / "s.png"))
    p.run()
    _wait(qtbot)
    e = win.pages["extract_message"]
    e.image.set_path(str(tmp_path / "s.png"))
    e.password.edit.setText("senha-errada-xyz")
    e.run()
    _wait(qtbot)
    assert e.text_card.isHidden() and e.run_btn.isEnabled()


def test_password_confirmation_mismatch_blocks(win, tmp_path):
    p = win.pages["hide_message"]
    p.cover.set_path(make_image(tmp_path / "capa.png"))
    p.message.setPlainText("x")
    p.password.edit.setText(PASSWORD)
    p.password.confirm.setText("diferente")
    p.output.set_path(str(tmp_path / "s.png"))
    assert p._validate() == "A confirmação da senha não confere."


def test_hide_recover_file_flow(win, qtbot, tmp_path):
    cover = make_image(tmp_path / "capa.png", size=(400, 300))
    secret = tmp_path / "planilha.csv"
    secret.write_text("a;b;c\n1;2;3\n", encoding="utf-8")
    p = win.pages["hide_file"]
    p.cover.set_path(cover)
    p.secret_file.set_path(str(secret))
    p.password.edit.setText(PASSWORD)
    p.password.confirm.setText(PASSWORD)
    p.output.set_path(str(tmp_path / "saida.png"))
    p.run()
    _wait(qtbot)
    r = win.pages["recover_file"]
    r.image.set_path(str(tmp_path / "saida.png"))
    r.password.edit.setText(PASSWORD)
    r.run()
    _wait(qtbot)
    assert not r.file_card.isHidden()
    dest = tmp_path / "rec"
    dest.mkdir()
    out = r.save_file_to(str(dest))
    assert out.read_text(encoding="utf-8") == secret.read_text(encoding="utf-8")


def test_crypto_page(win, qtbot, tmp_path):
    src = tmp_path / "doc.txt"
    src.write_text("documento confidencial", encoding="utf-8")
    c = win.pages["crypto"]
    c.enc_src.set_path(str(src))
    assert c.enc_dst.path().endswith(".mxs")
    c.enc_pwd.edit.setText(PASSWORD)
    c.enc_pwd.confirm.setText(PASSWORD)
    c.encrypt()
    _wait(qtbot)
    assert os.path.exists(str(src) + ".mxs")
    out = tmp_path / "out"
    out.mkdir()
    c.dec_src.set_path(str(src) + ".mxs")
    c.dec_dst.set_path(str(out))
    c.dec_pwd.edit.setText(PASSWORD)
    c.decrypt()
    _wait(qtbot)
    assert (out / "doc.txt").read_text(encoding="utf-8") == "documento confidencial"
    c.generate()
    assert len(c.gen_out.text()) == 20
    c.hash_src.set_path(str(src))
    c.compute_hash()
    _wait(qtbot)
    assert len(c.hash_out.text()) == 64


def test_analysis_compare_reports_pages(win, qtbot, tmp_path):
    cover = make_image(tmp_path / "capa.png", size=(300, 200))
    a = win.pages["analysis"]
    a.image.set_path(cover)
    a.run()
    _wait(qtbot)
    assert not a.details.isHidden() and a.result is not None
    a.save_pdf(str(tmp_path / "analise.pdf"))
    assert (tmp_path / "analise.pdf").exists()
    win.ctx.request_compare.emit(cover, cover)
    _wait(qtbot)
    cp = win.pages["compare"]
    assert win.current_key() == "compare" and cp.result.identical
    cp.save_pdf(str(tmp_path / "comp.pdf"))
    assert (tmp_path / "comp.pdf").exists()
    rp = win.pages["reports"]
    rp.dest.set_path(str(tmp_path))
    assert rp.make_pdf().exists() and rp.make_csv().exists()


def test_history_and_files_pages(win, qtbot, tmp_path):
    win.ctx.service.analyze(make_image(tmp_path / "x.png"))
    win.ctx.notify_history()
    h = win.pages["history"]
    assert h.table.rowCount() >= 1
    h.op_filter.setCurrentIndex(h.op_filter.findData("analisar_imagem"))
    assert h.table.rowCount() == 1
    h.clear()
    assert win.ctx.db.list_operations() == []
    f = win.pages["files"]
    (tmp_path / "apagar.txt").write_text("x")
    f.folder.set_path(str(tmp_path))
    names = [f.table.item(i, 0).text() for i in range(f.table.rowCount())]
    assert "apagar.txt" in names
    f.table.selectRow(names.index("apagar.txt"))
    f.table.setCurrentCell(names.index("apagar.txt"), 0)
    f.secure_delete_selected()
    _wait(qtbot)
    assert not (tmp_path / "apagar.txt").exists()


def test_settings_theme_switch(win):
    s = win.pages["settings"]
    s.theme.setCurrentIndex(s.theme.findData("claro"))
    s.bpc.setCurrentIndex(s.bpc.findData(2))
    s.save()
    assert win.ctx.setting("theme") == "claro"
    assert QApplication.instance().property("marx_theme") == "claro"
    assert win.pages["hide_message"].bpc.currentData() == 2
    s.reset()
    assert win.ctx.setting("theme") == "escuro"


def test_selftest_runs():
    from marx_secret.selftest import run_self_test

    ok, lines = run_self_test(include_gui=False)
    assert ok, "\n".join(lines)
