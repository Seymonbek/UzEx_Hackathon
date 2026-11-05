"""Нормализация текста: транслитерация кириллица->латиница, апострофы, сорт/класс."""
import re

_APOS = "’‘ʻʼ`´'"
_CYR = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "yo", "ж": "j", "з": "z",
    "и": "i", "й": "y", "к": "k", "л": "l", "м": "m", "н": "n", "о": "o", "п": "p", "р": "r",
    "с": "s", "т": "t", "у": "u", "ф": "f", "х": "x", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "sh",
    "ъ": "", "ы": "i", "ь": "", "э": "e", "ю": "yu", "я": "ya",
    "ғ": "g", "қ": "q", "ҳ": "h", "ў": "o", "ӯ": "o", "ҷ": "j", "ӣ": "i",
}
_LEGAL = {"mchj", "mchzh", "ooo", "ao", "ok", "xk", "mas", "uliyati", "cheklangan", "jamiyati",
          "masuliyati", "masuliyat", "jamiyat", "ooo", "limited", "llc", "ltd", "mchzh"}


def translit(s: str) -> str:
    out = []
    for ch in s.lower():
        out.append(_CYR.get(ch, ch))
    return "".join(out)


def norm_text(s) -> str:
    """нижний регистр, латиница, без апострофов/кавычек/знаков, одинарные пробелы."""
    if s is None:
        return ""
    s = str(s)
    for a in _APOS:
        s = s.replace(a, "")
    s = translit(s)
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def norm_name(s) -> str:
    """Название компании без организационно-правовой формы (для поиска)."""
    toks = [t for t in norm_text(s).split() if t not in _LEGAL]
    return " ".join(toks)


_ROMAN = {"i": "1", "ii": "2", "iii": "3"}
_WORD = {"первый": "1", "второй": "2", "третий": "3", "первого": "1", "второго": "2", "третьего": "3"}


def _one(token: str):
    token = token.strip().lower()
    if token.isdigit():
        return token
    if token in _ROMAN:
        return _ROMAN[token]
    return _WORD.get(token)


def norm_sort(text: str):
    """Сорт товара -> '1' | '2' | '3' | 'высший' | None (разные написания сведены к одному)."""
    t = (text or "").lower()
    m = re.search(r"(\d+|iii|ii|i|первый|второй|третий|первого|второго|третьего)[\s-]*сорт", t)
    if m:
        return _one(m.group(1))
    m = re.search(r"сорт[\s:]*(\d+|iii|ii|i|первый|второй|третий)\b", t)
    if m:
        return _one(m.group(1))
    if re.search(r"(высш\w*)\s*сорт|сорт\s*высш|сорт\s+в\b", t):
        return "высший"
    return None


def norm_class(text: str):
    """Класс товара -> '1' | '2' | '3' | None (только числовой/римский класс)."""
    t = (text or "").lower()
    m = re.search(r"(\d+|iii|ii|i)[\s-]*класс", t)
    if m:
        return _one(m.group(1))
    m = re.search(r"класс[\s:]*(\d+|iii|ii|i)\b", t)
    if m:
        return _one(m.group(1))
    return None


_TAG = re.compile(r"\((спот|форвард|фьючерс)\)", re.I)


def clean_variant(name: str) -> str:
    """Название продукта из карточки контракта без пометки (спот)/(форвард) и сорта/класса."""
    s = _TAG.sub("", name or "")
    s = re.sub(r"(\d+|iii|ii|i|первый|второй|третий|высший)[\s-]*(сорт\w*|класс\w*)", "", s, flags=re.I)
    s = re.sub(r"[\s-]+", " ", s).strip()
    return s[:1].upper() + s[1:].lower() if s else s
