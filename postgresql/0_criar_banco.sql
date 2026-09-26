CREATE TABLE IF NOT EXISTS silver_viagem (
    id_viagem VARCHAR(20) NOT NULL,
    num_proposta VARCHAR(20),
    situacao VARCHAR(50),
    viagem_urgente VARCHAR(5),
    cod_orgao_superior VARCHAR(20),
    nome_orgao_superior VARCHAR(255) NOT NULL,
    nome_viajante VARCHAR(255),
    cargo VARCHAR(255),
    data_inicio DATE,
    data_fim DATE,
    destinos VARCHAR(4000),
    motivo VARCHAR(4000),
    valor_diarias DECIMAL(10, 2),
    valor_passagens DECIMAL(10, 2),
    valor_devolucao DECIMAL(10, 2),
    valor_outros_gastos DECIMAL(10, 2),

    valor_total DECIMAL(12, 2)
        GENERATED ALWAYS AS (
            COALESCE(valor_diarias, 0)
            + COALESCE(valor_passagens, 0)
            - COALESCE(valor_devolucao, 0)
            + COALESCE(valor_outros_gastos, 0)
        ) STORED,

    duracao_dias INT
        GENERATED ALWAYS AS (
            data_fim - data_inicio
        ) STORED,

    CONSTRAINT pk_silver_viagem PRIMARY KEY (id_viagem),
    CONSTRAINT chk_silver_viagem_valor_diarias
        CHECK (valor_diarias >= 0)
);


CREATE TABLE IF NOT EXISTS silver_passagem (
    id_passagem INT GENERATED ALWAYS AS IDENTITY,
    id_viagem VARCHAR(20) NOT NULL,
    meio_transporte VARCHAR(50),
    pais_origem_ida VARCHAR(60),
    uf_origem_ida VARCHAR(40),
    cidade_origem_ida VARCHAR(80),
    pais_destino_ida VARCHAR(60),
    uf_destino_ida VARCHAR(40),
    cidade_destino_ida VARCHAR(80),
    valor_passagem DECIMAL(10, 2),
    taxa_servico DECIMAL(10, 2),
    data_emissao DATE,

    CONSTRAINT pk_silver_passagem PRIMARY KEY (id_passagem),
    CONSTRAINT fk_silver_passagem_viagem
        FOREIGN KEY (id_viagem)
        REFERENCES silver_viagem (id_viagem),
    CONSTRAINT chk_silver_passagem_valor
        CHECK (valor_passagem >= 0),
    CONSTRAINT chk_silver_passagem_taxa
        CHECK (taxa_servico >= 0)
);


CREATE TABLE IF NOT EXISTS silver_pagamento (
    id_pagamento INT GENERATED ALWAYS AS IDENTITY,
    id_viagem VARCHAR(20) NOT NULL,
    num_proposta VARCHAR(20),
    nome_orgao_pagador VARCHAR(255),
    nome_ug_pagadora VARCHAR(255),
    tipo_pagamento VARCHAR(50) NOT NULL,
    valor DECIMAL(10, 2),

    CONSTRAINT pk_silver_pagamento PRIMARY KEY (id_pagamento),
    CONSTRAINT fk_silver_pagamento_viagem
        FOREIGN KEY (id_viagem)
        REFERENCES silver_viagem (id_viagem),
    CONSTRAINT chk_silver_pagamento_valor
        CHECK (valor >= 0)
);


CREATE TABLE IF NOT EXISTS silver_trecho (
    id_trecho INT GENERATED ALWAYS AS IDENTITY,
    id_viagem VARCHAR(20) NOT NULL,
    sequencia_trecho INT,
    origem_data DATE,
    origem_uf VARCHAR(40),
    origem_cidade VARCHAR(80),
    destino_data DATE,
    destino_uf VARCHAR(40),
    destino_cidade VARCHAR(80),
    meio_transporte VARCHAR(50),
    numero_diarias DECIMAL(10, 2),

    CONSTRAINT pk_silver_trecho PRIMARY KEY (id_trecho),
    CONSTRAINT fk_silver_trecho_viagem
        FOREIGN KEY (id_viagem)
        REFERENCES silver_viagem (id_viagem),
    CONSTRAINT chk_silver_trecho_diarias
        CHECK (numero_diarias >= 0),
    CONSTRAINT uq_silver_trecho_viagem_sequencia
        UNIQUE (id_viagem, sequencia_trecho)
);


CREATE TABLE IF NOT EXISTS raw_viagem (
    identificador_do_processo_de_viagem VARCHAR(255),
    numero_da_proposta_pcdp VARCHAR(255),
    situacao VARCHAR(255),
    viagem_urgente VARCHAR(255),
    justificativa_urgencia_viagem VARCHAR(255),
    codigo_do_orgao_superior VARCHAR(255),
    nome_do_orgao_superior VARCHAR(255),
    codigo_orgao_solicitante VARCHAR(255),
    nome_orgao_solicitante VARCHAR(255),
    cpf_viajante VARCHAR(255),
    nome VARCHAR(255),
    cargo VARCHAR(255),
    funcao VARCHAR(255),
    descricao_funcao VARCHAR(255),
    periodo_data_de_inicio VARCHAR(255),
    periodo_data_de_fim VARCHAR(255),
    destinos VARCHAR(4000),
    motivo VARCHAR(4000),
    valor_diarias VARCHAR(255),
    valor_passagens VARCHAR(255),
    valor_devolucao VARCHAR(255),
    valor_outros_gastos VARCHAR(255)
);


CREATE TABLE IF NOT EXISTS raw_passagem (
    identificador_do_processo_de_viagem VARCHAR(255),
    numero_da_proposta_pcdp VARCHAR(255),
    meio_de_transporte VARCHAR(255),
    pais_origem_ida VARCHAR(255),
    uf_origem_ida VARCHAR(255),
    cidade_origem_ida VARCHAR(255),
    pais_destino_ida VARCHAR(255),
    uf_destino_ida VARCHAR(255),
    cidade_destino_ida VARCHAR(255),
    pais_origem_volta VARCHAR(255),
    uf_origem_volta VARCHAR(255),
    cidade_origem_volta VARCHAR(255),
    pais_destino_volta VARCHAR(255),
    uf_destino_volta VARCHAR(255),
    cidade_destino_volta VARCHAR(255),
    valor_da_passagem VARCHAR(255),
    taxa_de_servico VARCHAR(255),
    data_da_emissao_compra VARCHAR(255),
    hora_da_emissao_compra VARCHAR(255)
);


CREATE TABLE IF NOT EXISTS raw_pagamento (
    identificador_do_processo_de_viagem VARCHAR(255),
    numero_da_proposta_pcdp VARCHAR(255),
    codigo_do_orgao_superior VARCHAR(255),
    nome_do_orgao_superior VARCHAR(255),
    codigo_do_orgao_pagador VARCHAR(255),
    nome_do_orgao_pagador VARCHAR(255),
    codigo_da_unidade_gestora_pagadora VARCHAR(255),
    nome_da_unidade_gestora_pagadora VARCHAR(255),
    tipo_de_pagamento VARCHAR(255),
    valor VARCHAR(255)
);


CREATE TABLE IF NOT EXISTS raw_trecho (
    identificador_do_processo_de_viagem VARCHAR(255),
    numero_da_proposta_pcdp VARCHAR(255),
    sequencia_trecho VARCHAR(255),
    origem_data VARCHAR(255),
    origem_pais VARCHAR(255),
    origem_uf VARCHAR(255),
    origem_cidade VARCHAR(255),
    destino_data VARCHAR(255),
    destino_pais VARCHAR(255),
    destino_uf VARCHAR(255),
    destino_cidade VARCHAR(255),
    meio_de_transporte VARCHAR(255),
    numero_diarias VARCHAR(255),
    missao VARCHAR(255)
);
