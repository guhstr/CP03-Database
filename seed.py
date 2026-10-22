"""
Script de Seed do Banco de Dados MongoDB - TicketFlash
Popula o MongoDB com dados realistas: 16 eventos, 30 usuários e 80 pedidos.
Atende ao Requisito 1: mínimo de 10 eventos, 20 usuários e 50 pedidos.

Uso:
    docker compose exec api python seed.py
(A API também executa o seed automaticamente no startup se o banco estiver vazio)
"""
import random
from datetime import datetime, timedelta, timezone
from bson import ObjectId

from app.db import db, criar_indices

CATEGORIAS = ["Show", "Festival", "Teatro", "Stand-up", "Esporte", "Orquestra"]

CIDADES_LOCAIS = [
    ("São Paulo", "Allianz Parque - Av. Francisco Matarazzo, 1705"),
    ("São Paulo", "Teatro Renault - Av. Brigadeiro Luís Antônio, 411"),
    ("São Paulo", "MorumBIS - Praça Roberto Gomes Pedrosa, 1"),
    ("Rio de Janeiro", "Maracanã - Av. Pres. Castelo Branco, Portão 3"),
    ("Rio de Janeiro", "Teatro Riachuelo - Rua do Passeio, 38"),
    ("Rio de Janeiro", "Qualistage - Via Parque Shopping, Av. Ayrton Senna, 3000"),
    ("Belo Horizonte", "Mineirão - Av. Antônio Abrahão Caram, 1001"),
    ("Curitiba", "Pedreira Paulo Leminski - Parque das Pedreiras"),
    ("Salvador", "Arena Fonte Nova - Ladeira da Fonte das Pedras, s/n"),
    ("Porto Alegre", "Arena do Grêmio - Av. Padre Leopoldo Brentano, 110"),
    ("Brasília", "Estádio Mané Garrincha - SRPN Trecho 1")
]

EVENTOS_BASE = [
    ("Show: Rock in Night com Titãs e convidados", "Show", ["Titãs", "CPM 22", "Pitty"]),
    ("Festival Planeta Brasil 2026", "Festival", ["Alok", "Vintage Culture", "Dennis DJ"]),
    ("Teatro Musical: O Fantasma da Ópera", "Teatro", ["Companhia de Teatro Broadway Brasil"]),
    ("Stand-up Comedy: Noite dos Improvisos", "Stand-up", ["Thiago Ventura", "Afonso Padilha"]),
    ("Supercopa dos Campeões de Futebol 2026", "Esporte", ["Seleção Paulista", "Seleção Carioca"]),
    ("Orquestra Sinfônica: Clássicos do Cinema", "Orquestra", ["Orquestra Filarmônica Nacional"]),
    ("Show Acústico: Noite de MPB e Bossa Nova", "Show", ["Gilberto Gil", "Caetano Veloso"]),
    ("Festival Sertanejo Universitário", "Festival", ["Jorge & Mateus", "Henrique & Juliano"]),
    ("Teatro Comédia: Casamento em Apuros", "Teatro", ["Grupo Cênico Risadas"]),
    ("Stand-up Especial: A Vida Depois dos 30", "Stand-up", ["Bruna Louise", "Rodrigo Marques"]),
    ("Grand Prix de Judô e Artes Marciais", "Esporte", ["Confederação Brasileira de Judô"]),
    ("Show: Turnê de Despedida Skank", "Show", ["Skank", "Jota Quest"]),
    ("Festival Jazz & Blues na Serra", "Festival", ["Banda Blue Note", "Trio Instrumental"]),
    ("Teatro Infantil: Aventuras no Reino Encantado", "Teatro", ["Trupe Circo & Arte"]),
    ("Show: Noite Indie com Terno Rei e convidados", "Show", ["Terno Rei", "Boogarins"]),
    ("Final da Liga Nacional de Basquete", "Esporte", ["Franca Basquete", "Flamengo Basquete"])
]

USUARIOS_BASE = [
    ("Gustavo Sartori", "gustavo.sartori@fiap.com.br", "São Paulo"),
    ("Erik Naoki", "erik.naoki@fiap.com.br", "São Paulo"),
    ("Gutemberg Rocha", "gutemberg.rocha@fiap.com.br", "Rio de Janeiro"),
    ("João Henrique", "joao.henrique@fiap.com.br", "Belo Horizonte"),
    ("Juliana da Silva", "juliana.silva@fiap.com.br", "Curitiba"),
    ("Ana Clara Souza", "ana.souza@email.com", "São Paulo"),
    ("Bruno Oliveira", "bruno.oliveira@email.com", "Rio de Janeiro"),
    ("Carla Mendes", "carla.mendes@email.com", "Belo Horizonte"),
    ("Diego Ferreira", "diego.ferreira@email.com", "Porto Alegre"),
    ("Elisa Ribeiro", "elisa.ribeiro@email.com", "Curitiba"),
    ("Felipe Santos", "felipe.santos@email.com", "Salvador"),
    ("Gabriela Duarte", "gabriela.duarte@email.com", "São Paulo"),
    ("Henrique Lima", "henrique.lima@email.com", "Brasília"),
    ("Isabela Martins", "isabela.martins@email.com", "Campinas"),
    ("Lucas Santana", "lucas.santana@email.com", "Santos"),
    ("Mariana Costa", "mariana.costa@email.com", "São Paulo"),
    ("Nicolas Azevedo", "nicolas.azevedo@email.com", "Rio de Janeiro"),
    ("Otávio Rocha", "otavio.rocha@email.com", "Belo Horizonte"),
    ("Patrícia Gomes", "patricia.gomes@email.com", "Curitiba"),
    ("Renan Teixeira", "renan.teixeira@email.com", "Porto Alegre"),
    ("Sabrina Freitas", "sabrina.freitas@email.com", "Salvador"),
    ("Thiago Barros", "thiago.barros@email.com", "Brasília"),
    ("Vanessa Castro", "vanessa.castro@email.com", "São Paulo"),
    ("William Moraes", "william.moraes@email.com", "Rio de Janeiro"),
    ("Yasmin Farias", "yasmin.farias@email.com", "Curitiba"),
    ("Arthur Nogueira", "arthur.nogueira@email.com", "Belo Horizonte"),
    ("Beatriz Cardoso", "beatriz.cardoso@email.com", "São Paulo"),
    ("Caio Guimarães", "caio.guimaraes@email.com", "Salvador"),
    ("Débora Peixoto", "debora.peixoto@email.com", "Porto Alegre"),
    ("Eduardo Vianna", "eduardo.vianna@email.com", "Brasília")
]


def seed():
    random.seed(42)
    print("Iniciando rotina de Seed do TicketFlash...")

    # Limpeza de dados prévios e criação de índices
    for colecao in ("eventos", "usuarios", "pedidos"):
        db[colecao].drop()

    criar_indices()
    agora = datetime.now(timezone.utc)

    # 1. Criação dos Eventos
    eventos = []
    for i, (nome_ev, categoria, atracoes) in enumerate(EVENTOS_BASE):
        cidade, endereco = random.choice(CIDADES_LOCAIS)
        data_evento = agora + timedelta(days=random.randint(7, 180), hours=random.randint(18, 22))

        # Setores embutidos no documento de evento (Req. 1)
        modelos_setores = [
            ("Pista", round(random.uniform(90.0, 150.0), 2), random.randint(200, 500)),
            ("Pista Premium", round(random.uniform(220.0, 380.0), 2), random.randint(80, 200)),
            ("Camarote VIP", round(random.uniform(450.0, 750.0), 2), random.randint(30, 80)),
            ("Cadeira Superior", round(random.uniform(70.0, 110.0), 2), random.randint(150, 300))
        ]

        # Seleciona de 2 a 4 setores para este evento
        num_setores = random.randint(2, len(modelos_setores))
        setores_escolhidos = [
            {"nome": nome_s, "preco": preco, "capacidade": cap, "vendidos": 0}
            for nome_s, preco, cap in modelos_setores[:num_setores]
        ]

        evento_doc = {
            "_id": ObjectId(),
            "nome": nome_ev,
            "categoria": categoria,
            "data": data_evento,
            "local": {
                "cidade": cidade,
                "endereco": endereco
            },
            "atracoes": atracoes,
            "setores": setores_escolhidos
        }
        eventos.append(evento_doc)

    # 2. Criação dos Usuários (com unicidade de email)
    usuarios = []
    for nome, email, cidade in USUARIOS_BASE:
        data_cadastro = agora - timedelta(days=random.randint(10, 500))
        usuario_doc = {
            "_id": ObjectId(),
            "nome": nome,
            "email": email,
            "cidade": cidade,
            "dataCadastro": data_cadastro
        }
        usuarios.append(usuario_doc)

    # 3. Criação de Pedidos e atualização de ingressos vendidos
    pedidos = []
    for _ in range(80):
        evento = random.choice(eventos)
        usuario = random.choice(usuarios)
        setor = random.choice(evento["setores"])
        quantidade = random.randint(1, 4)

        # 80% confirmados, 10% cancelados, 10% pendentes
        status_pedido = random.choices(["confirmado", "cancelado", "pendente"], weights=[80, 10, 10])[0]

        if status_pedido == "confirmado":
            if setor["vendidos"] + quantidade > setor["capacidade"]:
                status_pedido = "cancelado"
            else:
                setor["vendidos"] += quantidade

        valor_total = round(quantidade * setor["preco"], 2)
        criado_em = agora - timedelta(days=random.randint(0, 45), hours=random.randint(1, 23))

        pedido_doc = {
            "usuarioId": usuario["_id"],
            "eventoId": evento["_id"],
            "setor": setor["nome"],
            "quantidade": quantidade,
            "valorTotal": valor_total,
            "status": status_pedido,
            "criadoEm": criado_em
        }
        pedidos.append(pedido_doc)

    # Inserção em lote no MongoDB
    db.eventos.insert_many(eventos)
    db.usuarios.insert_many(usuarios)
    db.pedidos.insert_many(pedidos)

    print(f"Seed concluído com sucesso:")
    print(f" - {len(eventos)} eventos criados")
    print(f" - {len(usuarios)} usuários criados")
    print(f" - {len(pedidos)} pedidos criados")


if __name__ == "__main__":
    seed()
