import importlib
import sys
import types
from unittest.mock import MagicMock, patch

import pytest


psycopg2_stub = types.ModuleType("psycopg2")
psycopg2_stub.connect = MagicMock()
psycopg2_stub.Error = Exception
sys.modules.setdefault("psycopg2", psycopg2_stub)


POSTGRESQL_DIR = str(__import__("pathlib").Path(__file__).parents[1] / "postgresql")
if POSTGRESQL_DIR not in sys.path:
    sys.path.insert(0, POSTGRESQL_DIR)


banco = importlib.import_module("banco")


def test_conectar_retorna_conexao_com_configuracao():
    conexao = MagicMock()
    with patch.object(banco.psycopg2, "connect", return_value=conexao) as conectar:
        resultado = banco.conectar()

    assert resultado is conexao
    conectar.assert_called_once_with(**banco.POSTGRES_CONFIG)


def test_conectar_converte_erro_do_driver_em_runtime_error():
    erro_driver = banco.Error("falha de conexão")
    with patch.object(banco.psycopg2, "connect", side_effect=erro_driver):
        with pytest.raises(RuntimeError, match="Nao foi possivel conectar"):
            banco.conectar()


def test_executar_executa_sql_confirma_e_fecha_cursor():
    conexao = MagicMock()
    cursor = conexao.cursor.return_value

    banco.executar(conexao, "SELECT 1")

    cursor.execute.assert_called_once_with("SELECT 1")
    conexao.commit.assert_called_once_with()
    cursor.close.assert_called_once_with()


def test_inserir_em_lote_nao_abre_cursor_para_lista_vazia():
    conexao = MagicMock()

    banco.inserir_em_lote(conexao, "INSERT", [])

    conexao.cursor.assert_not_called()
    conexao.commit.assert_not_called()


def test_inserir_em_lote_executa_linhas_confirma_e_fecha_cursor():
    conexao = MagicMock()
    cursor = conexao.cursor.return_value
    linhas = [(1, "A"), (2, "B")]

    banco.inserir_em_lote(conexao, "INSERT INTO tabela VALUES (%s, %s)", linhas)

    cursor.executemany.assert_called_once_with(
        "INSERT INTO tabela VALUES (%s, %s)", linhas
    )
    conexao.commit.assert_called_once_with()
    cursor.close.assert_called_once_with()