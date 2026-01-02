from flask import Flask, request, jsonify
import requests
import json
import base64
import time
import re

app = Flask(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://linkvertise.com/",
    "Origin": "https://linkvertise.com",
    "X-Requested-With": "XMLHttpRequest",
    "Sec-Fetch-Site": "same-site",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Dest": "empty"
}

def extract_link_id(obj):
    if not obj:
        return None
    if isinstance(obj, dict):
        d = obj.get("data")
        if isinstance(d, dict):
            link = d.get("link")
            if isinstance(link, dict) and "id" in link:
                return link.get("id")
            if isinstance(link, list) and len(link) > 0 and isinstance(link[0], dict) and "id" in link[0]:
                return link[0].get("id")
            if "linkId" in d and isinstance(d.get("linkId"), (str, int)):
                return d.get("linkId")
            if "link_id" in d and isinstance(d.get("link_id"), (str, int)):
                return d.get("link_id")
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
                if "url" in t and isinstance(t["url"], str):
                    return t["url"]
                if "target" in t and isinstance(t["target"], str):
                    return t["target"]
            if isinstance(t, list) and len(t) > 0:
                first = t[0]
                if isinstance(first, str):
                    return first
                if isinstance(first, dict) and "target" in first and isinstance(first["target"], str):
                    return first["target"]
                if isinstance(first, dict) and "url" in first and isinstance(first["url"], str):
                    return first["url"]
        if isinstance(d, list):
            for item in d:
                if isinstance(item, dict):
                    found = extract_target(item)
                    if found:
                        return found
    if isinstance(obj, list):
        for item in obj:
            found = extract_target(item)
            if found:
                return found
    return None

def parse_linkid_from_html(html):
    if not html:
        return None
    patterns = [
        r'"linkId"\s*:\s*["\']?(\d+)["\']?',
        r'"link_id"\s*:\s*["\']?(\d+)["\']?',
        r'data-link-id\s*=\s*["\']?(\d+)["\']?',
        r'linkId\s*=\s*["\']?(\d+)["\']?',
        r'link_id\s*=\s*["\']?(\d+)["\']?'
    ]
    for p in patterns:
        m = re.search(p, html)
        if m:
            return m.group(1)
    return None

def stimulate_linkvertise(session, path):
    urls = [
        f"https://publisher.linkvertise.com/api/v1/redirect/link/{path}/countdown_impression?trafficOrigin=network",
        f"https://publisher.linkvertise.com/api/v1/redirect/link/{path}/todo_impression?mobile=true&trafficOrigin=network",
        f"https://publisher.linkvertise.com/api/v1/redirect/link/{path}/click?trafficOrigin=network"
    ]
    for u in urls:
        try:
            session.get(u, headers=HEADERS, timeout=8)
        except Exception:
            pass

def bypass_linkvertise(original_url):
    try:
        domains = ["linkvertise.com", "direct-link.net", "link-target.net", "link-to.net", "link-center.net", "link-hub.net", "up-to-down.net"]
        pattern = '|'.join(re.escape(d) for d in domains)
        match = re.search(rf'(?:https?://)?(?:www\.)?(?:{pattern})/(\d+/[^/?#]+)', original_url)
        if not match:
            return {"success": False, "error": "Invalid Linkvertise URL"}
        path = match.group(1).rstrip('/')
        session = requests.Session()
        session.headers.update(HEADERS)
        try:
            session.get(original_url, timeout=10, allow_redirects=True)
        except Exception:
            pass
        static_url = f"https://publisher.linkvertise.com/api/v1/redirect/link/static/{path}"
        try:
            resp = session.get(static_url, timeout=10)
        except Exception as e:
            return {"success": False, "error": "Static request exception", "exception": str(e)}
        if resp.status_code != 200:
            return {"success": False, "error": f"Static request failed ({resp.status_code})", "status_code": resp.status_code, "body": resp.text[:1000]}
        try:
            static_data = resp.json()
        except Exception:
            static_data = None
        link_id = extract_link_id(static_data)
        if not link_id:
            html_linkid = None
            try:
                r2 = session.get(original_url, timeout=10, allow_redirects=True)
                html_linkid = parse_linkid_from_html(r2.text)
            except Exception:
                html_linkid = None
            if html_linkid:
                link_id = html_linkid
            else:
                stimulate_linkvertise(session, path)
                try:
                    resp2 = session.get(static_url, timeout=10)
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
        payload = {"timestamp": int(time.time() * 1000), "random": "6548307", "link_id": int(link_id) if isinstance(link_id, (str,)) and link_id.isdigit() else link_id}
        serial = base64.b64encode(json.dumps(payload).encode("utf-8")).decode("utf-8")
        target_url = f"https://publisher.linkvertise.com/api/v1/redirect/link/{path}/target?serial={serial}"
        try:
            resp = session.get(target_url, timeout=10)
        except Exception as e:
            return {"success": False, "error": "Target request exception", "exception": str(e)}
        if resp.status_code != 200:
            return {"success": False, "error": f"Target request failed ({resp.status_code})", "status_code": resp.status_code, "body": resp.text[:1000]}
        try:
            target_data = resp.json()
        except Exception:
            target_data = None
        destination = extract_target(target_data)
        if not destination:
            return {"success": False, "error": "No target found in response", "target_excerpt": json.dumps(target_data)[:1500]}
        return {"success": True, "destination": destination}
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.route('/bypass')
def api_bypass():
    url = request.args.get('url')
    if not url:
        return jsonify({"success": False, "error": "Missing 'url' parameter"}), 400
    result = bypass_linkvertise(url)
    return jsonify(result)
