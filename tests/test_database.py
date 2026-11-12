from marx_secret.data.database import Database, OperationRecord


def test_crud_filters_and_stats(db):
    db.add_operation(OperationRecord("ocultar_mensagem", "sucesso", input_path="a.png", payload_size=100))
    db.add_operation(OperationRecord("ocultar_arquivo", "sucesso", input_path="b.png", payload_size=900))
    rid = db.add_operation(OperationRecord("extrair_mensagem", "falha", input_path="c.png", message="Senha incorreta"))
    assert len(db.list_operations()) == 3
    assert len(db.list_operations(operation="ocultar_arquivo")) == 1
    assert len(db.list_operations(status="falha")) == 1
    assert len(db.list_operations(search="Senha")) == 1
    assert len(db.list_operations(limit=2)) == 2
    st = db.statistics()
    assert st["total"] == 3 and st["success"] == 2 and st["failure"] == 1
    assert st["hidden_bytes"] == 1000 and len(st["last7"]) == 7
    assert st["last7"][-1][1] == 3
    db.delete_operation(rid)
    assert len(db.list_operations()) == 2
    assert db.clear_history() == 2
    assert db.list_operations() == []


def test_settings(db):
    assert db.get_setting("theme") == "escuro"
    db.set_setting("theme", "claro")
    db.set_setting("bits_per_channel", 2)
    assert db.get_setting("theme") == "claro"
    assert db.all_settings()["bits_per_channel"] == 2
    db.reset_settings()
    assert db.get_setting("theme") == "escuro"


def test_persistence(tmp_path):
    p = tmp_path / "x.db"
    d = Database(p)
    d.add_operation(OperationRecord("analisar_imagem", "sucesso"))
    d.close()
    d2 = Database(p)
    assert d2.list_operations()[0].operation_label == "Análise de imagem"
    d2.close()
