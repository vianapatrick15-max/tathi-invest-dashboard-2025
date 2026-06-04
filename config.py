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

# Famílias na ordem preferida. Lista fechada do ano de 2025 — o classificador
# (funnel_key) só emite estas + "Outros", então essa ordem controla 100% dos pills.
FAM_PREF = [
    "IPM", "DP100K", "PALESTRA MEMORAVEL", "NEP", "WKP", "IEM", "VCO",
    "KLT", "W.E.M", "MXP", "MXP.PT", "FA-Fp", "VPO", "WPL", "ID-WEBN", "Outros",
]


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


# Classificador de funil 2025 por ASSINATURA. Os nomes de campanha de 2025 usam
# várias convenções incompatíveis (colchete-produto, objetivo-no-1o-colchete,
# underscore, ix./th. prefixo, label de conta vazando). Em vez de parsear posição,
# varremos o nome inteiro contra regras ordenadas — a 1ª que casa vence. A ORDEM
# resolve nomes multi-token: [KLT]...[DP100K] -> KLT; [IPM-Le01][NEP] -> IPM.
# Tudo que não casa com nenhum produto conhecido cai em "Outros".
_RULES = [
    (r"IPM-(FP|LE|TL)|\[IPM|\bII-FP",                                  "IPM"),
    (r"\bKLT\b|TH\.KLT|\bKLT\d",                                       "KLT"),
    (r"DP100K|P100K",                                                  "DP100K"),
    (r"\bVPO\b|VPO-LE",                                                "VPO"),
    (r"NEP0|\[NEP\]",                                                  "NEP"),
    (r"\bWKP\b",                                                       "WKP"),
    (r"\bIEM\b",                                                       "IEM"),
    (r"\bVCO0\d",                                                      "VCO"),
    (r"\bWPL\b|WPL-FP",                                                "WPL"),
    (r"\bFA-FP|\[FA-FP",                                               "FA"),
    (r"MXP\.PT|MXP PT|MXP-PT",                                         "MXP.PT"),
    (r"\bMXP\b|MXP-(FP|LE)|\[MXP|MXP BRASIL",                          "MXP"),
    (r"PALESTRA MEMORAVEL|\bPDP\b|CORREDOR|IMERS[ÃA]O PALCO|"
     r"PALCO MILIONARI|ESTAMOS AO VIVO|TATHI'?S BRAZIL|"
     r"INSCRI[CÇ][AÃ]O IMERS",                                         "PALESTRA MEMORAVEL"),
    (r"W\.?E\.?M\b|EVENTOS MILION[ÁA]RIOS",                            "W.E.M"),
    (r"ID WEBN",                                                       "ID-WEBN"),
]

# Famílias que carregam fase (PRODUTO-FaseNN) no nome — extraímos para detalhar
# o funil. Para as demais, funil == família (produto consolidado).
_PHASED = {"IPM", "DP100K", "MXP", "MXP.PT", "FA", "VPO", "WPL"}


def funnel_key(name: str) -> str:
    up = (name or "").strip().upper()
    if not up:
        return "Outros"
    # Post/publicação impulsionado sem produto identificável -> Outros
    if re.match(r"^(POST|PUBLICA[CÇ][AÃ]O) DO INSTAGRAM", up):
        return "Outros"

    fam = next((f for rx, f in _RULES if re.search(rx, up)), None)
    if fam is None:
        return "Outros"

    if fam in _PHASED:
        m = re.search(r"-(FP|LE|TL)\s?0?(\d{1,2})", up)
        if m:
            ph = {"FP": "Fp", "LE": "Le", "TL": "TL"}[m.group(1)]
            return f"{fam}-{ph}{int(m.group(2)):02d}"
    return fam


def family(funnel: str) -> str:
    m = re.match(r"^(.*?)-(Fp|Le|TL)\d", funnel)
    base = m.group(1) if m else funnel
    return "FA-Fp" if base == "FA" else base
