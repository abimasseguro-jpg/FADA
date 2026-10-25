from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "governanca/relatorios/FLUXOGRAMA_DECISAO_OCUPAR_OU_AGUARDAR_2026-08-06.png"
W, H = 1500, 1900
img = Image.new("RGB", (W, H), "white")
d = ImageDraw.Draw(img)
font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
bold_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
F = lambda n: ImageFont.truetype(font_path, n)
B = lambda n: ImageFont.truetype(bold_path, n)

def center(text, xy, font, fill="#0f172a"):
    box=d.multiline_textbbox((0,0),text,font=font,spacing=8,align="center")
    d.multiline_text((xy[0]-(box[2]-box[0])/2,xy[1]-(box[3]-box[1])/2),text,font=font,fill=fill,spacing=8,align="center")
def box(x1,y1,x2,y2,text,fill,outline="#2563eb",font=None):
    d.rounded_rectangle((x1,y1,x2,y2),radius=24,fill=fill,outline=outline,width=5)
    center(text,((x1+x2)//2,(y1+y2)//2),font or F(27))
def arrow(x1,y1,x2,y2,color="#334155"):
    d.line((x1,y1,x2,y2),fill=color,width=5)
    import math
    a=math.atan2(y2-y1,x2-x1); L=22
    p1=(x2-L*math.cos(a-0.45),y2-L*math.sin(a-0.45)); p2=(x2-L*math.cos(a+0.45),y2-L*math.sin(a+0.45))
    d.polygon([(x2,y2),p1,p2],fill=color)

center("ESCALONAMENTO ADAPTATIVO MVHSN",(W//2,55),B(38))
center("Decisão: ocupar o worker ou aguardar?",(W//2,100),F(27),"#475569")
box(300,150,1200,270,"Worker s ficou livre\ne existem tarefas pendentes?","#f1f5f9","#475569",B(27))
arrow(750,270,750,325)
box(230,325,1270,455,"Atualizar estado\nQ, tarefas em execução, leases e carga restante Lₛ","#ecfdf5","#16a34a")
arrow(750,455,750,510)
box(180,510,1320,650,"Estimar custos\nĈ(k) por cenário · mᵢ por complexidade · vₛ por worker","#ecfdf5","#16a34a")
arrow(750,650,750,705)
box(150,705,1350,850,"Selecionar candidatos\nn50, n100, n200 e n400; priorizar tarefas pesadas","#eff6ff","#2563eb")
arrow(750,850,750,905)
box(120,905,1380,1080,"Para cada tarefa i, simular a atribuição ao worker s\np̂ᵢₛ = Ĉ(kᵢ) · mᵢ / vₛ\ne redistribuir o restante por menor término previsto","#eff6ff","#2563eb",F(25))
arrow(750,1080,750,1135)
box(250,1135,1250,1265,"Calcular makespan previsto\nT̂(i→s) = maxᵣ L′ᵣ","#eff6ff","#2563eb",B(28))
arrow(750,1265,750,1320)
d.polygon([(750,1320),(1080,1490),(750,1660),(420,1490)],fill="#fff7ed",outline="#ea580c",width=5)
center("O melhor candidato\nreduz o término em\nmais que ε?",(750,1490),B(28),"#7c2d12")
arrow(420,1490,210,1490); center("NÃO",(320,1455),B(22),"#dc2626")
box(35,1400,385,1580,"Aguardar até\no próximo evento\nde conclusão","#f1f5f9","#475569",F(24))
arrow(1080,1490,1290,1490); center("SIM",(1180,1455),B(22),"#16a34a")
box(1115,1400,1465,1580,"Despachar a tarefa\ni para o worker s","#f0fdf4","#16a34a",F(24))
arrow(210,1580,210,1740); arrow(1290,1580,1290,1740)
box(410,1740,1090,1840,"Registrar tempo observado e atualizar o modelo","#ecfdf5","#16a34a",F(25))
center("ε = margem de segurança contra erro de previsão",(W//2,1870),F(21),"#475569")
img.save(OUT, "PNG", optimize=True)
print(OUT)
