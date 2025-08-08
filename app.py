from flask import Flask, request, jsonify, render_template,abort
import json
import os

app = Flask(__name__)

# ランキングデータの保存ファイル
DATA_FILE = 'scores.json'

# 初期化
if not os.path.exists(DATA_FILE):
    with open(DATA_FILE, 'w') as f:
        json.dump({}, f)

def load_data():
    with open(DATA_FILE, 'r') as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f, indent=2)

def get_client_ip():
    forwarded_for = request.headers.get('X-Forwarded-For', '')
    ip = forwarded_for.split(',')[0] if forwarded_for else request.remote_addr
    return ip

ALLOWED_IPS = ['127.0.0.1',        # IPv4 localhost
    '::1',
    '180.44.146.151',   #  wlan
    '192.174.128.170', #proxy
    '10.152.211.180']  # ← 調べたプロキシのIPをここに入れる

@app.before_request
def limit_remote_addr():
    client_ip = request.remote_addr
    if client_ip not in ALLOWED_IPS:
        abort(403)  # アクセス拒否


@app.route('/submit', methods=['POST'])
def submit_score():
    content = request.get_json()
    game_id = content['game_id']
    username = content['username']
    score = content['score']

    data = load_data()
    if game_id not in data:
        data[game_id] = []

    # 更新 or 追加
    existing = next((entry for entry in data[game_id] if entry['username'] == username), None)
    if existing:
        if score > existing['score']:
            existing['score'] = score
    else:
        data[game_id].append({'username': username, 'score': score})

    # スコア降順でソート
    data[game_id].sort(key=lambda x: x['score'], reverse=True)
    top_scores = data[game_id][:10]
    save_data(data)
    return jsonify({'status': 'success',
                    'top_scores': top_scores })

@app.route('/ranking/<game_id>')
def get_ranking(game_id):
    data = load_data()
    ranking = data.get(game_id, [])
    return jsonify(ranking)

@app.route('/<game_id>')
def show_ranking(game_id):
    data = load_data()
    ranking = data.get(game_id, [])
    return render_template('ranking.html', game_id=game_id, ranking=ranking)

if __name__ == '__main__':
    app.run()
