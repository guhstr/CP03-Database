"""
Bônus: Assinante do Canal Redis Pub/Sub 'pedidos:confirmados'
Escuta notificações em tempo real sempre que um pedido for confirmado na plataforma.

Uso:
    docker compose exec api python subscriber.py
    (ou localmente: python subscriber.py)
"""
import sys
import json
from datetime import datetime

from app.config import settings
from app.db import r


def iniciar_subscriber():
    canal = settings.CANAL_PUB_SUB
    pubsub = r.pubsub()
    pubsub.subscribe(canal)

    print("=" * 70, flush=True)
    print(f"[*] Assinante Redis Pub/Sub inicializado com sucesso!", flush=True)
    print(f"[*] Escutando eventos no canal: '{canal}'", flush=True)
    print(f"[*] Pressione Ctrl+C para encerrar o assinante.", flush=True)
    print("=" * 70, flush=True)

    try:
        for mensagem in pubsub.listen():
            if mensagem["type"] == "message":
                dados_raw = mensagem["data"]
                try:
                    payload = json.loads(dados_raw)
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    print(
                        f"\n[{timestamp}] >>> NOVO PEDIDO CONFIRMADO <<<\n"
                        f"  - Pedido ID:    {payload.get('pedidoId')}\n"
                        f"  - Usuário ID:   {payload.get('usuarioId')}\n"
                        f"  - Evento ID:    {payload.get('eventoId')}\n"
                        f"  - Setor:        {payload.get('setor')}\n"
                        f"  - Quantidade:   {payload.get('quantidade')}\n"
                        f"  - Valor Total:  R$ {payload.get('valorTotal'):.2f}\n"
                        f"  --------------------------------------------------",
                        flush=True
                    )
                except Exception:
                    print(f"[MENSAGEM BRUTA] {dados_raw}", flush=True)
    except KeyboardInterrupt:
        print("\n[*] Assinante encerrado pelo usuário.", flush=True)
        sys.exit(0)


if __name__ == "__main__":
    iniciar_subscriber()
