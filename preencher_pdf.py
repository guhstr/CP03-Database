"""
Script utilitário para preenchimento automático do PDF da avaliação do Checkpoint 3.
Gera o PDF oficial preenchido com os dados do grupo e links de entrega.

Uso:
    python preencher_pdf.py
"""
import os
import pypdf

PDF_ORIGINAL = "Prova_MongoDB_Redis_Python_2TDSPG.pdf"
PDF_DESTINO = "Prova_MongoDB_Redis_Python_2TDSPG_Preenchida.pdf"

# Se o arquivo estiver dentro do subdiretório, busca no pai se necessário
if not os.path.exists(PDF_ORIGINAL) and os.path.exists(os.path.join("..", PDF_ORIGINAL)):
    PDF_ORIGINAL = os.path.join("..", PDF_ORIGINAL)

def preencher():
    reader = pypdf.PdfReader(PDF_ORIGINAL)
    writer = pypdf.PdfWriter()
    writer.append(reader)

    # Página 1: Integrantes do grupo
    writer.update_page_form_field_values(
        writer.pages[0],
        {
            "rm1": "561650",
            "nome1": "Gustavo Arthur Carvalho Sartori",
            "rm2": "565771",
            "nome2": "Erik Naoki",
            "rm3": "562267",
            "nome3": "Gutemberg Rocha",
            "rm4": "564361",
            "nome4": "João Henrique",
            "rm5": "561171",
            "nome5": "Juliana da Silva"
        }
    )

    # Página 5: Links e observações
    writer.update_page_form_field_values(
        writer.pages[4],
        {
            "link_repositorio": "https://github.com/guhstr/CP03-Database",
            "link_video": "https://www.youtube.com/watch?v=SEU_LINK_AQUI",
            "observacoes": "Projeto completo com FastAPI, MongoDB e Redis. Atende a todos os requisitos e bônus Pub/Sub."
        }
    )

    with open(PDF_DESTINO, "wb") as f:
        writer.write(f)

    print(f"[OK] PDF preenchido gerado com sucesso: {PDF_DESTINO}")

if __name__ == "__main__":
    preencher()
