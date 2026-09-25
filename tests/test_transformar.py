import importlib.util
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

import pytest


psycopg2_stub = types.ModuleType("psycopg2")
psycopg2_stub.connect = MagicMock()
psycopg2_stub.Error = Exception
sys.modules.setdefault("psycopg2", psycopg2_stub)


PROJECT_ROOT = Path(__file__).parents[1]
POSTGRESQL_DIR = str(PROJECT_ROOT / "postgresql")
if POSTGRESQL_DIR not in sys.path:
    sys.path.insert(0, POSTGRESQL_DIR)

SPEC = importlib.util.spec_from_file_location(
    "transformar", PROJECT_ROOT / "postgresql" / "2_transformar.py"
)
transformar = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(transformar)


def test_decimal_sql_trata_decimal_brasileiro_e_valor_vazio():
    expressao = transformar.gerar_sql_viagem()

    assert "POSITION(',' IN BTRIM(valor_diarias))" in expressao
    assert "REPLACE(REPLACE(BTRIM(valor_diarias), '.', ''), ',', '.')" in expressao
    assert "::DECIMAL" in expressao


def test_data_sql_aceita_apenas_data_no_formato_brasileiro():
    expressao = transformar.gerar_sql_viagem()

    assert "DD/MM/YYYY" in expressao
    assert "^[0-9]{2}/[0-9]{2}/[0-9]{4}$" in expressao
    assert "ELSE NULL" in expressao


def test_insert_passagem_mapeia_uf_e_cidade_de_destino():
    comando = transformar.gerar_sql_passagem()

    assert "FROM raw_passagem" in comando
    assert "uf_destino_ida" in comando
    assert "cidade_destino_ida" in comando


def test_transformar_trunca_e_carrega_na_ordem_das_dependencias():
    conexao = MagicMock()
    cursor = conexao.cursor.return_value.__enter__.return_value

    transformar.transformar(conexao)

    comandos = [chamada.args[0] for chamada in cursor.execute.call_args_list]
    assert comandos[0].startswith(
        "TRUNCATE TABLE silver_passagem, silver_pagamento, "
    )
    assert comandos[1].find("FROM raw_viagem") >= 0
    assert comandos[2].find("FROM raw_passagem") >= 0
    assert comandos[3].find("FROM raw_pagamento") >= 0
    assert comandos[4].find("FROM raw_trecho") >= 0


def test_executar_pipeline_confirma_e_fecha_conexao(monkeypatch):
    conexao = MagicMock()
    transformar_pipeline = MagicMock()
    monkeypatch.setattr(transformar, "obter_conexao", lambda: conexao)
    monkeypatch.setattr(transformar, "transformar", transformar_pipeline)

    transformar.executar_pipeline()

    transformar_pipeline.assert_called_once_with(conexao)
    conexao.commit.assert_called_once_with()
    conexao.rollback.assert_not_called()
    conexao.close.assert_called_once_with()


def test_executar_pipeline_desfaz_transacao_e_fecha_conexao_se_falhar(
    monkeypatch,
):
    conexao = MagicMock()
    monkeypatch.setattr(transformar, "obter_conexao", lambda: conexao)
    monkeypatch.setattr(
        transformar,
        "transformar",
        MagicMock(side_effect=RuntimeError("falha na transformação")),
    )

    with pytest.raises(RuntimeError, match="falha na transformação"):
        transformar.executar_pipeline()

    conexao.commit.assert_not_called()
    conexao.rollback.assert_called_once_with()
    conexao.close.assert_called_once_with()
