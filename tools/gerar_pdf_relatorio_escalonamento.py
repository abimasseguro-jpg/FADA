from pathlib import Path
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer

out = Path(__file__).resolve().parents[1] / "governanca/relatorios/RELATORIO_CONCLUSOES_ESCALONAMENTO_DINAMICO_2026-08-06.pdf"
styles = getSampleStyleSheet()
styles.add(ParagraphStyle(name="TitleCenter", parent=styles["Title"], alignment=TA_CENTER, fontSize=16, leading=20, spaceAfter=16))
styles.add(ParagraphStyle(name="Small", parent=styles["BodyText"], fontSize=9, leading=12))
doc = SimpleDocTemplate(str(out), pagesize=A4, rightMargin=2*cm, leftMargin=2*cm, topMargin=1.8*cm, bottomMargin=1.8*cm)
story = []
sections = [
("1. Resultado do estudo", "A equação original é matematicamente consistente como modelo de minimização do makespan. Ela é superior a uma ETA baseada apenas em médias porque considera tarefas pendentes, tarefas em execução, velocidades diferentes e a possibilidade de aguardar."),
("2. Limitação identificada", "A solução exata exigiria reotimizar uma alocação heterogênea de centenas de tarefas a cada liberação. Isso é caro e pouco necessário para a operação. Além disso, os custos das tarefas não são determinísticos."),
("3. Fórmula recomendada", "Cada worker é tratado como um slot independente. Para a tarefa i no worker s, o tempo previsto é: p̂(i,s) = Ĉ(kᵢ) · mᵢ / vₛ. Ĉ(kᵢ) é o custo aprendido do cenário; mᵢ representa a complexidade observada da tarefa; e vₛ é a velocidade histórica do worker."),
("4. Decisão operacional", "Quando um worker fica livre, o coordenador avalia uma janela de candidatos. Para cada candidato, simula uma distribuição gulosa das tarefas restantes e calcula: T̂(i→s) = maxᵣ Lᵣ′. A tarefa escolhida é a que minimiza T̂(i→s). A máquina só permanece ociosa quando esperar produz ganho maior que a margem de erro da previsão."),
("5. Melhorias incorporadas", "O modelo recomendado diferencia n50, n100, n200 e n400; aprende com tempos reais; trata workers individualmente; considera iterações ECM e fallbacks; limita a busca a candidatos relevantes; usa margem de segurança; e mantém fallback para a política atual quando há poucos dados."),
("6. Exclusão deliberada", "Temperatura, clock e carga térmica não fazem parte desta versão, conforme decisão do projeto. A velocidade será aprendida exclusivamente do histórico de execução e da capacidade observada dos workers."),
("7. Validação necessária", "Ainda não é possível afirmar um percentual de ganho sem backtest. A comparação deve medir makespan, erro da ETA, tempo ocioso, vazão por cenário, equilíbrio entre n50–n400, reexecuções e leases expirados."),
("8. Parecer final", "A proposta deve ser aprovada como base de evolução, mas implementada como heurística adaptativa por worker, cenário e custo aprendido, com horizonte móvel, margem de segurança e fallback. Essa versão preserva a robustez da fila e permite medir o ganho antes de alterar o coordenador em produção."),
]
story.append(Paragraph("Relatório de conclusões — escalonamento dinâmico de tarefas", styles["TitleCenter"]))
story.append(Paragraph("MVHSN · 06/08/2026", styles["Small"]))
story.append(Spacer(1, 12))
for heading, body in sections:
    story.append(Paragraph(heading, styles["Heading2"]))
    story.append(Paragraph(body, styles["BodyText"]))
    story.append(Spacer(1, 8))
doc.build(story)
print(out)
