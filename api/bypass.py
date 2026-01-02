from flask import Flask, request, jsonify
import requests
import json
import base64
import time
import re
import random
import string

app = Flask(__name__)

BASE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "en-US,en;q=0.9",
    "Origin": "https://linkvertise.com",
    "X-Requested-With": "XMLHttpRequest",
    "Sec-Fetch-Site": "same-site",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Dest": "empty",
    "Connection": "keep-alive",
    "TE": "trailers"
}

def extract_link_id(obj):
    if not obj:
        return None
    if isinstance(obj, dict):
        if obj.get("success") is False and "data" in obj and obj.get("data") == []:
            return None
        d = obj.get("data")
        if isinstance(d, dict):
            link = d.get("link")
            if isinstance(link, dict) and "id" in link:
                return link.get("id")
            if isinstance(link, list) and len(link) > 0 and isinstance(link[0], dict) and "id" in link[0]:
                return link[0].get("id")
            for key in ("linkId","link_id","linkid","id"):
                if key in d and isinstance(d.get(key), (str,int)):
                    return d.get(key)
        if isinstance(d, list):
            for item in d:
                if isinstance(item, dict):
                    found = extract_link_id(item)
                    if found:
                        return found
    if isinstance(obj, list):
        for item in obj:
            if isinstance(item, dict):
                found = extract_link_id(item)
                if found:
                    return found
    return None

def extract_target(obj):
    if not obj:
        return None
    if isinstance(obj, dict):
        d = obj.get("data")
        if isinstance(d, dict):
            t = d.get("target")
            if isinstance(t, str) and t:
                return t
            if isinstance(t, dict):
                for key in ("url","target","destination","link"):
                    if key in t and isinstance(t.get(key), str):
                        return t.get(key)
            if isinstance(t, list) and len(t) > 0:
                first = t[0]
                if isinstance(first, str):
                    return first
                if isinstance(first, dict):
                    for key in ("target","url","link"):
                        if key in first and isinstance(first.get(key), str):
                            return first.get(key)
        if isinstance(d, list):
            for item in d:
                found = extract_target(item)
                if found:
                    return found
    if isinstance(obj, list):
        for item in obj:
            found = extract_target(item)
            if found:
                return found
    return None

def find_urls_in_text(text):
    if not text:
        return []
    urls = re.findall(r'https?://[A-Za-z0-9\-\._~:/\?#\[\]@!\$&\'\(\)\*\+,;=%]+', text)
    unique = []
    for u in urls:
        if u not in unique:
            unique.append(u)
    return unique

def random_ip():
    return '.'.join(str(random.randint(1,254)) for _ in range(4))

def bypass_linkvertise(original_url):
    try:
        domains = ["linkvertise.com", "direct-link.net", "link-target.net", "link-to.net", "link-center.net", "link-hub.net", "up-to-down.net"]
        pattern = '|'.join(re.escape(d) for d in domains)
        match = re.search(rf'(?:https?://)?(?:www\.)?(?:{pattern})/(\d+/[^/?#]+)', original_url)
        if not match:
            return {"success": False, "error": "Invalid Linkvertise URL"}
        path = match.group(1).rstrip('/')
        session = requests.Session()
        session.headers.update(BASE_HEADERS)
        session.headers.update({"Referer": "https://linkvertise.com/"})
        try:
            session.get("https://publisher.linkvertise.com/", timeout=8)
        except Exception:
            pass
        try:
            session.get(original_url, timeout=10, allow_redirects=True)
        except Exception:
            pass
        static_url = f"https://publisher.linkvertise.com/api/v1/redirect/link/static/{path}"
        hdrs = dict(session.headers)
        hdrs.update({"Referer": original_url, "X-Forwarded-For": random_ip(), "True-Client-IP": random_ip()})
        try:
            resp = session.get(static_url, headers=hdrs, timeout=10)
        except Exception as e:
            return {"success": False, "error": "Static request exception", "exception": str(e)}
        if resp.status_code != 200:
            return {"success": False, "error": f"Static request failed ({resp.status_code})", "status_code": resp.status_code, "body": resp.text[:1000]}
        static_data = None
        try:
            static_data = resp.json()
        except Exception:
            static_data = None
        link_id = extract_link_id(static_data)
        if not link_id:
            try:
                r2 = session.get(original_url, timeout=10, allow_redirects=True)
                html = r2.text if r2 is not None else ""
            except Exception:
                html = ""
            link_from_html = None
            m = re.search(r'publisher\.linkvertise\.com\/api\/v1\/redirect\/link\/(\d+)\/', html, re.I)
            if m:
                link_from_html = m.group(1)
            if not link_from_html:
                m2 = re.search(r'["\']link(?:Id|_id|id)["\']\s*[:=]\s*["\']?(\d+)["\']?', html, re.I)
                if m2:
                    link_from_html = m2.group(1)
            if link_from_html:
                link_id = link_from_html
        if not link_id:
            numeric_from_path = path.split('/')[0] if '/' in path else path
            if numeric_from_path and re.fullmatch(r'\d+', numeric_from_path):
                link_id = numeric_from_path
        if not link_id:
            try:
                stimulate_urls = [
                    f"https://publisher.linkvertise.com/api/v1/redirect/link/{path}/countdown_impression?trafficOrigin=network",
                    f"https://publisher.linkvertise.com/api/v1/redirect/link/{path}/todo_impression?mobile=true&trafficOrigin=network",
                    f"https://publisher.linkvertise.com/api/v1/redirect/link/{path}/click?trafficOrigin=network"
                ]
                for u in stimulate_urls:
                    try:
                        session.get(u, headers=hdrs, timeout=6)
                    except Exception:
                        pass
                resp2 = session.get(static_url, headers=hdrs, timeout=10)
                if resp2.status_code == 200:
                    try:
                        static_data = resp2.json()
                    except Exception:
                        static_data = None
                    link_id = extract_link_id(static_data)
            except Exception:
                pass
        if not link_id:
            alternative_keys = []
            if isinstance(static_data, dict):
                alternative_keys = [k for k in static_data.keys() if k.lower().find("link")!=-1 or k.lower().find("id")!=-1 or k.lower().find("data")!=-1]
            return {"success": False, "error": "Could not extract link id from static response", "static_excerpt": json.dumps(static_data)[:1500], "alternative_keys": alternative_keys}
        try:
            lid = int(link_id) if isinstance(link_id, (str,)) and str(link_id).isdigit() else link_id
        except Exception:
            lid = link_id
        payload = {"timestamp": int(time.time() * 1000), "random": "6548307", "link_id": lid}
        serial = base64.b64encode(json.dumps(payload).encode("utf-8")).decode("utf-8")
        target_url = f"https://publisher.linkvertise.com/api/v1/redirect/link/{path}/target?serial={serial}"
        try:
            resp = session.get(target_url, headers=hdrs, timeout=10)
        except Exception as e:
            return {"success": False, "error": "Target request exception", "exception": str(e)}
        if resp.status_code != 200:
            return {"success": False, "error": f"Target request failed ({resp.status_code})", "status_code": resp.status_code, "body": resp.text[:1000]}
        target_data = None
        try:
            target_data = resp.json()
        except Exception:
            target_data = None
        destination = extract_target(target_data)
        if destination:
            return {"success": True, "destination": destination, "method": "api_serial"}
        try:
            r3 = session.get(original_url, timeout=10, allow_redirects=True)
            html = r3.text if r3 is not None else ""
            urls = find_urls_in_text(html)
            candidate = None
            for u in urls:
                if re.search(r'\.(zip|rar|exe|pdf|jpg|png|mp4|torrent|mkv|iso)\b', u, re.I):
                    candidate = u
                    break
            if not candidate and urls:
                for u in urls:
                    if "linkvertise" not in u and "publisher.linkvertise" not in u:
                        candidate = u
                        break
            if candidate:
                return {"success": True, "destination": candidate, "method": "html_scan"}
        except Exception:
            pass
        return {"success": False, "error": "No target found in response", "target_excerpt": json.dumps(target_data)[:1500]}
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.route('/bypass')
def api_bypass():
    url = request.args.get('url')
    if not url:
        return jsonify({"success": False, "error": "Missing 'url' parameter"}), 400
    result = bypass_linkvertise(url)
    return jsonify(result)
