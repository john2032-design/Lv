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

def bypass_linkvertise(url):
    try:
        domains = ["linkvertise.com", "direct-link.net", "link-target.net", "link-to.net", "link-center.net", "link-hub.net", "up-to-down.net"]
        pattern = '|'.join(re.escape(d) for d in domains)
        match = re.search(rf'({pattern})/(\d+/[^/?]+)', url)
        if not match:
            return {"success": False, "error": "Invalid Linkvertise URL"}
        path = match.group(2).rstrip('/')
        static_url = f"https://publisher.linkvertise.com/api/v1/redirect/link/static/{path}"
        resp = requests.get(static_url, headers=HEADERS, timeout=10)
        if resp.status_code != 200:
            return {"success": False, "error": f"Static request failed ({resp.status_code})"}
        data = resp.json()
        link_id = data["data"]["link"]["id"]
        payload = {"timestamp": int(time.time() * 1000), "random": "6548307", "link_id": link_id}
        serial = base64.b64encode(json.dumps(payload).encode("utf-8")).decode("utf-8")
        target_url = f"https://publisher.linkvertise.com/api/v1/redirect/link/{path}/target?serial={serial}"
        resp = requests.get(target_url, headers=HEADERS, timeout=10)
        if resp.status_code != 200:
            return {"success": False, "error": f"Target request failed ({resp.status_code})"}
        data = resp.json()
        destination = data.get("data", {}).get("target")
        if not destination:
            return {"success": False, "error": "No target found in response"}
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
