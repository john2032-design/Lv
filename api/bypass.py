from flask import Flask, request, jsonify
import requests
import json
import base64
import time
import re

app = Flask(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://linkvertise.com/",
    "Origin": "https://linkvertise.com"
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
        if isinstance(d, list):
            for item in d:
                if isinstance(item, dict):
                    link = item.get("link")
                    if isinstance(link, dict) and "id" in link:
                        return link.get("id")
                    if isinstance(link, list) and len(link) > 0 and isinstance(link[0], dict) and "id" in link[0]:
                        return link[0].get("id")
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
            if isinstance(t, list) and len(t) > 0:
                first = t[0]
                if isinstance(first, str):
                    return first
                if isinstance(first, dict) and "target" in first and isinstance(first["target"], str):
                    return first["target"]
                if isinstance(first, dict) and "url" in first and isinstance(first["url"], str):
                    return first["url"]
        if isinstance(d, list) and len(d) > 0:
            for item in d:
                if isinstance(item, dict):
                    t = item.get("target")
                    if isinstance(t, str):
                        return t
                    if isinstance(t, list) and len(t) > 0 and isinstance(t[0], str):
                        return t[0]
                    if isinstance(t, dict) and "url" in t and isinstance(t["url"], str):
                        return t["url"]
    return None

def bypass_linkvertise(url):
    try:
        domains = ["linkvertise.com", "direct-link.net", "link-target.net", "link-to.net", "link-center.net", "link-hub.net", "up-to-down.net"]
        pattern = '|'.join(re.escape(d) for d in domains)
        match = re.search(rf'(?:https?://)?(?:www\.)?(?:{pattern})/(\d+/[^/?#]+)', url)
        if not match:
            return {"success": False, "error": "Invalid Linkvertise URL"}
        path = match.group(1).rstrip('/')
        static_url = f"https://publisher.linkvertise.com/api/v1/redirect/link/static/{path}"
        resp = requests.get(static_url, headers=HEADERS, timeout=10)
        if resp.status_code != 200:
            return {"success": False, "error": f"Static request failed ({resp.status_code})", "status_code": resp.status_code, "body": resp.text[:1000]}
        static_data = resp.json()
        link_id = extract_link_id(static_data)
        if not link_id:
            return {"success": False, "error": "Could not extract link id from static response", "static_excerpt": json.dumps(static_data)[:1500]}
        payload = {"timestamp": int(time.time() * 1000), "random": "6548307", "link_id": link_id}
        serial = base64.b64encode(json.dumps(payload).encode("utf-8")).decode("utf-8")
        target_url = f"https://publisher.linkvertise.com/api/v1/redirect/link/{path}/target?serial={serial}"
        resp = requests.get(target_url, headers=HEADERS, timeout=10)
        if resp.status_code != 200:
            return {"success": False, "error": f"Target request failed ({resp.status_code})", "status_code": resp.status_code, "body": resp.text[:1000]}
        target_data = resp.json()
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
