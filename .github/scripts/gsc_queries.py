# -*- coding: utf-8 -*-
"""GSC: реальные поисковые запросы через Search Console API (service account из секрета GA_SERVICE_KEY)."""
import io, os, sys, json, time
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import jwt
import requests

KEY_FILE = sys.argv[1] if len(sys.argv) > 1 else "/tmp/ga-key.json"
SITE = os.environ.get("GSC_SITE", "sc-domain:uriy-as.org")
TOKEN_URL = "https://oauth2.googleapis.com/token"
API = "https://www.googleapis.com/webmasters/v3/sites/%s/searchAnalytics/query" % SITE.replace(":", "%3A")

sa = json.load(open(KEY_FILE, encoding="utf-8"))
now = int(time.time())
payload = {
    "iss": sa["client_email"],
    "scope": "https://www.googleapis.com/auth/webmasters.readonly",
    "aud": TOKEN_URL,
    "iat": now,
    "exp": now + 3600,
}
signed = jwt.encode(payload, sa["private_key"], algorithm="RS256", headers={"typ": "JWT"})
r = requests.post(TOKEN_URL, data={"grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                                    "assertion": signed}, timeout=20)
if r.status_code != 200:
    print("OAUTH ERROR", r.status_code, r.text[:400])
    print("EMAIL:", sa.get("client_email"))
    raise SystemExit(1)
tok = r.json()["access_token"]
print("service account:", sa.get("client_email"))
print("site:", SITE)


def q(start, end, dims, extra=None):
    body = {"startDate": start, "endDate": end, "dimensions": dims, "rowLimit": 25000, "dataState": "all"}
    if extra:
        body.update(extra)
    rr = requests.post(API, json=body, headers={"Authorization": "Bearer " + tok}, timeout=60)
    if rr.status_code != 200:
        print("API ERROR", rr.status_code, rr.text[:400])
        return []
    return rr.json().get("rows", [])


end = time.strftime("%Y-%m-%d")
start90 = time.strftime("%Y-%m-%d", time.localtime(time.time() - 90 * 86400))
start28 = time.strftime("%Y-%m-%d", time.localtime(time.time() - 28 * 86400))

print("\n=== СВОДКА (90 дней) ===")
rows = q(start90, end, ["date"])
print("строк по дням:", len(rows))

print("\n=== ТОП-ЗАПРОСЫ (90 дней) ===")
rows = q(start90, end, ["query"])
rows.sort(key=lambda x: -x["clicks"])
for x in rows[:60]:
    print("  %-58s показы=%-6d клики=%-4d CTR=%-5.1f%% поз=%-6.1f" % (
        x["keys"][0][:58], x["impressions"], x["clicks"], 100.0 * x["ctr"], x["position"]))

print("\n=== ТОП-СТРАНИЦЫ (90 дней) ===")
rows = q(start90, end, ["page"])
rows.sort(key=lambda x: -x["impressions"])
for x in rows[:25]:
    print("  %-70s показы=%-6d клики=%-4d поз=%.1f" % (x["keys"][0][:70], x["impressions"], x["clicks"], x["position"]))

print("\n=== ЗАПРОСЫ ПОСЛЕДНИЕ 28 ДНЕЙ ===")
rows = q(start28, end, ["query"])
rows.sort(key=lambda x: -x["impressions"])
for x in rows[:40]:
    print("  %-58s показы=%-6d клики=%-4d поз=%-6.1f" % (x["keys"][0][:58], x["impressions"], x["clicks"], x["position"]))

print("\n=== JSON (для разбора) ===")
out = {"site": SITE, "start": start90, "end": end,
       "queries": q(start90, end, ["query"]), "pages": q(start90, end, ["page"]),
       "queries28": q(start28, end, ["query"])}
print("__JSON__" + json.dumps(out, ensure_ascii=False))
