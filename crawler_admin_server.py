#!/usr/bin/env python3
"""
爬虫管理台 Web 服务器
"""
from flask import Flask, send_file, request, jsonify
import requests
import os

app = Flask(__name__)

# 后端 API 地址
BACKEND_API = "http://localhost:8000/api/v1/crawler"

@app.route('/')
def index():
    """监控台主页"""
    return send_file("/opt/shared_cfo/crawler_admin/index.html")

@app.route('/api/<path:path>', methods=['GET', 'POST'])
def proxy(path):
    """代理 API 请求到后端"""
    url = f"{BACKEND_API}/{path}"

    try:
        if request.method == 'POST':
            resp = requests.post(url, json=request.get_json(), timeout=30)
        else:
            # 处理查询参数
            resp = requests.get(url, params=request.args.to_dict(), timeout=30)

        return jsonify(resp.json()), resp.status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    print("🚀 爬虫管理台启动中...")
    print("📍 访问地址: http://120.78.5.4:5000")
    print("🔧 后端 API: http://localhost:8000")
    app.run(host='0.0.0.0', port=5000, debug=False)
