# Ritmo de venta por modelo y estado. Uso: python3 -I ritmo.py  -> escribe ritmo.json e imprime filas para la hoja
import json,os,statistics as st,time
D=os.path.dirname(os.path.abspath(__file__))
vh=json.load(open(os.path.join(D,'ventas_hist.json')))
act=json.load(open(os.path.join(D,'activos.json')))
now=time.time()
def fd(x): return '–' if x is None else f'{x:g} d'
def med(x): return round(st.median(x),1) if x else None
def pct(x,f): return round(100*sum(1 for v in x if f(v))/len(x)) if x else None
g={}
for v in vh.values(): g.setdefault((v['modelo'],v['estado']),{'v':[],'a':[]})['v'].append(v)
for a in act: g.setdefault((a['modelo'],a['estado']),{'v':[],'a':[]})['a'].append(a)
out={};filas=[]
for (m,e),d in sorted(g.items()):
    V=d['v'];A=d['a']
    precios=sorted(v['precio'] for v in V); dias=[v['dias'] for v in V if v['dias'] is not None]
    n=len(V)
    act_d=[(now-time.mktime(time.strptime(a['publicado'],'%Y-%m-%d')))/86400 for a in A]
    estanc=sum(1 for x in act_d if x>30)
    r=dict(modelo=m,estado=e,vendidas=n,precio_med=med(precios),dias_med=med(dias),
           pct_3d=pct(dias,lambda x:x<=3),pct_7d=pct(dias,lambda x:x<=7),activos=len(A),estancados=estanc,
           activos_precio_med=med([float(a['precio']) for a in A]))
    # dias segun tramo de precio (tercio barato / medio / caro de lo vendido)
    if n>=6:
        c1,c2=precios[n//3],precios[(2*n)//3]
        r['corte_barato'],r['corte_caro']=c1,c2
        for k,f in (('dias_barato',lambda p:p<c1),('dias_medio',lambda p:c1<=p<=c2),('dias_caro',lambda p:p>c2)):
            r[k]=med([v['dias'] for v in V if v['dias'] is not None and f(v['precio'])])
    # favoritos / visitas: vendidos vs activos que llevan >14 dias (regla ~10 %)
    def ratio(L): 
        L=[x for x in L if (x.get('visitas') or 0)>=20 and x.get('favs') is not None]
        return round(100*st.median([x['favs']/x['visitas'] for x in L]),1) if L else None
    r['fav_vis_vendidos']=ratio(V)
    r['fav_vis_estancados']=ratio([a for a,x in zip(A,act_d) if x>14])
    # rotacion: ventas/dia en el periodo observado vs oferta activa
    if n:
        dias_obs=max(1,(now-min(time.mktime(time.strptime(v['fecha'],'%Y-%m-%d')) for v in V))/86400)
        r['ventas_dia']=round(n/dias_obs,2)
    if n>=3 and dias:
        rap='muy rápido' if r['dias_med']<=2 else 'rápido' if r['dias_med']<=5 else 'normal' if r['dias_med']<=14 else 'lento'
        r['resumen']=(f"{rap}: se vende en ~{r['dias_med']:g} días a ~{r['precio_med']:g} € ({n} ventas, {r['pct_3d']}% en ≤3 días)").replace('.',',')
    else:
        r['resumen']=f"pocos datos ({n} ventas registradas)"
    if estanc and len(A): r['resumen']+=f"; {estanc} de {len(A)} anuncios llevan >30 días"
    out[f'{m}|{e}']=r
    filas.append([m,e,n,r['precio_med'] or '',r['dias_med'] if r['dias_med'] is not None else '',r['pct_3d'] if r['pct_3d'] is not None else '',
                  r['pct_7d'] if r['pct_7d'] is not None else '',
                  (f"<{r['corte_barato']:g} €: {fd(r['dias_barato'])} · medio: {fd(r['dias_medio'])} · >{r['corte_caro']:g} €: {fd(r['dias_caro'])}").replace('.',',') if 'corte_barato' in r else '',
                  len(A),estanc,r['activos_precio_med'] or '',r.get('ventas_dia',''),
                  r['fav_vis_vendidos'] if r['fav_vis_vendidos'] is not None else '',r['fav_vis_estancados'] if r['fav_vis_estancados'] is not None else '',r['resumen']])
json.dump(out,open(os.path.join(D,'ritmo.json'),'w'),ensure_ascii=False,indent=0)
filas.sort(key=lambda f:-f[2])
print(json.dumps(filas,ensure_ascii=False))
