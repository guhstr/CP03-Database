import json
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, status

from app.config import settings
from app.db import db, r, oid, ser, invalidar_cache
from app.models import PedidoConfirmar
from app.routers.reservas import chave_reserva

router = APIRouter(prefix="/pedidos", tags=["Pedidos e Compra"])


@router.post("/confirmar", status_code=status.HTTP_201_CREATED, summary="Confirmar pedido com transição atômica (Req. 10 e Bônus)")
def confirmar_pedido(dados: PedidoConfirmar):
    """
    Req. 10 - Fluxo completo de confirmação de pedido:
    1. Verifica e remove atomicamente a reserva no Redis via GETDEL.
       - Se a reserva expirou (passaram os 10 minutos) ou não existe: retorna HTTP 410 (Gone).
    2. Realiza incremento atômico ($inc) de ingressos vendidos no MongoDB,
       assegurando no próprio filtro da query que a capacidade do setor não seja excedida.
       - Se esgotado: retorna HTTP 409 (Conflict).
    3. Persiste o documento do pedido com status 'confirmado'.
       - Inclui mecanismo de compensação (rollback) se a gravação do pedido falhar.
    4. Invalida a chave de cache do evento no Redis (pois a quantidade de vendidos mudou).
    5. Bônus Pub/Sub: publica o evento no canal 'pedidos:confirmados' para assinantes externos.
    """
    chave = chave_reserva(dados.usuarioId, dados.eventoId, dados.setor)
    user_oid = oid(dados.usuarioId)
    evento_oid = oid(dados.eventoId)

    # 1. Leitura e remoção atômica da reserva no Redis (GETDEL evita race condition / dupla confirmação)
    conteudo_reserva = r.getdel(chave)
    if conteudo_reserva is None:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Reserva expirada ou inexistente. Realize uma nova reserva."
        )

    reserva_info = json.loads(conteudo_reserva)
    qtd = reserva_info["quantidade"]
    preco_unitario = reserva_info["preco"]
    valor_total = round(qtd * preco_unitario, 2)

    # 2. Incremento atômico condicional no MongoDB com validação de capacidade embutida
    filtro_atomico = {
        "_id": evento_oid,
        "$expr": {
            "$anyElementTrue": {
                "$map": {
                    "input": "$setores",
                    "as": "s",
                    "in": {
                        "$and": [
                            {"$eq": ["$$s.nome", dados.setor]},
                            {"$lte": [{"$add": ["$$s.vendidos", qtd]}, "$$s.capacidade"]}
                        ]
                    }
                }
            }
        }
    }

    resultado_update = db.eventos.update_one(
        filtro_atomico,
        {"$inc": {"setores.$[s].vendidos": qtd}},
        array_filters=[{"s.nome": dados.setor}]
    )

    if resultado_update.modified_count == 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A capacidade máxima do setor foi atingida durante a confirmação."
        )

    # 3. Gravação definitiva do pedido
    doc_pedido = {
        "usuarioId": user_oid,
        "eventoId": evento_oid,
        "setor": dados.setor,
        "quantidade": qtd,
        "valorTotal": valor_total,
        "status": "confirmado",
        "criadoEm": datetime.now(timezone.utc)
    }

    try:
        res_pedido = db.pedidos.insert_one(doc_pedido)
        pedido_id = str(res_pedido.inserted_id)
    except Exception as exc:
        # Mecanismo de compensação: desfaz o incremento atômico no setor caso o insert falhe
        db.eventos.update_one(
            {"_id": evento_oid},
            {"$inc": {"setores.$[s].vendidos": -qtd}},
            array_filters=[{"s.nome": dados.setor}]
        )
        raise HTTPException(
            status_code=500,
            detail=f"Falha ao persistir pedido: {str(exc)}"
        )

    # 4. Invalidação do cache do evento no Redis (Req. 9)
    invalidar_cache(dados.eventoId)

    # 5. Bônus (+0,5): Publicação no canal Pub/Sub 'pedidos:confirmados'
    payload_notificacao = {
        "pedidoId": pedido_id,
        "usuarioId": dados.usuarioId,
        "eventoId": dados.eventoId,
        "setor": dados.setor,
        "quantidade": qtd,
        "valorTotal": valor_total,
        "dataConfirmacao": datetime.now(timezone.utc).isoformat()
    }
    r.publish(settings.CANAL_PUB_SUB, json.dumps(payload_notificacao))

    return {
        "pedidoId": pedido_id,
        "status": "confirmado",
        "valorTotal": valor_total,
        "quantidade": qtd,
        "mensagem": "Pedido confirmado com sucesso!"
    }
