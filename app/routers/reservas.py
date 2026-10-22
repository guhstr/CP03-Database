import json
from fastapi import APIRouter, HTTPException, status, Response

from app.config import settings
from app.db import db, r, oid
from app.models import ReservaCreate

router = APIRouter(prefix="/reservas", tags=["Reservas e Rate Limit"])


def chave_reserva(usuario_id: str, evento_id: str, setor: str) -> str:
    """Padronização da chave de reserva temporária no Redis."""
    return f"reserva:{usuario_id}:{evento_id}:{setor}"


def verificar_rate_limit(usuario_id: str):
    """
    Req. 8: Limite de requisições por usuário.
    Estrutura Redis: String com INCR + EXPIRE.
    Máximo de 10 reservas por minuto por usuário; acima disso a API responde 429 com cabeçalho Retry-After.
    """
    key = f"limite:reservas:{usuario_id}"
    total = r.incr(key)

    # Se for o primeiro incremento na chave, define a janela de expiração de 60 segundos
    if r.ttl(key) == -1:
        r.expire(key, settings.JANELA_LIMITE)

    if total > settings.LIMITE_RESERVAS:
        ttl_restante = max(r.ttl(key), 1)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Limite de {settings.LIMITE_RESERVAS} reservas por minuto excedido. Aguarde antes de tentar novamente.",
            headers={"Retry-After": str(ttl_restante)}
        )


@router.post("", status_code=status.HTTP_201_CREATED, summary="Criar reserva temporária (Req. 6, 8 e 10)")
def criar_reserva(reserva: ReservaCreate):
    """
    Fluxo de reserva (Requisitos 6, 8 e 10):
    1. Verifica rate limit do usuário (Req. 8: máx 10 por minuto -> 429).
    2. Valida existência do usuário no MongoDB.
    3. Confere no MongoDB se o evento e o setor existem.
    4. Checa disponibilidade de vagas (capacidade - vendidos >= quantidade).
    5. Cria a reserva no Redis via SET NX EX 600s (Req. 6: expiração automática em 10 minutos).
    """
    # 1. Rate Limiting
    verificar_rate_limit(reserva.usuarioId)

    # 2. Validação do Usuário
    usuario = db.usuarios.find_one({"_id": oid(reserva.usuarioId)}, {"_id": 1})
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")

    # 3. Validação do Evento e Setor
    evento = db.eventos.find_one({"_id": oid(reserva.eventoId)})
    if not evento:
        raise HTTPException(status_code=404, detail="Evento não encontrado")

    setor_alvo = next((s for s in evento.get("setores", []) if s["nome"] == reserva.setor), None)
    if not setor_alvo:
        raise HTTPException(status_code=404, detail=f"Setor '{reserva.setor}' não encontrado neste evento")

    # 4. Checagem de Vagas
    vagas_disponiveis = setor_alvo["capacidade"] - setor_alvo.get("vendidos", 0)
    if vagas_disponiveis < reserva.quantidade:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Setor sem vagas suficientes (disponíveis: {vagas_disponiveis}, solicitadas: {reserva.quantidade})"
        )

    # 5. Criação da reserva temporária atômica no Redis (SET NX EX)
    chave = chave_reserva(reserva.usuarioId, reserva.eventoId, reserva.setor)
    dados_reserva = json.dumps({
        "quantidade": reserva.quantidade,
        "preco": setor_alvo["preco"]
    })

    sucesso = r.set(chave, dados_reserva, nx=True, ex=settings.RESERVA_TTL)
    if not sucesso:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Já existe uma reserva ativa pendente para este usuário neste setor"
        )

    return {
        "reservado": True,
        "expiraEmSegundos": settings.RESERVA_TTL,
        "chaveRedis": chave,
        "mensagem": f"Ingressos bloqueados por 10 minutos. Confirme o pedido antes da expiração."
    }
