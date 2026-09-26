import re
from pathlib import Path

import pytest


ARQUIVO_SQL = Path(__file__).parents[1] / "postgresql" / "0_criar_banco.sql"


COLUNAS_RAW_ESPERADAS = {
    "raw_viagem": {
        "identificador_do_processo_de_viagem",
        "numero_da_proposta_pcdp",
        "situacao",
        "viagem_urgente",
        "justificativa_urgencia_viagem",
        "codigo_do_orgao_superior",
        "nome_do_orgao_superior",
        "codigo_orgao_solicitante",
        "nome_orgao_solicitante",
        "cpf_viajante",
        "nome",
        "cargo",
        "funcao",
        "descricao_funcao",
        "periodo_data_de_inicio",
        "periodo_data_de_fim",
        "destinos",
        "motivo",
        "valor_diarias",
        "valor_passagens",
        "valor_devolucao",
        "valor_outros_gastos",
    },
    "raw_passagem": {
        "identificador_do_processo_de_viagem",
        "numero_da_proposta_pcdp",
        "meio_de_transporte",
        "pais_origem_ida",
        "uf_origem_ida",
        "cidade_origem_ida",
        "pais_destino_ida",
        "uf_destino_ida",
        "cidade_destino_ida",
        "pais_origem_volta",
        "uf_origem_volta",
        "cidade_origem_volta",
        "pais_destino_volta",
        "uf_destino_volta",
        "cidade_destino_volta",
        "valor_da_passagem",
        "taxa_de_servico",
        "data_da_emissao_compra",
        "hora_da_emissao_compra",
    },
    "raw_pagamento": {
        "identificador_do_processo_de_viagem",
        "numero_da_proposta_pcdp",
        "codigo_do_orgao_superior",
        "nome_do_orgao_superior",
        "codigo_do_orgao_pagador",
        "nome_do_orgao_pagador",
        "codigo_da_unidade_gestora_pagadora",
        "nome_da_unidade_gestora_pagadora",
        "tipo_de_pagamento",
        "valor",
    },
    "raw_trecho": {
        "identificador_do_processo_de_viagem",
        "numero_da_proposta_pcdp",
        "sequencia_trecho",
        "origem_data",
        "origem_pais",
        "origem_uf",
        "origem_cidade",
        "destino_data",
        "destino_pais",
        "destino_uf",
        "destino_cidade",
        "meio_de_transporte",
        "numero_diarias",
        "missao",
    },
}


def _colunas_da_tabela(sql: str, tabela: str) -> set[str]:
    trecho = re.search(
        rf"CREATE TABLE IF NOT EXISTS {tabela} \((.*?)\n\);",
        sql,
        flags=re.DOTALL,
    )
    assert trecho is not None
    return {
        linha.strip().split()[0]
        for linha in trecho.group(1).splitlines()
        if linha.strip()
    }


@pytest.mark.parametrize("tabela", COLUNAS_RAW_ESPERADAS)
def test_schema_raw_contem_todos_os_cabecalhos_normalizados_do_csv(tabela):
    sql = ARQUIVO_SQL.read_text(encoding="utf-8")

    assert _colunas_da_tabela(sql, tabela) == COLUNAS_RAW_ESPERADAS[tabela]
