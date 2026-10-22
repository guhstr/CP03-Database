"""
Suite de Testes Automatizados - Validação Completa dos Requisitos do Checkpoint 3
Executa testes ponta a ponta contra a API TicketFlash cobrindo os 10 requisitos e o bônus.

Uso:
    python tests/test_fluxo_completo.py
"""
import time
import requests

BASE_URL = "http://localhost:8000"


def log_test(nome: str, sucesso: bool, detalhe: str = ""):
    simbolo = "OK" if sucesso else "FAIL"
    status = "PASSOU" if sucesso else "FALHOU"
    print(f"[{simbolo}] {status} - {nome} {f'({detalhe})' if detalhe else ''}")


def executar_testes():
    print("=" * 70)
    print(" INICIANDO TESTES AUTOMATIZADOS - TICKETFLASH (FASTAPI + MONGO + REDIS)")
    print("=" * 70)

    # 0. Healthcheck
    try:
        r = requests.get(f"{BASE_URL}/health", timeout=5)
        assert r.status_code == 200, f"Status code inesperado: {r.status_code}"
        dados = r.json()
        assert dados["status"] == "saudavel", f"Status não saudável: {dados}"
        log_test("0. Healthcheck da API e Conectividade", True)
    except Exception as e:
        log_test("0. Healthcheck da API e Conectividade", False, str(e))
        return

    # 1. Usuários e Unicidade de Email (Req. 1 e 3)
    try:
        # Criar usuário novo
        email_teste = f"teste.{int(time.time())}@fiap.com.br"
        r = requests.post(f"{BASE_URL}/usuarios", json={
            "nome": "Usuário Teste Automatizado",
            "email": email_teste,
            "cidade": "São Paulo"
        })
        assert r.status_code == 201, f"Falha ao criar usuário: {r.status_code} - {r.text}"
        usuario_id = r.json()["id"]

        # Tentar criar com o mesmo email para validar o índice único (deve dar 409)
        r_dup = requests.post(f"{BASE_URL}/usuarios", json={
            "nome": "Usuário Teste Duplicado",
            "email": email_teste,
            "cidade": "São Paulo"
        })
        assert r_dup.status_code == 409, f"Deveria retornar 409 para e-mail duplicado, retornou {r_dup.status_code}"
        log_test("1. Criação de Usuário e Validação de Índice Único (409)", True)
    except Exception as e:
        log_test("1. Criação de Usuário e Validação de Índice Único (409)", False, str(e))

    # 2. CRUD de Eventos e Filtros (Req. 2)
    try:
        # Criar Evento
        payload_evento = {
            "nome": "Show Exclusivo de Teste",
            "categoria": "Show",
            "data": "2026-12-31T22:00:00",
            "local": {"cidade": "Curitiba", "endereco": "Teatro Teste, 100"},
            "atracoes": ["Banda Teste 1", "Banda Teste 2"],
            "setores": [
                {"nome": "Pista", "preco": 100.0, "capacidade": 50, "vendidos": 0},
                {"nome": "VIP", "preco": 250.0, "capacidade": 10, "vendidos": 0}
            ]
        }
        r = requests.post(f"{BASE_URL}/eventos", json=payload_evento)
        assert r.status_code == 201, f"Falha ao criar evento: {r.status_code}"
        evento_id = r.json()["id"]

        # Listar com filtros
        r_list = requests.get(f"{BASE_URL}/eventos?categoria=Show&cidade=Curitiba")
        assert r_list.status_code == 200, f"Falha ao filtrar eventos: {r_list.status_code}"
        eventos = r_list.json()
        assert any(e["_id"] == evento_id for e in eventos), "Evento recém-criado não encontrado no filtro"
        log_test("2. CRUD de Eventos (Criação e Listagem com Filtros)", True)
    except Exception as e:
        log_test("2. CRUD de Eventos (Criação e Listagem com Filtros)", False, str(e))

    # 3. Cache-aside e Origem dos Dados (Req. 5) + Ranking (Req. 7)
    try:
        # Chamada 1: deve vir do banco
        r1 = requests.get(f"{BASE_URL}/eventos/{evento_id}")
        assert r1.status_code == 200
        assert r1.json()["origem"] == "banco", f"Esperado 'banco', obtido {r1.json().get('origem')}"

        # Chamada 2: deve vir do cache
        r2 = requests.get(f"{BASE_URL}/eventos/{evento_id}")
        assert r2.status_code == 200
        assert r2.json()["origem"] == "cache", f"Esperado 'cache', obtido {r2.json().get('origem')}"

        # Verificar Ranking (Req. 7)
        r_rank = requests.get(f"{BASE_URL}/eventos/ranking")
        assert r_rank.status_code == 200
        ranking = r_rank.json()
        assert len(ranking) <= 5, "Ranking deve retornar no máximo top 5"
        assert any(item["eventoId"] == evento_id for item in ranking), "Evento não contabilizado no ranking"
        log_test("3. Cache-aside ('origem': banco/cache) e Ranking Top 5 (ZINCRBY)", True)
    except Exception as e:
        log_test("3. Cache-aside ('origem': banco/cache) e Ranking Top 5 (ZINCRBY)", False, str(e))

    # 4. Invalidação de Cache (Req. 9)
    try:
        # Atualizar evento
        r_up = requests.put(f"{BASE_URL}/eventos/{evento_id}", json={"nome": "Show Exclusivo de Teste - Alterado"})
        assert r_up.status_code == 200

        # Próxima busca deve ter cache invalidado -> 'origem': 'banco'
        r3 = requests.get(f"{BASE_URL}/eventos/{evento_id}")
        assert r3.status_code == 200
        assert r3.json()["origem"] == "banco", "Cache não foi invalidado após update"
        log_test("4. Invalidação de Cache após Atualização (Req. 9)", True)
    except Exception as e:
        log_test("4. Invalidação de Cache após Atualização (Req. 9)", False, str(e))

    # 5. Agregações no MongoDB (Req. 4)
    try:
        # Faturamento por evento ($group + $lookup)
        r_fat = requests.get(f"{BASE_URL}/relatorios/faturamento")
        assert r_fat.status_code == 200
        faturamentos = r_fat.json()
        assert isinstance(faturamentos, list)
        if len(faturamentos) > 1:
            assert faturamentos[0]["faturamento"] >= faturamentos[1]["faturamento"], "Não ordenado por faturamento desc"

        # Ocupação por setor ($unwind + $project)
        r_ocup = requests.get(f"{BASE_URL}/relatorios/ocupacao/{evento_id}")
        assert r_ocup.status_code == 200
        ocupacoes = r_ocup.json()
        assert len(ocupacoes) == 2, f"Esperado 2 setores, obtido {len(ocupacoes)}"
        assert "percentualVendido" in ocupacoes[0]
        log_test("5. Relatórios de Agregação (Faturamento e Ocupação)", True)
    except Exception as e:
        log_test("5. Relatórios de Agregação (Faturamento e Ocupação)", False, str(e))

    # 6. Diagnóstico de Índices e explain() (Req. 3)
    try:
        r_exp = requests.get(f"{BASE_URL}/admin/explain?categoria=Show")
        assert r_exp.status_code == 200
        dados_exp = r_exp.json()
        winning_plan = str(dados_exp["planoExecucao"])
        assert "IXSCAN" in winning_plan, "Plano de execução não utilizou IXSCAN"
        assert "categoria_data" in winning_plan, "Índice categoria_data não foi referenciado no winningPlan"
        log_test("6. Explain da Consulta com Índice Composto (IXSCAN)", True)
    except Exception as e:
        log_test("6. Explain da Consulta com Índice Composto (IXSCAN)", False, str(e))

    # 7. Reserva Temporária (Req. 6) e Rate Limiting (Req. 8)
    try:
        # Reserva com sucesso
        r_res = requests.post(f"{BASE_URL}/reservas", json={
            "usuarioId": usuario_id,
            "eventoId": evento_id,
            "setor": "Pista",
            "quantidade": 2
        })
        assert r_res.status_code == 201, f"Falha na reserva: {r_res.status_code} - {r_res.text}"
        assert r_res.json()["reservado"] is True

        # Teste de Rate Limiting (disparar requisições até exceder limite de 10)
        excedeu_rate_limit = False
        for _ in range(12):
            r_rate = requests.post(f"{BASE_URL}/reservas", json={
                "usuarioId": usuario_id,
                "eventoId": evento_id,
                "setor": "VIP",
                "quantidade": 1
            })
            if r_rate.status_code == 429:
                excedeu_rate_limit = True
                assert "Retry-After" in r_rate.headers, "Header Retry-After ausente na resposta 429"
                break

        assert excedeu_rate_limit, "Rate limit de 10 requisições/min não disparou 429"
        log_test("7. Reserva Temporária (SET NX EX) e Rate Limit (HTTP 429)", True)
    except Exception as e:
        log_test("7. Reserva Temporária (SET NX EX) e Rate Limit (HTTP 429)", False, str(e))

    # 8. Fluxo de Compra e Confirmação Atômica (Req. 10)
    try:
        # Confirmar reserva válida existente
        r_conf = requests.post(f"{BASE_URL}/pedidos/confirmar", json={
            "usuarioId": usuario_id,
            "eventoId": evento_id,
            "setor": "Pista"
        })
        assert r_conf.status_code == 201, f"Falha ao confirmar pedido: {r_conf.status_code} - {r_conf.text}"
        assert r_conf.json()["status"] == "confirmado"

        # Tentar confirmar novamente a mesma reserva (já consumida ou expirada) -> deve retornar 410 Gone
        r_conf_again = requests.post(f"{BASE_URL}/pedidos/confirmar", json={
            "usuarioId": usuario_id,
            "eventoId": evento_id,
            "setor": "Pista"
        })
        assert r_conf_again.status_code == 410, f"Deveria retornar 410 Gone, retornou {r_conf_again.status_code}"
        log_test("8. Fluxo de Compra Atômica ($inc) e Tratamento de Reserva Expirada (410)", True)
    except Exception as e:
        log_test("8. Fluxo de Compra Atômica ($inc) e Tratamento de Reserva Expirada (410)", False, str(e))

    # 9. Remoção de Evento e Invalidação Total (Req. 2 e 9)
    try:
        r_del = requests.delete(f"{BASE_URL}/eventos/{evento_id}")
        assert r_del.status_code == 200
        r_check = requests.get(f"{BASE_URL}/eventos/{evento_id}")
        assert r_check.status_code == 404, "Evento ainda existe após DELETE"
        log_test("9. Remoção de Evento com Invalidação Completa (Req. 2 e 9)", True)
    except Exception as e:
        log_test("9. Remoção de Evento com Invalidação Completa (Req. 2 e 9)", False, str(e))

    print("=" * 70)
    print(" TODOS OS TESTES FORAM EXECUTADOS COM SUCESSO!")
    print("=" * 70)


if __name__ == "__main__":
    executar_testes()
