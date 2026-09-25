import importlib.util
import sys
import types
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
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
    "extrair", PROJECT_ROOT / "1_extrair.py"
)
extrair = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(extrair)


def test_normalizar_nome_coluna_remove_acento_e_formata_snake_case():
    assert extrair.normalizar_nome_coluna(" Órgão superior / UF ") == (
        "orgao_superior_uf"
    )


def test_obter_configuracao_retorna_valor_existente(monkeypatch):
    monkeypatch.setattr(extrair.config, "TESTE", "valor", raising=False)

    assert extrair.obter_configuracao("TESTE") == "valor"


@pytest.mark.parametrize("valor", [None, ""])
def test_obter_configuracao_falha_para_valor_ausente(monkeypatch, valor):
    monkeypatch.setattr(extrair.config, "TESTE_AUSENTE", valor, raising=False)

    with pytest.raises(RuntimeError, match="Defina TESTE_AUSENTE"):
        extrair.obter_configuracao("TESTE_AUSENTE")


def test_baixar_arquivo_grava_blocos_e_verifica_resposta(tmp_path):
    resposta = MagicMock()
    resposta.__enter__.return_value = resposta
    resposta.iter_content.return_value = [b"abc", b"", b"def"]

    destino = tmp_path / "arquivo.zip"
    with patch.object(extrair.requests, "get", return_value=resposta) as obter:
        resultado = extrair.baixar_arquivo("https://exemplo.test/arquivo", destino)

    assert resultado == destino
    assert destino.read_bytes() == b"abcdef"
    resposta.raise_for_status.assert_called_once_with()
    obter.assert_called_once_with("https://exemplo.test/arquivo", stream=True, timeout=120)


def test_baixar_zip_google_drive_trata_token_de_confirmacao(tmp_path):
    primeira = MagicMock()
    primeira.cookies.items.return_value = [("download_warning_x", "token")]
    primeira.iter_content.return_value = []
    segunda = MagicMock()
    segunda.cookies.items.return_value = []
    segunda.iter_content.return_value = [b"zip"]
    sessao = MagicMock()
    sessao.get.side_effect = [primeira, segunda]

    with patch.object(extrair.requests, "Session", return_value=sessao):
        destino = extrair.baixar_zip_google_drive("id-123", tmp_path / "dados.zip")

    assert destino.read_bytes() == b"zip"
    assert sessao.get.call_count == 2
    primeira.close.assert_called_once_with()
    segunda.close.assert_called_once_with()


def test_extrair_zip_extrai_os_quatro_csvs(tmp_path):
    caminho_zip = tmp_path / "dados.zip"
    with zipfile.ZipFile(caminho_zip, "w") as arquivo_zip:
        for nome in extrair.TABELAS_CSV:
            arquivo_zip.writestr(nome, "id;valor\n1;teste\n")

    caminhos = extrair.extrair_zip(caminho_zip, tmp_path / "csv")

    assert set(caminhos) == set(extrair.TABELAS_CSV)
    assert all(caminho.exists() for caminho in caminhos.values())


def test_extrair_zip_falha_quando_csv_esta_ausente(tmp_path):
    caminho_zip = tmp_path / "incompleto.zip"
    with zipfile.ZipFile(caminho_zip, "w") as arquivo_zip:
        arquivo_zip.writestr("2025_Viagem.csv", "id;valor\n")

    with pytest.raises(FileNotFoundError, match=r"CSV\(s\) ausente\(s\)"):
        extrair.extrair_zip(caminho_zip, tmp_path / "csv")


def test_obter_conexao_usa_configuracao_do_modulo(monkeypatch):
    parametros = {"host": "localhost", "dbname": "teste"}
    monkeypatch.setattr(extrair.config, "DB_CONFIG", parametros, raising=False)
    conexao = MagicMock()

    with patch.object(extrair.psycopg2, "connect", return_value=conexao) as conectar:
        assert extrair.obter_conexao() is conexao

    conectar.assert_called_once_with(**parametros)


def test_obter_colunas_tabela_consulta_catalogo():
    conexao = MagicMock()
    cursor = conexao.cursor.return_value.__enter__.return_value
    cursor.fetchall.return_value = [("id",), ("nome",)]

    resultado = extrair.obter_colunas_tabela(conexao, "raw_teste")

    assert resultado == ["id", "nome"]
    cursor.execute.assert_called_once()
    assert cursor.execute.call_args.args[1] == ("raw_teste",)


def test_ler_csv_em_blocos_configura_formato_do_arquivo(monkeypatch, tmp_path):
    esperado = iter([pd.DataFrame({"id": ["1"]})])
    leitor = MagicMock(return_value=esperado)
    monkeypatch.setattr(extrair.pd, "read_csv", leitor)

    resultado = extrair.ler_csv_em_blocos(tmp_path / "dados.csv")

    assert resultado is esperado
    leitor.assert_called_once_with(
        tmp_path / "dados.csv",
        sep=";",
        encoding="latin-1",
        dtype=str,
        chunksize=extrair.TAMANHO_LOTE,
        keep_default_na=False,
    )


def test_inserir_lote_monta_insert_e_converte_vazio_para_null():
    conexao = MagicMock()
    cursor = conexao.cursor.return_value.__enter__.return_value
    quadro = pd.DataFrame({"id": ["1"], "nome": [""]})

    extrair.inserir_lote(conexao, "raw_teste", quadro)

    sql, registros = cursor.executemany.call_args.args
    assert sql == 'INSERT INTO "raw_teste" ("id", "nome") VALUES (%s, %s)'
    assert registros == [("1", None)]


def test_carregar_csv_raw_trunca_valida_e_insere_lotes(monkeypatch, tmp_path):
    conexao = MagicMock()
    cursor = conexao.cursor.return_value.__enter__.return_value
    monkeypatch.setattr(extrair, "obter_colunas_tabela", lambda *_: ["id", "nome"])
    quadro = pd.DataFrame({"ID": ["1"], "Nome": ["Ana"]})
    monkeypatch.setattr(extrair, "ler_csv_em_blocos", lambda *_: iter([quadro]))
    inserir = MagicMock()
    monkeypatch.setattr(extrair, "inserir_lote", inserir)

    total = extrair.carregar_csv_raw(conexao, tmp_path / "dados.csv", "raw_teste")

    assert total == 1
    cursor.execute.assert_called_once_with('TRUNCATE TABLE "raw_teste" RESTART IDENTITY')
    inserir.assert_called_once()
    assert list(inserir.call_args.args[2].columns) == ["id", "nome"]


def test_carregar_csv_raw_falha_para_coluna_ausente(monkeypatch, tmp_path):
    conexao = MagicMock()
    monkeypatch.setattr(extrair, "obter_colunas_tabela", lambda *_: ["id", "nome"])
    quadro = pd.DataFrame({"ID": ["1"]})
    monkeypatch.setattr(extrair, "ler_csv_em_blocos", lambda *_: iter([quadro]))

    with pytest.raises(ValueError, match="Colunas ausentes"):
        extrair.carregar_csv_raw(conexao, tmp_path / "dados.csv", "raw_teste")


def test_executar_pipeline_faz_commit_e_fecha_conexao(monkeypatch, tmp_path):
    conexao = MagicMock()
    monkeypatch.setattr(extrair, "obter_configuracao", lambda _: "drive-id")
    monkeypatch.setattr(extrair.config, "DATA_DIR", tmp_path, raising=False)
    monkeypatch.setattr(extrair, "baixar_zip_google_drive", MagicMock())
    arquivos = {nome: tmp_path / nome for nome in extrair.TABELAS_CSV}
    monkeypatch.setattr(extrair, "extrair_zip", MagicMock(return_value=arquivos))
    monkeypatch.setattr(extrair, "obter_conexao", MagicMock(return_value=conexao))
    monkeypatch.setattr(extrair, "carregar_csv_raw", MagicMock(return_value=2))

    extrair.executar_pipeline()

    conexao.commit.assert_called_once_with()
    conexao.rollback.assert_not_called()
    conexao.close.assert_called_once_with()


def test_executar_pipeline_faz_rollback_e_fecha_conexao_se_houver_falha(
    monkeypatch, tmp_path
):
    conexao = MagicMock()
    monkeypatch.setattr(extrair, "obter_configuracao", lambda _: "drive-id")
    monkeypatch.setattr(extrair.config, "DATA_DIR", tmp_path, raising=False)
    monkeypatch.setattr(extrair, "baixar_zip_google_drive", MagicMock())
    monkeypatch.setattr(
        extrair,
        "extrair_zip",
        MagicMock(return_value={nome: tmp_path / nome for nome in extrair.TABELAS_CSV}),
    )
    monkeypatch.setattr(extrair, "obter_conexao", MagicMock(return_value=conexao))
    monkeypatch.setattr(
        extrair,
        "carregar_csv_raw",
        MagicMock(side_effect=RuntimeError("falha na carga")),
    )

    with pytest.raises(RuntimeError, match="falha na carga"):
        extrair.executar_pipeline()

    conexao.commit.assert_not_called()
    conexao.rollback.assert_called_once_with()
    conexao.close.assert_called_once_with()