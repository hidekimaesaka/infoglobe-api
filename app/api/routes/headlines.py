from fastapi import APIRouter

from app.schemas.headline import Headline


router = APIRouter(tags=["headlines"])


HEADLINES = [
    Headline(
        region="Americas",
        title="Mercados acompanham indicadores economicos",
        summary="Investidores monitoram dados de inflacao, juros e atividade.",
    ),
    Headline(
        region="Europe",
        title="Lideres discutem energia e seguranca",
        summary="A pauta regional segue focada em infraestrutura e cooperacao.",
    ),
    Headline(
        region="Asia",
        title="Tecnologia impulsiona novos investimentos",
        summary="Empresas ampliam projetos em chips, IA e automacao.",
    ),
]


@router.get("/headlines", response_model=list[Headline])
def list_headlines() -> list[Headline]:
    return HEADLINES
