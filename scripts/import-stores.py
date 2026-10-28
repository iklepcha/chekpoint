"""Fetch official store data. Run manually; no fabricated prices or inferred regional offers."""
import json,re,time,html,urllib.request,urllib.error,xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime,timezone
from zoneinfo import ZoneInfo
ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/'dist/catalog.json'; NOW=datetime.now(timezone.utc).isoformat()
def get(url):
 for attempt in range(3):
  try:
   req=urllib.request.Request(url,headers={'User-Agent':'Checkpoint/0.1 (game price research)','Accept':'application/json,text/html,*/*'})
   with urllib.request.urlopen(req,timeout=30) as r:return r.read()
  except urllib.error.HTTPError as e:
   if e.code==429:
    if attempt==2:raise
    time.sleep(max(60,int(e.headers.get("Retry-After","60"))))
   elif attempt==2:raise
   else:time.sleep(2**attempt)
  except Exception:
   if attempt==2:raise
   time.sleep(2**attempt)
def plain(x):return html.unescape(re.sub('<[^>]+>',' ',x or '')).strip()
def walk(x):
 if isinstance(x,dict):
  yield x
  for v in x.values():yield from walk(v)
 elif isinstance(x,list):
  for v in x:yield from walk(v)
old=json.loads(OUT.read_text()) if OUT.exists() else {}; history=old.get('history',[]); games={}; errors=[]
fxurl='https://www.cbr.ru/scripts/XML_daily.asp?date_req='+datetime.now(ZoneInfo('Europe/Moscow')).strftime('%d/%m/%Y')
fxxml=ET.fromstring(get(fxurl)); rates={'RUB':1}
for v in fxxml.findall('Valute'):rates[v.findtext('CharCode')]=float(v.findtext('Value').replace(',','.'))/float(v.findtext('Nominal'))
regions=[('US','США'),('PL','Польша'),('TR','Турция'),('JP','Япония'),('BR','Бразилия')]
def offer(g,store,region,amount,currency,url,discount=None,initial=None):
 if amount<0 or currency not in rates:raise ValueError('Invalid price/currency')
 o={'store':store,'region':region,'amount':amount,'currency':currency,'rub':round(amount*rates[currency],2),'usd':round(amount*rates[currency]/rates['USD'],2),'url':url,'checkedAt':NOW,'discount':discount,'initial':initial}
 g['offers'].append(o)
 history.append({'game':g['id'],**o})
apps=[('hades2',1145350),('hades',1145360),('cyberpunk',1091500),('hollow',367520),('elden',1245620),('forza',1551360),('stardew',413150),('dead-cells',588650),('baldurs-gate',1086940),('disco',632470),('celeste',504230),('dave',1868140)]
apps += [('witcher3',292030),('rdr2',1174180),('hogwarts',990080),('god-of-war',1593500),('spider-man',1817070),('sekiro',814380),('dark-souls3',374320),('re4',2050650),('re-village',1196590),('doom-eternal',782330),('it-takes-two',1426210),('terraria',105600),('portal2',620),('left4dead2',550),('no-mans-sky',275850),('subnautica',264710),('valheim',892970),('rust',252490),('palworld',1623730),('helldivers2',553850),('monster-hunter-world',582010),('death-stranding',1850570),('control',870780),('cuphead',268910),('ori',1057090),('slay-the-spire',646570),('vampire-survivors',1794680),('cult-of-the-lamb',1313140),('stray',1332010),('deep-rock',548430)]
for gid,appid in apps:
 for region,_ in regions:
  api=f'https://store.steampowered.com/api/appdetails?appids={appid}&cc={region.lower()}&l=russian'
  try:
   item=json.loads(get(api))[str(appid)]
   if not item.get('success'):raise ValueError('Store did not return product')
   d=item['data'];p=d.get('price_overview');g=games.setdefault(gid,{'id':gid,'name':d['name'],'description':plain(d.get('short_description')),'image':d['header_image'],'genre':' · '.join(x['description'] for x in d.get('genres',[])),'developer':', '.join(d.get('developers',[])),'release':d.get('release_date',{}).get('date'),'metadataSource':f'https://store.steampowered.com/app/{appid}/','offers':[]})
   if p:offer(g,'Steam',region,p['final']/100,p['currency'],f'https://store.steampowered.com/app/{appid}/?cc={region.lower()}',p['discount_percent'],p['initial']/100)
   elif d.get('is_free'):offer(g,'Steam',region,0,'USD',f'https://store.steampowered.com/app/{appid}/?cc={region.lower()}',0)
   else:errors.append({'store':'Steam','game':gid,'region':region,'error':'No public price'})
  except Exception as e:errors.append({'store':'Steam','game':gid,'region':region,'error':str(e)})
  time.sleep(2)
 print(gid,flush=True)
pages=[('hades','PS5','https://store.playstation.com/en-us/product/UP2125-PPSA03355_00-3466019145463410/'),('hades','Xbox','https://www.xbox.com/en-us/games/store/Hades/9P8DL6W0JBB8'),('hades','Nintendo','https://www.nintendo.com/us/store/products/hades-switch/'),('hades2','Nintendo','https://www.nintendo.com/us/store/products/hades-ii-switch/'),('hollow','Nintendo','https://www.nintendo.com/us/store/products/hollow-knight-switch/')]
for gid,store,url in pages:
 try:
  raw=get(url).decode();products=[]
  for s in re.findall(r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',raw,re.S):
   for x in walk(json.loads(s)):
    types=x.get('@type',[]);types=[types] if isinstance(types,str) else types
    if 'Product' in types and x.get('offers'):products.append(x)
  if not products:raise ValueError('No structured product price in official page')
  p=products[0];o=p['offers'];o=o[0] if isinstance(o,list) else o
  if 'price' not in o:raise ValueError('No exact public offer price')
  g=games.setdefault(gid,{'id':gid,'name':p['name'],'description':plain(p.get('description'))[:600],'image':p.get('image'),'genre':'','metadataSource':url,'offers':[]})
  offer(g,store,'US',float(o['price']),o['priceCurrency'],url)
 except Exception as e:errors.append({'store':store,'game':gid,'region':'US','error':str(e)})
 print(store,gid,flush=True)
if not games:raise SystemExit('No products fetched; previous catalog retained')
data={'fetchedAt':NOW,'fxDate':fxxml.attrib.get('Date'),'fxSource':'https://www.cbr.ru/scripts/XML_daily.asp','rates':rates,'regions':regions,'games':list(games.values()),'history':history,'errors':errors,'coverage':{'Steam':str(len(apps))+' игры · 5 регионов','Nintendo':'3 игры · США','PS5':'Hades · США','Xbox':'Hades · США'}}
tmp=OUT.with_suffix('.tmp');tmp.write_text(json.dumps(data,ensure_ascii=False));tmp.replace(OUT)
print(json.dumps({'games':len(games),'offers':sum(len(g['offers']) for g in games.values()),'errors':errors},ensure_ascii=False),flush=True)
