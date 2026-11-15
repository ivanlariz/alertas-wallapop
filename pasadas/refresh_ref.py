# Actualiza ventas reales (valoraciones nuevas) y anuncios activos de los revendedores y reconstruye ref.json
# Uso: python3 -I refresh_ref.py   (desde la carpeta sched; datos en ../resell/sold y ../resell/active)
import json,os,subprocess,sys
D=os.path.dirname(os.path.abspath(__file__)); R=os.path.join(D,'..','resell')
os.makedirs(os.path.join(R,'sold'),exist_ok=True); os.makedirs(os.path.join(R,'active'),exist_ok=True)
P=json.load(open(os.path.join(D,'profiles.json')))
nuevas=0
for p in P:
    if not p.get('id'): continue
    fn=os.path.join(R,'sold',p['slug']+'.json'); tmp=fn+'.new'
    pages='2' if os.path.exists(fn) else '25'
    subprocess.run([sys.executable,'-I',os.path.join(D,'reviews_sold.py'),p['id'],tmp,pages],capture_output=True,timeout=900)
    if not os.path.exists(tmp): continue
    new=json.load(open(tmp)); old=json.load(open(fn)) if os.path.exists(fn) else []
    ids={x['id'] for x in old}; add=[x for x in new if x['id'] not in ids]; nuevas+=len(add)
    json.dump(add+old,open(fn,'w'),ensure_ascii=False); os.remove(tmp)
subprocess.run([sys.executable,'-I',os.path.join(D,'fetch_active.py'),os.path.join(D,'profiles.json'),os.path.join(R,'active')],capture_output=True,timeout=3600)
r=subprocess.run([sys.executable,'-I',os.path.join(D,'build_ref.py'),os.path.join(R,'sold'),os.path.join(R,'active'),os.path.join(D,'ref.json')],capture_output=True,text=True)
print('ventas nuevas',nuevas,'|',r.stdout.strip())
