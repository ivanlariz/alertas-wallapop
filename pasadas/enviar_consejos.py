"""Envía fichas revisadas a mano por el bot de GitHub (mismo formato con foto + Telegram).
Uso: python3 -I enviar_consejos.py fichas.json
fichas.json = {"asunto": "...", "intro": "...", "fichas": [{"titulo","url","img","precio","envio","ciudad","cabecera",
               "lineas": [["Estado en fotos","..."],["Vendedor","..."],["Referencia","..."],["Números","..."],["Señales","..."]],
               "avisos": ["..."], "veredicto": "COMPRAR / OFRECER X € / VERIFICAR ..."}]}
"""
import json, subprocess, sys
datos = json.load(open(sys.argv[1]))
txt = json.dumps(datos, ensure_ascii=False, separators=(',', ':'))
if len(txt) > 60000:
    sys.exit('Demasiado largo para el bot; envíalo por Gmail')
r = subprocess.run(['gh', 'api', '-X', 'POST', 'repos/ivanlariz/alertas-wallapop/actions/workflows/alertas.yml/dispatches',
                    '-f', 'ref=main', '-f', f'inputs[consejos]={txt}'], capture_output=True, text=True)
print('OK enviado al bot' if r.returncode == 0 else 'ERROR ' + r.stderr)
sys.exit(r.returncode)
