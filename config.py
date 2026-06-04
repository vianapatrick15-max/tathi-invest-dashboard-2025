"""Config do dashboard de investimento — contas, tokens e parsing de funil."""
import os, re
from pathlib import Path

# Janela do dashboard — ano fechado de 2025 (histórico, range fixo).
SINCE = "2025-01-01"
UNTIL_OVERRIDE = "2025-12-31"

# Contas de anúncio. token_env = nome da variável de ambiente / GitHub secret.
# Fallback local: .env da skill correspondente (skill_env).
ACCOUNTS = [
    {"key": "act_1725623984282551", "client": "Instituto ID", "label": "C1 (IPM)",          "token_env": "META_TOKEN_ID",  "skill_env": "meta-ads-instituto-id"},
    {"key": "act_506518827383127",  "client": "Instituto ID", "label": "C3 / Instituto ID",  "token_env": "META_TOKEN_ID",  "skill_env": "meta-ads-instituto-id"},
    {"key": "act_306533480853015",  "client": "Instituto ID", "label": "C2",                 "token_env": "META_TOKEN_ID",  "skill_env": "meta-ads-instituto-id"},
    {"key": "act_629440996401732",  "client": "Instituto ID", "label": "C4",                 "token_env": "META_TOKEN_ID",  "skill_env": "meta-ads-instituto-id"},
    {"key": "act_529640016271311",  "client": "Instituto ID", "label": "C5",                 "token_env": "META_TOKEN_ID",  "skill_env": "meta-ads-instituto-id"},
    {"key": "act_1307282709635504", "client": "Memorável",    "label": "C1",                 "token_env": "META_TOKEN_MEM", "skill_env": "meta-ads-memoravel"},
    {"key": "act_1835702343244302", "client": "Memorável",    "label": "C2",                 "token_env": "META_TOKEN_MEM", "skill_env": "meta-ads-memoravel"},
    {"key": "act_422653132521856",  "client": "Memorável",    "label": "C3",                 "token_env": "META_TOKEN_MEM", "skill_env": "meta-ads-memoravel"},
]

# Famílias na ordem preferida (extras presentes nos dados entram depois).
FAM_PREF = ["IPM", "DP100K", "IPL", "MXP", "KLT", "FA-Fp"]


def resolve_token(token_env: str, skill_env: str) -> str:
    """Lê o token do ambiente (GitHub secret) ou cai pro .env da skill (uso local)."""
    v = os.environ.get(token_env)
    if v:
        return v.strip()
    p = Path.home() / ".claude/skills" / skill_env / ".env"
    if p.exists():
        for line in p.read_text().splitlines():
            line = line.strip()
            if line.startswith("META_ADS_TOKEN") and "=" in line:
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise RuntimeError(f"Token nao encontrado: env {token_env} nem .env de {skill_env}")


# Palavras de OBJETIVO (não são produto). Em nomes 2025 o 1º colchete costuma
# ser o objetivo e o produto vem no 2º: [VENDAS] [P100K], [CAPTURA] [PDP]...
_OBJ = {
    "VENDAS", "CAPTURA", "ESCALA", "INSCRICAO", "INSCRIÇÃO", "INSCRICÕES", "INSCRIÇÕES",
    "TESTE", "TESTE DE CRIATIVO", "TESTE DE CRIATIVOS", "RMKT", "RKMT", "REMARKETING",
    "TRAFEGO", "TRÁFEGO", "LEADS", "TOPO", "ENGAJAMENTO", "ALCANCE", "CONVERSAO",
    "CONVERSÃO", "AQUISICAO", "AQUISIÇÃO", "RETARGETING",
}


def funnel_key(name: str) -> str:
    s = (name or "").strip()
    if s.lower().startswith(("post do instagram", "publicacao", "publicação")):
        return "Impulsionamentos IG"
    s = re.sub(r"^ix\.\s*", "", s)                       # prefixo ix.
    s = re.sub(r"\s*[-–—]\s*[Cc][óo]pia\s*$", "", s)     # sufixo "— Cópia"
    s = re.sub(r"^C\d+\s*[-–]\s*", "", s)                # label de conta "C3 - "

    # 1) Código de produto com fase no começo: IPM-Fp01, VPO-Le03, Mxp.Pt-Fp01, DP100K-Fp01
    m = re.match(r"^\[?\s*([A-Za-z][A-Za-z0-9.]{1,7})[-\s.]?(Le|Fp)\s?0?(\d+)", s, re.I)
    if m:
        ph = "Le" if m.group(2).lower() == "le" else "Fp"
        return f"{m.group(1).upper().rstrip('.')}-{ph}{int(m.group(3)):02d}"

    # 2) Colchetes: pula objetivo(s) e usa o 1º que for produto de verdade
    brackets = re.findall(r"\[([^\]]+)\]", s)
    if brackets:
        for b in brackets:
            if b.strip().upper() not in _OBJ:
                return b.strip()
        return brackets[0].strip()

    # 3) Sem colchete: 1º token de produto, pulando nº de campanha (CPnn) e datas
    for tok in re.split(r"[-_\s|]+", s):
        tok = tok.strip()
        if not tok:
            continue
        if re.fullmatch(r"CP\d+|C\d+|\d+|\d{1,2}/\d{1,2}", tok, re.I):
            continue
        return tok
    return (s[:16] or "Outros")


def family(funnel: str) -> str:
    if funnel.lower().startswith("impuls"):
        return "Outros"
    tok = re.split(r"[-\s]", funnel)[0].upper()
    return "FA-Fp" if tok == "FA" else tok
