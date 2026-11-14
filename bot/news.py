#!/usr/bin/env python3
"""روبوت «الجديد» لتطبيق دمّاج — يعمل يومياً على GitHub Actions.
يزور مواقع المشايخ الرسمية، ويأخذ ما نُشر بعد آخر جمع **بنصّه كما هو** (نقل لا إفتاء)،
ويكتبه في news/<الشيخ>.json فيقرؤه التطبيق ويضمّه إلى المكتبة والبحث.
  python3 bot/news.py                 كل المشايخ (ابن عثيمين أسبوعياً فقط: الجمعة)
  python3 bot/news.py hajuri rabee    مشايخ محددون
  python3 bot/news.py --all-oth ...   يفحص ابن عثيمين اليوم أيضاً
الحالة (ما سبق جمعه) في bot/state/<الشيخ>.json.gz — لا يُعاد عنصر سبق أخذه.
الألباني ومقبل رحمهما الله: أرشيف ثابت؛ يُفحص مقبل فقط (أول صفحة) احتياطاً."""
import gzip, html as H, json, os, re, sys, time, datetime, urllib.request, urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ST, NEWS = f'{ROOT}/bot/state', f'{ROOT}/news'
os.makedirs(NEWS, exist_ok=True)
UA = 'Mozilla/5.0 (Linux; Android 13) DammajNewsBot/1.0 (+dammajapp@gmail.com)'
CAP = 4000          # أقصى عدد عناصر في ملف الجديد (الأحدث أولاً)
MAXNEW = 300        # أقصى جديد يؤخذ في تشغيل واحد لكل شيخ (الباقي في التشغيل التالي)
LOG = []

def log(*a):
    s = ' '.join(str(x) for x in a); print(s, flush=True); LOG.append(s)

def get(url, tries=4, js=False):
    for k in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': UA, 'Accept-Language': 'ar'}), timeout=40) as r:
                b = r.read().decode('utf8', 'replace'); time.sleep(.35)
                return json.loads(b) if js else b
        except urllib.error.HTTPError as e:
            if e.code in (404, 410): return None
        except Exception: pass
        time.sleep(3 + 4 * k)
    return None

def txt(x):
    x = re.sub(r'<(script|style|svg)\b.*?</\1>', '', x or '', flags=re.S)
    x = re.sub(r'\s*\n\s*', ' ', x)
    x = re.sub(r'(?i)<br\s*/?>|</(p|div|li|h\d|tr|blockquote)>', '\n', x)
    x = H.unescape(re.sub(r'<[^>]+>', '', x)).replace('\xa0', ' ').replace('\u200c', '').replace('\u200b', '')
    return '\n'.join(re.sub(r'[ \t]+', ' ', l).strip() for l in x.split('\n') if l.strip())

enc = lambda u: urllib.parse.quote(u, safe=':/?&=%#') if u else ''
def snip(x, n=150):
    x = re.sub(r'\s+', ' ', x or '').strip(); return x[:n] + ('…' if len(x) > n else '')
qa = lambda q, a: f'السؤال: {q}\nالجواب: {a}' if q else a
today = lambda: datetime.date.today().isoformat()

def load_state(k):
    p = f'{ST}/{k}.json.gz'
    d = json.load(gzip.open(p, 'rt', encoding='utf8')) if os.path.exists(p) else {'known': []}
    d['known'] = set(d['known']); return d

def save_state(k, d):
    d = dict(d); d['known'] = sorted(d['known'])
    with gzip.open(f'{ST}/{k}.json.gz', 'wt', encoding='utf8') as f: json.dump(d, f, ensure_ascii=False, separators=(',', ':'))

def save_news(k, items):
    """items: [{ty,t,mp3,x,path,d}] الأحدث أولاً ← يُدمج مع الملف السابق"""
    p = f'{NEWS}/{k}.json'
    old = json.load(open(p, encoding='utf8')) if os.path.exists(p) else {'I': [], 'X': []}
    have = {x[5] for x in old['I']}
    I, X = [], []
    for o in items:
        if o['path'] in have or not o.get('t'): continue
        x = o.get('x') or ''
        I.append([o['ty'], o['t'], -1, enc(o.get('mp3', '')), -2, o['path'], snip(re.split(r'\n\s*(?:الجواب|ج)\s*[:：]\s*', x, 1)[-1] if re.search(r'\n\s*(?:الجواب|ج)\s*[:：]', x) else x.replace(o['t'], '', 1)), o.get('d') or today()]); X.append(x)
    I, X = (I + old['I'])[:CAP], (X + old['X'])[:CAP]
    json.dump({'v': 1, 'k': k, 't': datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%MZ'), 'n': len(I), 'I': I, 'X': X},
              open(p, 'w', encoding='utf8'), ensure_ascii=False, separators=(',', ':'))
    return len(I)

# ======================= الحجوري: sh-yahia.net =======================
def hajuri(st):
    B = 'https://sh-yahia.net'; out = []
    cats = st.get('cats', {})
    def chain(c):
        L = [c]
        while c in cats and cats[c][0] not in (0, -1): c = str(cats[c][0]); L.append(c)
        return L[::-1]
    def block(s, start):
        depth = 0
        for m in re.finditer(r'<(/?)div\b[^>]*>', s[start:]):
            depth += -1 if m.group(1) else 1
            if depth == 0: return s[start:start + m.end()]
        return s[start:]
    def prose(s):
        m = re.search(r'<div class="prose[^"]*"[^>]*>', s); return txt(block(s, m.start())) if m else ''
    def title(s):
        m = re.search(r'<h1[^>]*>(.*?)</h1>', s, re.S); return txt(m.group(1)) if m else ''
    def date(s):
        i = s.find('<h1'); m = re.search(r'(20\d\d-\d\d-\d\d)', s[i:i + 3000] if i >= 0 else s); return m.group(1) if m else ''
    for php, kind, pat in (('sounds.php', 'sound', 'show_sound_%d.html'), ('fatawa.php', 'fatawa', 'show_fatawa_%d.html'), ('articles.php', 'art', 'show_art_%d.html')):
        new = []
        for p in range(1, 12):
            s = get(f'{B}/{php}' + (f'?page={p}' if p > 1 else '')) or ''
            ids = list(dict.fromkeys(int(x) for x in re.findall(r'show_' + kind + r'_(\d+)\.html', s)))
            fresh = [i for i in ids if pat % i not in st['known'] and i not in new]
            new += fresh
            if not fresh or len(new) >= MAXNEW: break
        log('hajuri', kind, 'new', len(new))
        for i in sorted(new, reverse=True)[:MAXNEW]:
            path = pat % i; s = get(f'{B}/{path}')
            if not s or 'غير موجود' in (re.search(r'<title>(.*?)</title>', s, re.S) or [None, ''])[1]: continue
            t, d, x = title(s), date(s), prose(s)
            if kind == 'sound':
                m = re.search(r'["\'](https?://cdn\.sh-yahia\.net/[^"\']+\.(?:mp3|m4a|ogg|wav|amr|rm))["\']', s)
                mp3 = H.unescape(m.group(1)) if m else ''
                fol = urllib.parse.unquote(mp3).split('/sounds/')[-1].replace('_', ' ') if mp3 else ''
                top = fol.split('/')[0]
                st['known'].add(path)
                if not mp3 or re.search(r'المصحف|تلاو|قصائد|قصيدة', top): continue
                ty = 'f' if re.search(r'أسئلة|الأسئلة|فتاوى|الفتاوى', top) else 'd' if 'لقاء' in top else 'k' if re.search(r'خطب', t) else 'l' if re.search(r'دروس|الدروس|شرح', top + ' ' + t) else 'c'
                out.append({'ty': ty, 't': t, 'mp3': mp3, 'x': x if len(x.replace(t, '', 1).strip()) > 120 else '', 'path': path, 'd': d})
            elif kind == 'fatawa':
                i0 = s.find('</h1>'); j0 = s.find('export_pdf', i0); j0 = s.rfind('<a', i0, j0)
                blk = txt(s[i0 + 5:j0]) if i0 > 0 and j0 > 0 else ''
                blk = re.sub(r'^\s*\d{4}-\d\d-\d\d[^\n]*\n', '', blk).strip()      # سطر التاريخ والمشاهدات
                if not x.strip() and not re.search(r'(^|\n)\s*(الجواب|ج)\s*[:：]', blk): continue   # سؤال لم يُجب بعد ← يُعاد فحصه لاحقاً
                blk = re.sub(r'^\s*(بسم الله الرحمن الرحيم|بِسْمِ اللَّهِ الرَّحْمَنِ الرَّحِيمِ)\s*\n', '', blk).strip()
                st['known'].add(path)
                out.append({'ty': 'f', 't': t, 'x': blk if 'السؤال' in blk[:400] else qa(t, blk), 'path': path, 'd': d})
            else:
                st['known'].add(path)
                if len(x) > 80: out.append({'ty': 'a', 't': t, 'x': x, 'path': path, 'd': d})
    return out

# ======================= ربيع: rabee.net (ووردبريس) =======================
def rabee(st):
    B = 'https://rabee.net/wp-json/wp/v2/'; out = []
    AC = {86: 'c', 87: 'd', 94: 'c', 72: 'c', 73: 'l'}
    def body(x):
        t = txt(x['content']['rendered'])
        return re.sub(r'(?m)^(اسم المادة|المتحدث|المادة الصوتية في قسم)\s*:.*$\n?', '', t).strip()
    tt = lambda x: re.sub(r'\s+', ' ', H.unescape(x['title']['rendered'])).strip()
    for typ in ('alfatawi-api', 'audio-api', 'posts', 'benefits-api'):
        L = get(f'{B}{typ}?per_page=30&orderby=date&order=desc', js=True) or []
        new = [x for x in L if isinstance(x, dict) and f'?p={x["id"]}' not in st['known']]
        log('rabee', typ, 'new', len(new))
        for x in new:
            path = f'?p={x["id"]}'; st['known'].add(path); t = tt(x); a = body(x); d = (x.get('date') or '')[:10]
            if typ == 'alfatawi-api':
                q = re.sub(r'^(السؤال|سؤال)\s*[:：]\s*', '', t)
                if len(a) < 20: continue
                if a.startswith(q[:40]): a = a[len(q):].strip()
                a = re.sub(r'^(الجواب|الإجابة)\s*[:：]\s*', '', a)
                out.append({'ty': 'f', 't': q, 'x': qa(q, a), 'path': path, 'd': d})
            elif typ == 'audio-api':
                s = get(x['link']) or ''
                c = s.find('theme-post-content.default'); b2 = s[c:] if c > 0 else ''
                m = re.search(r"<a href='([^']+\.(?:mp3|m4a))' download=", b2, re.I) or re.search(r'data-source="([^"]+\.(?:mp3|m4a))"', b2, re.I)
                mp3 = H.unescape(m.group(1)) if m else ''
                if not mp3 and len(a) < 300: continue
                cats = x.get('audio_category_api') or []
                ty = next((AC[c] for c in cats if c in AC), 'c')
                out.append({'ty': ty, 't': t, 'mp3': mp3, 'x': a if len(a) > len(t) + 40 else '', 'path': path, 'd': d})
            elif len(a) > 40:
                out.append({'ty': 'a' if typ == 'posts' else 'p', 't': t, 'x': a, 'path': path, 'd': d})
    return out

# ======================= الفوزان: alfawzan.live =======================
def fawzan(st):
    B = 'https://alfawzan.live'; out = []
    sm = get(f'{B}/sitemap-0.xml') or ''
    ids = sorted({int(x) for x in re.findall(r'/content/(\d+)', sm)}, reverse=True)
    new = [i for i in ids if f'content/{i}' not in st['known']][:MAXNEW]
    log('fawzan', 'sitemap', len(ids), 'new', len(new))
    TY = {'ftwa': 'f', 'droos': 'l', 'mohadrat': 'c', 'khotab': 'k', 'bayan': 'a'}
    for i in new:
        path = f'content/{i}'; s = get(f'{B}/{path}/')
        if s is None: continue
        st['known'].add(path)
        b = re.sub(r'<svg.*?</svg>', '', s[s.find('<article'):], flags=re.S)
        g = lambda rx, fl=re.S: (re.search(rx, b, fl) or [None, ''])[1]
        ty = TY.get(g(r'data-content-type="([^"]*)"'), 'l'); t = txt(g(r'<h1[^>]*>(.*?)</h1>'))
        head = b[:b.find('<!-- Audio Player')] if '<!-- Audio Player' in b else b[:3000]
        if 'محذوفة من الموقع الرسمي' in head or not t: continue
        mp3 = H.unescape(g(r'data-audio-url="([^"]+)"'))
        q = txt(g(r'>\s*السؤال\s*</h2>\s*<p[^>]*>(.*?)</p>')); a = txt(g(r'>\s*الجواب\s*</h2>\s*<div[^>]*>(.*?)</div>\s*</div>\s*</section>'))
        x = txt(g(r'<!-- Body content \(for other types\) -->\s*<section[^>]*>\s*<div[^>]*>\s*<div[^>]*>(.*?)</div>\s*</div>\s*</section>'))
        x = re.sub(r'https?://\S+', '', x).strip()
        text = qa(q or t, a) if a else (x if len(x.replace(t, '', 1).strip()) > 60 else '')
        out.append({'ty': ty, 't': t, 'mp3': mp3, 'x': text, 'path': path})
    return out

# ======================= ابن باز: binbaz.org.sa =======================
def binbaz(st):
    B = 'https://binbaz.org.sa'; out = []
    def clean(x): return txt(re.sub(r'<sup.*?</sup>|<section class="footnotes.*?</section>', '', x or '', flags=re.S))
    pages = st.setdefault('pages', {})
    for kind in ('1', '2', '3', '4'):                     # أنواع الفتاوى: الجديد يُلحق في آخر الصفحات
        s = get(f'{B}/fatwas/kind/{kind}') or ''
        last = max([int(x) for x in re.findall(rf'fatwas/kind/{kind}\?page=(\d+)', s)] or [1])
        start = max(1, int(pages.get(kind, last)) - 1)
        new = []
        for p in range(start, last + 2):
            h = get(f'{B}/fatwas/kind/{kind}?page={p}') or ''
            for fid, slug in re.findall(r'href="https://binbaz\.org\.sa/fatwas/(\d+)/([^"]+)"', h):
                if f'fatwas/{fid}' not in st['known'] and (fid, slug) not in new: new.append((fid, slug))
        pages[kind] = last
        log('binbaz fatwas kind', kind, 'pages', last, 'new', len(new))
        for fid, slug in new[:MAXNEW]:
            h = get(f'{B}/fatwas/{fid}/{slug}')
            if not h: continue
            st['known'].add(f'fatwas/{fid}')
            t = clean((re.search(r'<h1 class="article-title[^"]*"[^>]*>(.*?)</h1>', h, re.S) or [None, ''])[1])
            q = clean((re.search(r'<h2 class="article-title__question[^"]*"[^>]*>(.*?)</h2>', h, re.S) or [None, ''])[1])
            q = re.sub(r'^(السؤال\s*:|س\s*:)\s*', '', q).strip()
            i = h.find('class="article-content"'); j = min([x for x in (h.find('أضف للمفضلة', i), h.find('sidebar__box', i)) if x > 0] or [len(h)])
            a = re.sub(r'^(الجواب\s*:|ج\s*:)\s*', '', clean(h[h.find('>', i) + 1:j]) if i > 0 else '').strip()
            m = re.search(r'https:\\?/\\?/files\.zadapps\.info[^"&]*?\.mp3', h)
            if t and a: out.append({'ty': 'f', 't': t, 'mp3': m.group(0).replace('\\/', '/') if m else '', 'x': qa(q, a), 'path': f'fatwas/{fid}'})
    TY = {'articles': 'a', 'discussions': 'd', 'pearls': 'p', 'speeches': 'm'}
    for kind, ty in TY.items():
        s = get(f'{B}/{kind}') or ''
        last = max([int(x) for x in re.findall(r'[?&]page=(\d+)', s)] or [1])
        ids = []
        for h in (s, get(f'{B}/{kind}?page={last}') or '' if last > 1 else ''):
            ids += [i for i in re.findall(rf'href="https://binbaz\.org\.sa/{kind}/(\d+)/', h) if f'{kind}/{i}' not in st['known'] and i not in ids]
        log('binbaz', kind, 'new', len(ids))
        for i in ids[:MAXNEW]:
            h = get(f'{B}/{kind}/{i}/x')
            if not h: continue
            st['known'].add(f'{kind}/{i}')
            t = clean((re.search(r'<h1[^>]*>([\s\S]*?)</h1>', h) or [None, ''])[1])
            k0 = h.find('class="article-content"'); j = min([x for x in (h.find('أضف للمفضلة', k0), h.find('col-md-6 text-left', k0), h.find('sidebar__box', k0)) if x > 0] or [len(h)])
            x = clean(h[h.find('>', k0) + 1:j]) if k0 > 0 else ''
            m = re.search(r'data-file="([^"]+\.mp3)"', h) or re.search(r'src="(https://files\.zadapps\.info/[^"]+\.mp3)"', h)
            if t and (x or m): out.append({'ty': ty, 't': t, 'mp3': H.unescape(m.group(1)) if m else '', 'x': x, 'path': f'{kind}/{i}'})
    return out

# ======================= مقبل: muqbel.net (أرشيف) =======================
def muqbil(st):
    B = 'https://muqbel.net/'; out = []
    s = get(B + 'fatwa.php') or ''
    new = [int(i) for i in dict.fromkeys(re.findall(r'href="fatwa\.php\?fatwa_id=(\d+)" class="list-group-item"', s)) if f'fatwa.php?fatwa_id={i}' not in st['known']]
    log('muqbil new', len(new))
    dd = lambda s, l: txt((re.search(r'<dt>\s*' + l + r'\s*</dt>\s*<dd>(.*?)</dd>', s, re.S) or [None, ''])[1])
    for i in new:
        path = f'fatwa.php?fatwa_id={i}'; s = get(B + path)
        if not s: continue
        st['known'].add(path)
        t = txt((re.search(r'<h1>(.*?)</h1>', s, re.S) or [None, ''])[1])
        m = re.search(r'<audio[^>]+src="([^"]+\.mp3)"', s)
        a = txt((re.search(r'<dt>نص الإجابة:</dt>\s*<dd>(.*?)</dd>\s*</dl>', s, re.S) or [None, ''])[1]).partition('--------------')[0].strip()
        q = dd(s, 'نص السؤال:')
        if t and (a or m): out.append({'ty': 'f', 't': t, 'mp3': m.group(1) if m else '', 'x': qa(q, a) if a else '', 'path': path})
    return out

# ======================= ابن عثيمين: واجهة موقعه (أسبوعياً) =======================
def othaimeen(st):
    A, CP = 'https://shekhapi.binothaimeen.net', 'https://shekhcp.binothaimeen.net'; out = []
    TOP = {'الشروحات العلمية': 'l', 'اللقاءات والفتاوى': 'f', 'دروس الحرمين': 'l', 'المحاضرات': 'c', 'الخطب': 'k', 'المرأة': 'c'}
    ar = lambda t: ((t or {}).get('ar') or '').strip() if isinstance(t, dict) else ('' if t is None else str(t)).strip()
    full = lambda u: '' if not u else u if u.startswith('http') else CP + urllib.parse.quote(u.replace('//', '/'), safe='/')
    fn = lambda u: re.sub(r'[?#].*', '', u or '').rsplit('/', 1)[-1]
    def pages(path):
        p = 1
        while True:
            d = get(A + path + ('&' if '?' in path else '?') + f'page={p}', js=True) or {}
            yield from d.get('data', [])
            m = d.get('meta') or {}
            if not d.get('data') or m.get('current_page', 1) >= m.get('last_page', 1): return
            p += 1
    from concurrent.futures import ThreadPoolExecutor
    def kids(sec): return list(pages(f'/course/sections/audio_library/children/{sec["id"]}?pageSize=100'))
    def lessons(sec): return list(pages(f'/course/sections/audio_library/many_lessons/{sec["id"]}/100'))
    level = [(t, ar(t.get('title'))) for t in (get(A + '/course/sections/audio_library/100', js=True) or {}).get('data', [])]
    allsec = []
    with ThreadPoolExecutor(8) as ex:
        while level:                                   # شجرة الأقسام طبقةً طبقة، ٨ طلبات معاً
            allsec += level
            res = list(ex.map(lambda sr: kids(sr[0]), level))
            level = [(k, sr[1]) for sr, ks in zip(level, res) for k in ks]
        log('othaimeen sections', len(allsec))
        for (sec, root), L in zip(allsec, ex.map(lambda sr: lessons(sr[0]), allsec)):
            for x in L:
                obj = x.get('objective') or {}; mp3 = full(x.get('certificate_url'))
                if not mp3 or fn(mp3) in st['known'] or len(out) >= MAXNEW: continue
                st['known'].add(fn(mp3)); t = ar(x.get('title'))
                body = txt(ar(obj.get('content') if isinstance(obj, dict) else ''))
                out.append({'ty': TOP.get(root, 'l'), 't': t, 'mp3': mp3, 'x': body if len(body.replace(t, '', 1).strip()) > 60 else '', 'path': ''})
    log('othaimeen new', len(out))
    return out

SITES = {'binbaz': binbaz, 'othaimeen': othaimeen, 'fawzan': fawzan, 'hajuri': hajuri, 'muqbil': muqbil, 'rabee': rabee}

if __name__ == '__main__':
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    keys = args or [k for k in SITES if k != 'othaimeen' or datetime.date.today().weekday() == 4 or '--all-oth' in sys.argv]
    summary = {}
    for k in keys:
        st = load_state(k)
        try: items = SITES[k](st)
        except Exception as e: log('ERR', k, repr(e)[:200]); continue
        n = save_news(k, items); save_state(k, st)
        summary[k] = {'new': len(items), 'total': n}; log('✓', k, 'new', len(items), 'file', n)
    p = f'{NEWS}/index.json'
    idx = json.load(open(p)) if os.path.exists(p) else {}
    for k, v in summary.items(): idx[k] = {'n': v['total'], 'last': datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%MZ'), 'added': v['new']}
    json.dump(idx, open(p, 'w'), ensure_ascii=False, separators=(',', ':'))
