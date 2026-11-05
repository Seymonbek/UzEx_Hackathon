"""Доступ к данным: безопасный read-only SQL + нечёткий поиск по названиям."""
import os, re, sqlite3, time, difflib, threading
from textnorm import norm_text, norm_name

DB_PATH = os.environ.get("UZEX_DB", os.path.join(os.path.dirname(__file__), "uzex.db"))
MAX_ROWS = 60          # сколько строк возвращаем модели
MAX_CHARS = 14000
SQL_TIMEOUT = 25       # секунд

_ALLOWED = {sqlite3.SQLITE_SELECT, sqlite3.SQLITE_READ, sqlite3.SQLITE_FUNCTION, sqlite3.SQLITE_RECURSIVE}


def _authorizer(action, *_):
    return sqlite3.SQLITE_OK if action in _ALLOWED else sqlite3.SQLITE_DENY


_local = threading.local()


def _conn():
    con = getattr(_local, "con", None)
    if con is None:
        con = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True, check_same_thread=False)
        # SQLite LIKE/lower() по умолчанию не понимают кириллицу — подменяем на Python-версии
        con.create_function("lower", 1, lambda s: s.lower() if isinstance(s, str) else s, deterministic=True)
        con.create_function("upper", 1, lambda s: s.upper() if isinstance(s, str) else s, deterministic=True)
        con.create_function("norm", 1, lambda s: norm_text(s) if s is not None else None, deterministic=True)
        con.set_authorizer(_authorizer)
        _local.con = con
    return con


def run_sql(query: str) -> dict:
    """Выполняет ОДИН SELECT. Возвращает {columns, rows, row_count, truncated} или {error}."""
    q = (query or "").strip().rstrip(";").strip()
    if not re.match(r"(?is)^(select|with)\b", q):
        return {"error": "Разрешены только запросы SELECT / WITH."}
    if ";" in q:
        return {"error": "Только один запрос за раз (без ';')."}
    con = _conn()
    t0 = time.time()
    con.set_progress_handler(lambda: 1 if time.time() - t0 > SQL_TIMEOUT else 0, 200000)
    try:
        cur = con.execute(q)
        cols = [c[0] for c in cur.description]
        rows = cur.fetchmany(MAX_ROWS + 1)
    except sqlite3.Error as e:
        msg = str(e)
        if "interrupted" in msg:
            msg = f"Запрос слишком долгий (>{SQL_TIMEOUT} с) — упростите или добавьте фильтры."
        return {"error": msg}
    finally:
        con.set_progress_handler(None, 0)
    truncated = len(rows) > MAX_ROWS
    rows = rows[:MAX_ROWS]
    out = [[_fmt(v) for v in r] for r in rows]
    res = {"columns": cols, "rows": out, "row_count": len(out), "truncated": truncated}
    if truncated:
        res["note"] = f"Показаны первые {MAX_ROWS} строк; добавьте LIMIT/агрегацию."
    return res


def _fmt(v):
    if isinstance(v, float):
        if v == int(v) and abs(v) < 1e18:
            return int(v)
        return round(v, 4)
    return v


# ---------------- поиск сущностей ----------------
_cache = {}


def _load(kind):
    if kind in _cache:
        return _cache[kind]
    con = _conn()
    if kind == "company":
        rows = con.execute("SELECT inn, name, role, region, activity, name_norm FROM participants").fetchall()
        items = [dict(id=r[0], name=r[1], role=r[2], region=r[3], activity=r[4], key=r[5]) for r in rows]
    elif kind == "broker":
        rows = con.execute("SELECT broker_code, name, inn, region, name_norm FROM brokers").fetchall()
        items = [dict(id=r[0], name=r[1], inn=r[2], region=r[3], key=r[4]) for r in rows]
    elif kind == "product":
        rows = con.execute("""SELECT d.product_variant, d.product_code, d.product_ru, p.product_uz, COUNT(*) n
                              FROM deals d JOIN products p USING(product_code)
                              GROUP BY d.product_variant, d.product_code""").fetchall()
        items = [dict(id=r[1], name=r[0], product_ru=r[2], product_uz=r[3], deals=r[4],
                      key=norm_text(r[0] + " " + r[2] + " " + r[3])) for r in rows]
    else:
        raise ValueError(kind)
    _cache[kind] = items
    return items


def search_entity(kind: str, query: str, limit: int = 8) -> dict:
    """kind: company | broker | product. Ищет по названию/STIR/коду; кириллица и латиница равнозначны."""
    kind = (kind or "").lower()
    if kind not in ("company", "broker", "product"):
        return {"error": "kind должен быть company, broker или product"}
    q = (query or "").strip()
    if not q:
        return {"error": "пустой запрос"}
    items = _load(kind)
    digits = re.sub(r"\D", "", q)
    res = []
    if digits and len(digits) >= 3 and digits == q.replace(" ", ""):
        res = [i for i in items if i["id"].startswith(digits) or str(i.get("inn", "")) == digits]
    if not res and kind == "broker" and re.match(r"(?i)^bk\d+$", q):
        res = [i for i in items if i["id"].lower() == q.lower()]
    if not res:
        nq = norm_name(q) if kind != "product" else norm_text(q)
        toks = nq.split()
        exact, fuzzy = [], []
        for i in items:
            k = i["key"]
            if toks and all(t in k for t in toks):
                exact.append((len(nq) / (len(k) + 1), i))
            else:
                r = difflib.SequenceMatcher(None, nq, k).ratio()
                if r >= 0.8:
                    fuzzy.append((r, i))
        pool = exact or fuzzy          # точные совпадения важнее «похожих»
        pool.sort(key=lambda x: -x[0])
        res = [i for _, i in pool]
    if kind == "product":  # объединяем варианты по коду, показываем варианты
        seen = {}
        for i in res:
            seen.setdefault(i["id"], dict(product_code=i["id"], product_ru=i["product_ru"], product_uz=i["product_uz"], variants=[]))
            seen[i["id"]]["variants"].append(f'{i["name"]} ({i["deals"]} сделок)')
        out = list(seen.values())[:limit]
        for o in out:
            o["variants"] = o["variants"][:6]
    else:
        out = [{k: v for k, v in i.items() if k != "key"} for i in res[:limit]]
    return {"matches": out, "count": len(out)} if out else {"matches": [], "count": 0,
            "note": "Ничего не найдено — в данных такой записи нет (проверьте написание)."}


def db_overview() -> dict:
    con = _conn()
    r = con.execute("SELECT MIN(deal_date), MAX(deal_date), COUNT(*) FROM deals").fetchone()
    return {"first_date": r[0], "last_date": r[1], "deals": r[2]}
