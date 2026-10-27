# -*- coding: utf-8 -*-
"""GSC: реальные поисковые запросы через Search Console API (service account из секрета GA_SERVICE_KEY).
Вывод — TSV (устойчив к санитайзеру логов GitHub)."""
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
signed = jwt.encode({"iss": sa["client_email"],
                     "scope": "https://www.googleapis.com/auth/webmasters.readonly",
                     "aud": TOKEN_URL, "iat": now, "exp": now + 3600},
                    sa["private_key"], algorithm="RS256", headers={"typ": "JWT"})
r = requests.post(TOKEN_URL, data={"grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                                    "assertion": signed}, timeout=20)
if r.status_code != 200:
    print("OAUTH_ERROR", r.status_code, r.text[:300])
    print("SA_EMAIL", sa.get("client_email"))
    raise SystemExit(1)
tok = r.json()["access_token"]
print("SITE", SITE)
print("SA_EMAIL", sa.get("client_email"))


def q(start, end, dims):
    body = {"startDate": start, "endDate": end, "dimensions": dims, "rowLimit": 25000, "dataState": "all"}
    rr = requests.post(API, json=body, headers={"Authorization": "Bearer " + tok}, timeout=60)
    if rr.status_code != 200:
        print("API_ERROR", rr.status_code, rr.text[:300])
        return []
    return rr.json().get("rows", [])


end = time.strftime("%Y-%m-%d")
d90 = time.strftime("%Y-%m-%d", time.localtime(time.time() - 90 * 86400))
d28 = time.strftime("%Y-%m-%d", time.localtime(time.time() - 28 * 86400))
d7 = time.strftime("%Y-%m-%d", time.localtime(time.time() - 7 * 86400))

for label, start in (("90", d90), ("28", d28), ("7", d7)):
    rows = q(start, end, ["query"])
    rows.sort(key=lambda x: -x["impressions"])
    print("###QUERIES_%s###" % label)
    for x in rows:
        print("GSCQ\t%s\t%s\t%s\t%s" % (label, x["keys"][0].replace("\t", " "),
                                        x["impressions"], x["clicks"], round(x["position"], 1)))

rows = q(d90, end, ["page"])
rows.sort(key=lambda x: -x["impressions"])
print("###PAGES_90###")
for x in rows:
    print("GSCP\t%s\t%s\t%s\t%s" % (x["keys"][0], x["impressions"], x["clicks"], round(x["position"], 1)))

rows = q(d90, end, ["query", "page"])
rows.sort(key=lambda x: -x["impressions"])
print("###QPAGE_90###")
for x in rows:
    print("GSCQP\t%s\t%s\t%s\t%s\t%s" % (x["keys"][0], x["keys"][1], x["impressions"], x["clicks"], round(x["position"], 1)))
print("###DONE###")
