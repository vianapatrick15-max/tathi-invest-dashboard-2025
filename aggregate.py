"""Puxa o spend diário por campanha de todas as contas (Meta Ads API),
agrupa por funil/dia e escreve data.json no schema do dashboard.

Rodável local (usa .env das skills) ou no GitHub Actions (usa secrets
META_TOKEN_ID / META_TOKEN_MEM). Reescreve só data.json — index.html é estático.
"""
import os, sys, json, warnings, collections
warnings.filterwarnings("ignore")
from datetime import date
from pathlib import Path

try:
    from zoneinfo import ZoneInfo
    TODAY = date.today() if not os.environ.get("TZ_SP") else None
    today = __import__("datetime").datetime.now(ZoneInfo("America/Sao_Paulo")).date()
except Exception:
    today = date.today()

from facebook_business.api import FacebookAdsApi
from facebook_business.adobjects.adaccount import AdAccount

from config import ACCOUNTS, FAM_PREF, SINCE, resolve_token, funnel_key, family
try:
    from config import UNTIL_OVERRIDE
except ImportError:
    UNTIL_OVERRIDE = None

OUT = Path(__file__).parent / "data.json"
# Ano fechado: trava o fim da janela; senão segue o dia corrente.
UNTIL = UNTIL_OVERRIDE or today.isoformat()
FIELDS = ["campaign_name", "spend"]
BASE_PARAMS = {"level": "campaign", "time_increment": 1, "limit": 500}


def _month_windows(since: str, until: str):
    """Gera janelas mensais (since,until) cobrindo [since, until].

    Puxar o ano inteiro com time_increment=1 num request só estoura o endpoint
    síncrono (erro 500) e expira o cursor de paginação. Fatiar por mês mantém
    cada request pequeno e estável.
    """
    from datetime import date as _d
    y0, m0 = int(since[:4]), int(since[5:7])
    yN, mN = int(until[:4]), int(until[5:7])
    y, m = y0, m0
    while (y, m) <= (yN, mN):
        first = _d(y, m, 1)
        nm_y, nm_m = (y + 1, 1) if m == 12 else (y, m + 1)
        last = _d(nm_y, nm_m, 1).fromordinal(_d(nm_y, nm_m, 1).toordinal() - 1)
        s = max(first.isoformat(), since)
        u = min(last.isoformat(), until)
        yield s, u
        y, m = nm_y, nm_m


def pull_account(acct_id: str):
    """Retorna lista de (funnel, date, spend) com spend>0 da conta, mês a mês."""
    rows = []
    for s, u in _month_windows(SINCE, UNTIL):
        params = dict(BASE_PARAMS, time_range={"since": s, "until": u})
        last_err = None
        for attempt in range(3):  # retry em 500/cursor transitório
            try:
                cursor = AdAccount(acct_id).get_insights(fields=FIELDS, params=params)
                for it in cursor:
                    sp = float(it.get("spend", 0) or 0)
                    if sp <= 0:
                        continue
                    rows.append((funnel_key(it.get("campaign_name", "")), it.get("date_start"), sp))
                last_err = None
                break
            except Exception as e:
                last_err = e
        if last_err is not None:
            print(f"    WARN {acct_id} {s}->{u}: {last_err}", file=sys.stderr)
    return rows


def main():
    # agrega (acct_key -> {(funnel,date): spend})
    per_acct = collections.OrderedDict((a["key"], collections.defaultdict(float)) for a in ACCOUNTS)
    fam_of = {}
    dmin, dmax = "9999-99-99", "0000-00-00"

    last_token = None
    for a in ACCOUNTS:
        token = resolve_token(a["token_env"], a["skill_env"])
        if token != last_token:
            FacebookAdsApi.init(access_token=token)
            last_token = token
        try:
            rows = pull_account(a["key"])
        except Exception as e:
            print(f"WARN {a['key']} ({a['label']}): {e}", file=sys.stderr)
            rows = []
        for fk, d, sp in rows:
            per_acct[a["key"]][(fk, d)] += sp
            fam_of[fk] = family(fk)
            if d and d < dmin: dmin = d
            if d and d > dmax: dmax = d
        print(f"  {a['label']:<18} {a['key']}: {len(rows)} linhas", file=sys.stderr)

    # mantém só contas com verba, reindexando
    funded = [a for a in ACCOUNTS if per_acct[a["key"]]]
    idx_of = {a["key"]: i for i, a in enumerate(funded)}
    records = []
    for a in funded:
        ai = idx_of[a["key"]]
        for (fk, d), sp in per_acct[a["key"]].items():
            records.append([ai, fk, d, round(sp, 2)])
    records.sort(key=lambda r: (r[0], r[2], r[1]))

    present = sorted(set(fam_of.values()))
    fam_order = [f for f in FAM_PREF if f in present] + [f for f in present if f not in FAM_PREF]

    bounds_min = SINCE
    bounds_max = dmax if dmax != "0000-00-00" else UNTIL
    if bounds_max < UNTIL:
        bounds_max = UNTIL  # estende o eixo até hoje

    out = {
        "generated": today.strftime("%d/%m/%Y"),
        "bounds": {"min": bounds_min, "max": bounds_max},
        "accounts": [{"key": a["key"], "client": a["client"], "label": a["label"]} for a in funded],
        "fam_of": fam_of,
        "fam_order": fam_order,
        "records": records,
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")))
    tot = sum(r[3] for r in records)
    print(f"OK data.json | contas={len(funded)} funis={len(present)} registros={len(records)} "
          f"total=R$ {tot:,.2f} | {bounds_min}->{bounds_max} | gerado {out['generated']}", file=sys.stderr)


if __name__ == "__main__":
    main()
