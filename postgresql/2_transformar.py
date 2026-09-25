"""Transforma as tabelas Raw e carrega a camada Silver.

A transformação é executada no PostgreSQL para evitar carregar todas as linhas
em memória. Textos vazios viram NULL, datas no formato DD/MM/AAAA são
convertidas para DATE e valores com vírgula decimal são convertidos para
DECIMAL. As colunas ``valor_total`` e ``duracao_dias`` são calculadas pelo
próprio banco, conforme definido em ``0_criar_banco.sql``.
"""

from __future__ import annotations

import psycopg2

try:
    from postgresql import config
except ModuleNotFoundError:
    import config


TABELAS_SILVER = (
    "silver_passagem",
    "silver_pagamento",
    "silver_trecho",
    "silver_viagem",
)


def _texto_sql(coluna: str) -> str:
    """Retorna a expressão SQL para limpar uma coluna textual."""
    return f"NULLIF(BTRIM({coluna}), '')"


def _data_sql(coluna: str) -> str:
    """Retorna a expressão SQL para converter datas brasileiras com segurança."""
    texto = f"BTRIM({coluna})"
    return (
        "CASE "
        f"WHEN {texto} ~ '^[0-9]{{2}}/[0-9]{{2}}/[0-9]{{4}}$' "
        f"THEN TO_DATE({texto}, 'DD/MM/YYYY') "
        "ELSE NULL END"
    )


def _decimal_sql(coluna: str) -> str:
    """Retorna a expressão SQL para converter números no padrão brasileiro."""
    texto = f"BTRIM({coluna})"
    numero = (
        f"CASE WHEN POSITION(',' IN {texto}) > 0 "
        f"THEN REPLACE(REPLACE({texto}, '.', ''), ',', '.') "
        f"ELSE {texto} END"
    )
    return (
        "CASE "
        f"WHEN {texto} ~ '^-?[0-9]+([.,][0-9]+)?$' "
        f"THEN ({numero})::DECIMAL "
        "ELSE NULL END"
    )


def _inteiro_sql(coluna: str) -> str:
    """Retorna a expressão SQL para converter inteiros ou produzir NULL."""
    texto = f"BTRIM({coluna})"
    return (
        "CASE "
        f"WHEN {texto} ~ '^-?[0-9]+$' THEN {texto}::INTEGER "
        "ELSE NULL END"
    )


def gerar_sql_viagem() -> str:
    return f"""\
INSERT INTO silver_viagem (
    id_viagem,
    num_proposta,
    situacao,
    viagem_urgente,
    cod_orgao_superior,
    nome_orgao_superior,
    nome_viajante,
    cargo,
    data_inicio,
    data_fim,
    destinos,
    motivo,
    valor_diarias,
    valor_passagens,
    valor_devolucao,
    valor_outros_gastos
)
SELECT
    {_texto_sql('id_viagem')},
    {_texto_sql('num_proposta')},
    {_texto_sql('situacao')},
    {_texto_sql('viagem_urgente')},
    {_texto_sql('cod_orgao_superior')},
    {_texto_sql('nome_orgao_superior')},
    {_texto_sql('nome_viajante')},
    {_texto_sql('cargo')},
    {_data_sql('data_inicio')},
    {_data_sql('data_fim')},
    {_texto_sql('destinos')},
    {_texto_sql('motivo')},
    {_decimal_sql('valor_diarias')},
    {_decimal_sql('valor_passagens')},
    {_decimal_sql('valor_devolucao')},
    {_decimal_sql('valor_outros_gastos')}
FROM raw_viagem
"""


def gerar_sql_passagem() -> str:
    return f"""\
INSERT INTO silver_passagem (
    id_viagem,
    meio_transporte,
    pais_origem_ida,
    uf_origem_ida,
    cidade_origem_ida,
    pais_destino_ida,
    uf_destino_ida,
    cidade_destino_ida,
    valor_passagem,
    taxa_servico,
    data_emissao
)
SELECT
    {_texto_sql('id_viagem')},
    {_texto_sql('meio_transporte')},
    {_texto_sql('pais_origem_ida')},
    {_texto_sql('uf_origem_ida')},
    {_texto_sql('cidade_origem_ida')},
    {_texto_sql('pais_destino_ida')},
    {_texto_sql('uf_destino_ida')},
    {_texto_sql('cidade_destino_ida')},
    {_decimal_sql('valor_passagem')},
    {_decimal_sql('taxa_servico')},
    {_data_sql('data_emissao')}
FROM raw_passagem
"""


def gerar_sql_pagamento() -> str:
    return f"""\
INSERT INTO silver_pagamento (
    id_viagem,
    num_proposta,
    nome_orgao_pagador,
    nome_ug_pagadora,
    tipo_pagamento,
    valor
)
SELECT
    {_texto_sql('id_viagem')},
    {_texto_sql('num_proposta')},
    {_texto_sql('nome_orgao_pagador')},
    {_texto_sql('nome_ug_pagadora')},
    {_texto_sql('tipo_pagamento')},
    {_decimal_sql('valor')}
FROM raw_pagamento
"""


def gerar_sql_trecho() -> str:
    return f"""\
INSERT INTO silver_trecho (
    id_viagem,
    sequencia_trecho,
    origem_data,
    origem_uf,
    origem_cidade,
    destino_data,
    destino_uf,
    destino_cidade,
    meio_transporte,
    numero_diarias
)
SELECT
    {_texto_sql('id_viagem')},
    {_inteiro_sql('sequencia_trecho')},
    {_data_sql('origem_data')},
    {_texto_sql('origem_uf')},
    {_texto_sql('origem_cidade')},
    {_data_sql('destino_data')},
    {_texto_sql('destino_uf')},
    {_texto_sql('destino_cidade')},
    {_texto_sql('meio_transporte')},
    {_decimal_sql('numero_diarias')}
FROM raw_trecho
"""


def obter_conexao():
    """Abre a conexão usando as credenciais carregadas em ``config.py``."""
    return psycopg2.connect(**config.DB_CONFIG)


def truncar_silver(conexao) -> None:
    """Limpa a camada Silver antes da carga, mantendo o processo idempotente."""
    tabelas = ", ".join(TABELAS_SILVER)
    with conexao.cursor() as cursor:
        cursor.execute(f"TRUNCATE TABLE {tabelas} RESTART IDENTITY CASCADE")


def transformar(conexao) -> None:
    """Recria a camada Silver a partir das tabelas Raw."""
    truncar_silver(conexao)
    comandos = (
        gerar_sql_viagem(),
        gerar_sql_passagem(),
        gerar_sql_pagamento(),
        gerar_sql_trecho(),
    )
    with conexao.cursor() as cursor:
        for comando in comandos:
            cursor.execute(comando)


def executar_pipeline() -> None:
    """Executa a transformação em uma única transação."""
    conexao = obter_conexao()
    try:
        transformar(conexao)
        conexao.commit()
        print("Transformação Raw -> Silver concluída com sucesso.")
    except Exception:
        conexao.rollback()
        raise
    finally:
        conexao.close()


if __name__ == "__main__":
    try:
        executar_pipeline()
    except (OSError, psycopg2.Error) as erro:
        print(f"Falha na transformação: {erro}")
        raise SystemExit(1) from erro
