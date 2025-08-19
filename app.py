from flask import Flask, request, jsonify, render_template, abort
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from zoneinfo import ZoneInfo
import os

app = Flask(__name__)

# 環境変数や設定に応じてDB URIを切り替え
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///scores.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# スコアモデル（テーブル名はscores）
class Score(db.Model):
    __tablename__ = 'scores'
    id = db.Column(db.Integer, primary_key=True)
    game_id = db.Column(db.String(64), index=True, nullable=False)
    username = db.Column(db.String(64), nullable=False)
    score = db.Column(db.Integer, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    change = db.Column(db.String(4), default='', nullable=True)  # new, ↑, ↓ など

    __table_args__ = (
        db.UniqueConstraint('game_id', 'username', name='unique_game_user'),
    )

@app.template_filter('to_jst')
def to_jst(dt):
    if dt is None:
        return ''
    return dt.replace(tzinfo=ZoneInfo('UTC')).astimezone(ZoneInfo('Asia/Tokyo')).strftime('%Y-%m-%d %H:%M:%S')

# 初回起動時にテーブル作成
with app.app_context():
    db.create_all()

ALLOWED_IPS = ['127.0.0.1', '::1',
    '180.44.146.151',
    '153.177.163.237',
    '192.174.128.170',
    '10.152.211.180']

@app.before_request
def limit_remote_addr():
    client_ip = request.remote_addr
    if client_ip not in ALLOWED_IPS:
        abort(403)

def get_rankings(game_id):
    # game_idのスコアをスコア降順で取得
    return Score.query.filter_by(game_id=game_id).order_by(Score.score.desc(), Score.timestamp.asc()).all()

def find_user_rank(rankings, username):
    # usernameの順位を0始まりで返す。なければNone
    for i, s in enumerate(rankings):
        if s.username == username:
            return i
    return None

@app.route('/submit', methods=['POST'])
def submit_score():
    content = request.get_json()
    game_id = content['game_id']
    username = content['username']
    new_score = content['score']

    # 現状のランキング取得
    rankings = get_rankings(game_id)

    # 既存ユーザーのスコアを取得
    existing = Score.query.filter_by(game_id=game_id, username=username).first()
    flagRankChange=False

    if existing is None:
        # 新規ユーザー
        score_entry = Score(game_id=game_id, username=username, score=new_score, timestamp=datetime.utcnow(), change='New')
        db.session.add(score_entry)
        db.session.commit()
        flagRankChange=True
        new_rankings = get_rankings(game_id)
        new_rank = find_user_rank(new_rankings, username)
    else:
        # 既存ユーザーの前回スコアと順位
        old_score = existing.score
        old_rank = find_user_rank(rankings, username)

        if new_score > old_score:
            # スコア更新
            existing.score = new_score
            existing.timestamp = datetime.utcnow()
            #existing.timestamp = datetime.utcnow().replace(tzinfo=ZoneInfo('UTC')).astimezone(ZoneInfo('Asia/Tokyo'))
            # 更新後のランキングでの順位を調べるため、一旦コミットしてから再取得
            db.session.commit()
            new_rankings = get_rankings(game_id)
            new_rank = find_user_rank(new_rankings, username)

            # 変化判定
            if old_rank is None:
                # 以前なかった場合はnew（理論上ありえないけど念のため）
                existing.change = 'New'
                #flagRankChange=True
            else:
                if new_rank < old_rank:
                    existing.change = '↑'
                    flagRankChange=True
                elif new_rank > old_rank:
                    existing.change = '↓'
                else:
                    existing.change = '→'
            db.session.commit()
        else:
            # スコアが更新されていない場合は変化なし
            existing.change = '→'
            db.session.commit()

    if flagRankChange:
        # 1. 古いランキング辞書（username → 順位）
        old_ranks = {s.username: i for i, s in enumerate(rankings)}
        # 2. 新しいランキング取得
        #new_rankings = get_rankings(game_id)

        # 3. 新しいランキング辞書（username → 順位）
        new_ranks = {s.username: i for i, s in enumerate(new_rankings)}
        # 4. すべてのユーザーについて順位の変動をチェック
        for s in new_rankings:
            username = s.username
            old_rank = old_ranks.get(username)
            new_rank = new_ranks[username]
            if old_rank is None:
                # 新規ユーザー（すでに 'new' 設定済みのはず）
                continue
            elif new_rank > old_rank:
                s.change = '↓'
            elif new_rank < old_rank:
                s.change = '↑'
            else:
                s.change = '→'  # 順位変わらず
        db.session.commit()

    # 送信後のトップ10スコアを返す
    top_scores = Score.query.filter_by(game_id=game_id).order_by(Score.score.desc(), Score.timestamp.asc()).limit(10).all()
    print(top_scores)
    # JSON用に整形
    result = []
    for s in top_scores:
        result.append({
            'username': s.username,
            'score': s.score,
            'timestamp': s.timestamp.isoformat(),
            'change': s.change
        })

    return jsonify({'status': 'success', 'top_scores': result})

@app.route('/ranking/<game_id>')
def get_ranking(game_id):
    rankings = get_rankings(game_id)
    result = []
    for s in rankings:
        result.append({
            'username': s.username,
            'score': s.score,
            'timestamp': s.timestamp.isoformat(),
            'change': s.change
        })
    return jsonify(result)

@app.route('/<game_id>')
def show_ranking(game_id):
    rankings = get_rankings(game_id)
    return render_template('ranking2.html', game_id=game_id, ranking=rankings)

if __name__ == '__main__':
    app.run()

