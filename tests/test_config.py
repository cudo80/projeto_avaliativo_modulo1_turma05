import importlib
import sys


PROJECT_ROOT = __file__
POSTGRESQL_DIR = str(
    __import__("pathlib").Path(PROJECT_ROOT).parents[1] / "postgresql"
)
if POSTGRESQL_DIR not in sys.path:
    sys.path.insert(0, POSTGRESQL_DIR)


config = importlib.import_module("config")


def test_carregar_env_ignora_linhas_vazias_comentarios_e_invalidas(
    tmp_path, monkeypatch
):
    arquivo_env = tmp_path / ".env"
    arquivo_env.write_text(
        "\n# comentário\nVALIDA=valor\nSEM_IGUAL\nOUTRA = outro valor\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(config, "PASTA_RAIZ", tmp_path)
    monkeypatch.delenv("VALIDA", raising=False)
    monkeypatch.delenv("OUTRA", raising=False)

    config.carregar_env()

    assert config.os.environ["VALIDA"] == "valor"
    assert config.os.environ["OUTRA"] == "outro valor"
    assert "SEM_IGUAL" not in config.os.environ


def test_carregar_env_nao_falha_quando_arquivo_nao_existe(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "PASTA_RAIZ", tmp_path)

    assert config.carregar_env() is None