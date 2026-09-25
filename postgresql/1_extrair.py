"""Baixa os CSVs, extrai o arquivo e carrega a camada Raw.

O conteúdo dos CSVs não é transformado. Apenas os nomes das colunas são
normalizados para que correspondam aos nomes usados nas tabelas Raw.
"""

from __future__ import annotations

import re
import unicodedata
import zipfile
from pathlib import Path
from typing import Iterable

import pandas as pd
import psycopg2
import requests

try:
	from postgresql import config
except ModuleNotFoundError:
	# Permite executar o arquivo diretamente a partir da pasta postgresql.
	import config


TABELAS_CSV = {
	"2025_Viagem.csv": "raw_viagem",
	"2025_Pagamento.csv": "raw_pagamento",
	"2025_Passagem.csv": "raw_passagem",
	"2025_Trecho.csv": "raw_trecho",
}

TAMANHO_LOTE = getattr(config, "TAMANHO_LOTE", 1_000)


def normalizar_nome_coluna(nome: str) -> str:
	"""Padroniza o nome de uma coluna do CSV.

	Remove acentos, converte o texto para letras minúsculas e substitui espaços
	e caracteres especiais por sublinhados. Essa padronização permite comparar
	com segurança os cabeçalhos dos CSVs com as colunas das tabelas Raw, sem
	alterar os valores dos registros.
	"""
	texto = unicodedata.normalize("NFKD", str(nome))
	texto = texto.encode("ascii", "ignore").decode("ascii")
	texto = re.sub(r"[^a-zA-Z0-9]+", "_", texto.strip().lower())
	return texto.strip("_")


def obter_configuracao(nome: str):
	"""Busca uma configuração obrigatória no módulo ``config``.

	Centralizar essa leitura evita credenciais e parâmetros espalhados pelo
	código. Se a configuração não existir ou estiver vazia, a função interrompe
	o pipeline com uma mensagem clara antes de iniciar o download ou a carga.
	"""
	valor = getattr(config, nome, None)
	if valor in (None, ""):
		raise RuntimeError(f"Defina {nome} no arquivo config.py ou .env.")
	return valor


def baixar_arquivo(url: str, destino: Path) -> Path:
	"""Baixa um arquivo HTTP em partes e salva-o no caminho indicado.

	O streaming evita manter o arquivo inteiro na memória, o que é importante
	para arquivos grandes. A função é uma utilidade genérica de download e
	retorna o caminho salvo para que a etapa seguinte possa utilizá-lo.
	"""
	destino.parent.mkdir(parents=True, exist_ok=True)

	with requests.get(url, stream=True, timeout=120) as resposta:
		resposta.raise_for_status()
		with destino.open("wb") as arquivo:
			for bloco in resposta.iter_content(chunk_size=1024 * 1024):
				if bloco:
					arquivo.write(bloco)

	return destino


def baixar_zip_google_drive(file_id: str, destino: Path) -> Path:
	"""Baixa o ZIP de dados do Google Drive.

	Usa o identificador configurado no projeto e trata o token de confirmação
	que o Google Drive pode exigir para arquivos maiores. O arquivo é gravado em
	streaming, preparando a entrada da etapa de extração sem modificar seu
	conteúdo original.
	"""
	url = "https://drive.google.com/uc"
	sessao = requests.Session()
	parametros = {"export": "download", "id": file_id}

	resposta = sessao.get(url, params=parametros, stream=True, timeout=120)
	resposta.raise_for_status()

	token = next(
		(
			valor
			for chave, valor in resposta.cookies.items()
			if chave.startswith("download_warning")
		),
		None,
	)
	if token:
		parametros["confirm"] = token
		resposta.close()
		resposta = sessao.get(url, params=parametros, stream=True, timeout=120)
		resposta.raise_for_status()

	destino.parent.mkdir(parents=True, exist_ok=True)
	with destino.open("wb") as arquivo:
		for bloco in resposta.iter_content(chunk_size=1024 * 1024):
			if bloco:
				arquivo.write(bloco)

	resposta.close()
	return destino


def extrair_zip(caminho_zip: Path, pasta_destino: Path) -> dict[str, Path]:
	"""Extrai os quatro CSVs esperados para a pasta de dados.

	Antes de extrair, verifica se Viagem, Pagamento, Passagem e Trecho estão
	presentes no ZIP. Essa validação evita que o pipeline carregue apenas parte
	dos dados e retorna um dicionário que relaciona cada arquivo ao seu caminho
	local.
	"""
	pasta_destino.mkdir(parents=True, exist_ok=True)

	with zipfile.ZipFile(caminho_zip) as arquivo_zip:
		nomes_zip = {Path(nome).name: nome for nome in arquivo_zip.namelist()}
		ausentes = set(TABELAS_CSV) - set(nomes_zip)
		if ausentes:
			raise FileNotFoundError(
				"CSV(s) ausente(s) no ZIP: " + ", ".join(sorted(ausentes))
			)

		caminhos = {}
		for nome_csv in TABELAS_CSV:
			caminho = pasta_destino / nome_csv
			with arquivo_zip.open(nomes_zip[nome_csv]) as origem:
				caminho.write_bytes(origem.read())
			caminhos[nome_csv] = caminho

	return caminhos


def obter_conexao():
	"""Abre a conexão com o PostgreSQL usando ``DB_CONFIG``.

	Essa função concentra a criação da conexão em um único ponto. Assim, as
	demais funções trabalham apenas com a conexão recebida e não precisam
	conhecer detalhes de host, porta, banco ou credenciais.
	"""
	parametros = obter_configuracao("DB_CONFIG")
	return psycopg2.connect(**parametros)


def obter_colunas_tabela(conexao, tabela: str) -> list[str]:
	"""Consulta as colunas de uma tabela Raw no catálogo do PostgreSQL.

	A ordem retornada pelo banco é usada na montagem dos INSERTs. Isso mantém o
	mapeamento entre cada valor do DataFrame e a coluna correta e permite validar
	se o CSV corresponde ao modelo criado no arquivo SQL.
	"""
	consulta = """
		SELECT column_name
		FROM information_schema.columns
		WHERE table_schema = 'public' AND table_name = %s
		ORDER BY ordinal_position
	"""
	with conexao.cursor() as cursor:
		cursor.execute(consulta, (tabela,))
		return [linha[0] for linha in cursor.fetchall()]


def ler_csv_em_blocos(caminho_csv: Path) -> Iterable[pd.DataFrame]:
	"""Lê um CSV em blocos usando o formato oficial dos arquivos.

	Configura o separador ponto e vírgula, o encoding ``latin-1`` e o tipo texto
	para preservar os valores da camada Raw. O parâmetro ``chunksize`` permite
	processar arquivos grandes sem carregá-los integralmente na memória.
	"""
	return pd.read_csv(
		caminho_csv,
		sep=";",
		encoding="latin-1",
		dtype=str,
		chunksize=TAMANHO_LOTE,
		keep_default_na=False,
	)


def inserir_lote(conexao, tabela: str, quadro: pd.DataFrame) -> None:
	"""Insere um bloco de registros na tabela Raw.

	Monta um INSERT parametrizado e envia os registros ao PostgreSQL com
	``executemany``. Os parâmetros evitam concatenar valores diretamente no SQL,
	enquanto os valores vazios são convertidos para ``NULL`` na tabela Raw.
	"""
	colunas = list(quadro.columns)
	marcadores = ", ".join(["%s"] * len(colunas))
	nomes = ", ".join(f'"{coluna}"' for coluna in colunas)
	consulta = f'INSERT INTO "{tabela}" ({nomes}) VALUES ({marcadores})'

	registros = [
		tuple(None if valor == "" else valor for valor in linha)
		for linha in quadro.itertuples(index=False, name=None)
	]
	with conexao.cursor() as cursor:
		cursor.executemany(consulta, registros)


def carregar_csv_raw(conexao, caminho_csv: Path, tabela: str) -> int:
	"""Substitui o conteúdo de uma tabela Raw pelo CSV correspondente.

	Primeiro consulta o esquema e executa ``TRUNCATE`` para tornar a execução
	idempotente. Depois lê, valida e insere cada bloco. O total retornado serve
	para registrar quantos registros foram carregados e facilitar a auditoria.
	"""
	colunas_tabela = obter_colunas_tabela(conexao, tabela)
	total = 0
	primeira_linha = True

	with conexao.cursor() as cursor:
		cursor.execute(f'TRUNCATE TABLE "{tabela}" RESTART IDENTITY')

	for bloco in ler_csv_em_blocos(caminho_csv):
		bloco.columns = [normalizar_nome_coluna(coluna) for coluna in bloco.columns]

		if primeira_linha:
			ausentes = set(colunas_tabela) - set(bloco.columns)
			extras = set(bloco.columns) - set(colunas_tabela)
			if ausentes:
				raise ValueError(
					f"Colunas ausentes em {caminho_csv.name}: "
					+ ", ".join(sorted(ausentes))
				)
			if extras:
				raise ValueError(
					f"Colunas do CSV sem correspondência em {tabela}: "
					+ ", ".join(sorted(extras))
				)
			primeira_linha = False

		inserir_lote(conexao, tabela, bloco[colunas_tabela])
		total += len(bloco)

	return total


def executar_pipeline() -> None:
	"""Orquestra o pipeline completo da camada Raw.

	Obtém as configurações, baixa o ZIP, extrai os CSVs, abre a conexão e chama
	a carga de cada tabela na ordem definida em ``TABELAS_CSV``. Todas as cargas
	são confirmadas juntas com ``commit``; se qualquer etapa falhar, ``rollback``
	desfaz a transação e impede uma camada Raw parcialmente atualizada.
	"""
	file_id = obter_configuracao("DRIVE_FILE_ID")
	pasta_dados = Path(getattr(config, "DATA_DIR", "data"))
	caminho_zip = pasta_dados / "viagens_2025.zip"
	pasta_csv = pasta_dados / "raw_csv"

	baixar_zip_google_drive(file_id, caminho_zip)
	arquivos = extrair_zip(caminho_zip, pasta_csv)

	conexao = obter_conexao()
	try:
		for nome_csv, tabela in TABELAS_CSV.items():
			quantidade = carregar_csv_raw(conexao, arquivos[nome_csv], tabela)
			print(f"{tabela}: {quantidade} registros carregados.")
		conexao.commit()
	except Exception:
		conexao.rollback()
		raise
	finally:
		conexao.close()


if __name__ == "__main__":
	try:
		executar_pipeline()
		print("Extração e carga da camada Raw concluídas com sucesso.")
	except (OSError, ValueError, requests.RequestException, psycopg2.Error) as erro:
		print(f"Falha no pipeline de extração: {erro}")
		raise SystemExit(1) from erro


