# 🔽🔽🔽 必要なモジュールをインポート 🔽🔽🔽
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, send_from_directory # send_from_directory をインポート
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from flask_socketio import SocketIO, emit, join_room, leave_room # join_room, leave_room をインポート
import os # os をインポート
import re # ◀️ 追加: タグ抽出のための正規表現
from werkzeug.utils import secure_filename # secure_filename をインポート
from sqlalchemy import func, or_, distinct
from sqlalchemy.orm import joinedload, subqueryload # ◀️ N+1問題対策: subqueryload をインポート
from collections import defaultdict
from flask_migrate import Migrate # Migrate
from functools import wraps # ◀️ 追加: デコレータに必要
# ▲▲▲ インポート完了 ▲▲▲

app = Flask(__name__)
app.secret_key = "secret_key_for_demo"
socketio = SocketIO(app, async_mode='gevent')

# 🔽🔽🔽 このフィルタ定義を追加 🔽🔽🔽
@app.template_filter('remove_tags')
def remove_tags_filter(s):
    """
    Jinja2テンプレートフィルタ: 文字列から #タグ を除去する
    """
    if not s:
        return s
    # 既存のタグ抽出関数(extract_and_get_tags)と同じ正規表現を使用
    return re.sub(r'#([a-zA-Z0-9_ぁ-んァ-ヶー一-龠]+)', '', s).strip()
# 🔼🔼🔼 追加完了 🔼🔼🔼

S3_BUCKET_NAME = os.environ.get('S3_BUCKET_NAME', 'your-app-uploads-xxxx')
# ====== 🔽 追加: ファイルアップロードの設定 🔽 ======
# UPLOAD_FOLDER = 'static/uploads' # アップロード先フォルダ
# ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'} # 許可する拡張子
# app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# アップロード用ディレクトリがなければ作成
# if not os.path.exists(UPLOAD_FOLDER):
#     os.makedirs(UPLOAD_FOLDER)
# ====== 🔼 追加完了 🔼 ======

# ====== 既存の設定 ======
db_url = os.environ.get("DATABASE_URL")

if db_url:
    # RenderのデータベースURLは 'postgres://' で始まることがありますが、
    # SQLAlchemyは 'postgresql://' を推奨するため、置換します。
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)
    app.config["SQLALCHEMY_DATABASE_URI"] = db_url
else:
    # 環境変数がない場合（ローカル実行時など）は、ローカルの設定を使う
    app.config["SQLALCHEMY_DATABASE_URI"] = "postgresql://postgres:postgres@localhost:5432/comm_site"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

try:
    from psycogreen.gevent import patch_psycopg
    patch_psycopg()
except ImportError:
    pass # psycogreen がインストールされていなければ何もしない
db = SQLAlchemy(app)
migrate = Migrate(app, db)

POSTS_PER_PAGE = 10

# ====== 🔽 追加: フォロー関係を定義する中間テーブル 🔽 ======
follow = db.Table('follow',
    db.Column('follower_id', db.Integer, db.ForeignKey('User.user_id'), primary_key=True),
    db.Column('followed_id', db.Integer, db.ForeignKey('User.user_id'), primary_key=True)
)
# ====== 🔼 追加完了 🔼 ======

# ====== 🔽 追加: ブロック関係を定義する中間テーブル 🔽 ======
blocks = db.Table('blocks',
    db.Column('blocker_id', db.Integer, db.ForeignKey('User.user_id'), primary_key=True),
    db.Column('blocked_id', db.Integer, db.ForeignKey('User.user_id'), primary_key=True)
)
# ====== 🔼 追加完了 🔼 ======

# 🔽🔽🔽 タグ機能のためのDBテーブル定義を追加 🔽🔽🔽

# 投稿とタグの中間テーブル
post_tags = db.Table('post_tags',
    db.Column('post_id', db.Integer, db.ForeignKey('post.post_id'), primary_key=True),
    db.Column('tag_id', db.Integer, db.ForeignKey('tag.tag_id'), primary_key=True)
)

# コメントとタグの中間テーブル
comment_tags = db.Table('comment_tags',
    db.Column('comment_id', db.Integer, db.ForeignKey('comment.comment_id'), primary_key=True),
    db.Column('tag_id', db.Integer, db.ForeignKey('tag.tag_id'), primary_key=True)
)

# タグモデル
class Tag(db.Model):
    __tablename__ = "tag"
    tag_id = db.Column(db.Integer, primary_key=True)
    # タグ名はユニーク（一意）にし、検索しやすいようインデックスを貼る
    name = db.Column(db.String(100), unique=True, nullable=False, index=True)

# ▲▲▲ DBテーブル定義 完了 ▲▲▲


# ====== 🔽 モデルの修正・追加 🔽 ======
class User(db.Model):
    __tablename__ = "User"
    user_id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    name = db.Column(db.String(100), nullable=False)

    school_id = db.Column(db.Integer, db.ForeignKey("school.school_id"), nullable=False)
    role = db.Column(db.String(20), nullable=False)
    posts = db.relationship("Post", backref="author", lazy=True)
    school = db.relationship("School", backref="users", lazy=True)

    department_id = db.Column(db.Integer, db.ForeignKey("department.department_id"), nullable=True)
    last_login = db.Column(db.DateTime, nullable=True)
    year = db.Column(db.Integer, nullable=True)

    department = db.relationship("Department", backref="users")

    icon_path = db.Column(db.String(255), nullable=True, default='default_icon.png')
    header_path = db.Column(db.String(255), nullable=True)
    introduction = db.Column(db.Text, nullable=True)
    tags = db.Column(db.String(255), nullable=True)

    # ◀️ 追加: 機能制限フラグ
    is_restricted = db.Column(db.Boolean, default=False, nullable=False)
    gomoku_score = db.Column(db.Integer, default=0, nullable=False)

    # ====== 🔽 追加: フォロー機能のためのリレーションシップ 🔽 ======
    followed = db.relationship(
        'User', secondary=follow,
        primaryjoin=(follow.c.follower_id == user_id),
        secondaryjoin=(follow.c.followed_id == user_id),
        backref=db.backref('followers', lazy='dynamic'), lazy='dynamic')
    # ====== 🔼 追加完了 🔼 ======

    # ====== 🔽 追加: ブロック機能のためのリレーションシップ 🔽 ======
    blocked_users = db.relationship(
        'User', secondary=blocks,
        primaryjoin=(blocks.c.blocker_id == user_id),
        secondaryjoin=(blocks.c.blocked_id == user_id),
        backref=db.backref('blocked_by', lazy='dynamic'), lazy='dynamic')
    # ====== 🔼 追加完了 🔼 ======

# ◀️ 追加: 通報情報を格納するモデル
class Report(db.Model):
    __tablename__ = "report"
    report_id = db.Column(db.Integer, primary_key=True)
    reporter_id = db.Column(db.Integer, db.ForeignKey("User.user_id"), nullable=False)
    reported_user_id = db.Column(db.Integer, db.ForeignKey("User.user_id"), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey("post.post_id"), nullable=True)
    comment_id = db.Column(db.Integer, db.ForeignKey("comment.comment_id"), nullable=True)
    reason = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now)
    is_resolved = db.Column(db.Boolean, default=False, nullable=False)

    reporter = db.relationship("User", foreign_keys=[reporter_id], backref="sent_reports")
    reported_user = db.relationship("User", foreign_keys=[reported_user_id], backref="received_reports")
    post = db.relationship("Post", backref="reports")
    comment = db.relationship("Comment", backref="reports")
# ====== 🔼 モデルの修正・追加完了 🔼 ======


class Department(db.Model):
    __tablename__ = "department"
    department_id = db.Column(db.Integer, primary_key=True)
    school_id = db.Column(db.Integer, nullable=False)
    department_name = db.Column(db.String(100), nullable=False)

class School(db.Model):
    __tablename__ = "school"
    school_id = db.Column(db.Integer, primary_key=True)
    school_name = db.Column(db.String(100), nullable=False)

class Post(db.Model):
    __tablename__ = "post"
    post_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("User.user_id"), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    scope = db.Column(db.String(50), nullable=False)
    
    # 🔽🔽🔽 PostとTagのリレーションシップを追加 🔽🔽🔽
    # lazy='subquery' にすることで、Post読み込み時にタグも効率的に読み込む
    tags = db.relationship('Tag', secondary=post_tags, lazy='subquery',
        backref=db.backref('posts', lazy='dynamic'))
    # ▲▲▲ 追加完了 ▲▲▲

class Comment(db.Model):
    __tablename__ = "comment"
    comment_id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey("post.post_id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("User.user_id"), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now)

    post = db.relationship("Post", backref="comments")
    user = db.relationship("User", backref="comments")

    # 🔽🔽🔽 CommentとTagのリレーションシップを追加 🔽🔽🔽
    tags = db.relationship('Tag', secondary=comment_tags, lazy='subquery',
        backref=db.backref('comments', lazy='dynamic'))
    # ▲▲▲ 追加完了 ▲▲▲

# app.py のモデル定義セクションに追加

class DirectMessage(db.Model):
    __tablename__ = "direct_message"
    message_id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey("User.user_id"), nullable=False)
    recipient_id = db.Column(db.Integer, db.ForeignKey("User.user_id"), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now)
    read_at = db.Column(db.DateTime, nullable=True)

    sender = db.relationship("User", foreign_keys=[sender_id], backref="sent_messages")
    recipient = db.relationship("User", foreign_keys=[recipient_id], backref="received_messages")

class Reaction(db.Model):
    __tablename__ = "reaction"
    reaction_id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey("post.post_id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("User.user_id"), nullable=False)
    # 'like' または絵文字そのものを保存
    reaction_type = db.Column(db.String(10), nullable=False)

    post = db.relationship("Post", backref=db.backref("reactions", cascade="all, delete-orphan"))
    user = db.relationship("User", backref="reactions")

    # ユーザーは1つの投稿に同じリアクションを1度しかできないように制約を設定
    __table_args__ = (db.UniqueConstraint('post_id', 'user_id', 'reaction_type', name='_user_post_reaction_uc'),)

class QA(db.Model):
    __tablename__ = "qa"
    qa_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("User.user_id"), nullable=False)
    question = db.Column(db.Text, nullable=False)
    answer = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.now)
    answered_at = db.Column(db.DateTime)

    user = db.relationship("User", backref="questions")

# 🔽🔽🔽 タグをDBから検索・作成するヘルパー関数を追加 🔽🔽🔽
def extract_and_get_tags(content):
    """
    コンテンツから #タグ を抽出し、DBから該当タグを取得または新規作成する。
    日本語タグにも対応。
    """
    # 日本語、英数字、アンダースコアに対応した正規表現
    tag_names = re.findall(r'#([a-zA-Z0-9_ぁ-んァ-ヶー一-龠]+)', content)
    
    # 重複を削除し、長すぎるタグを除外
    unique_names = {name for name in tag_names if len(name) <= 50}
    
    if not unique_names:
        return []

    # 既存のタグをDBから一括取得
    existing_tags = Tag.query.filter(Tag.name.in_(unique_names)).all()
    existing_names = {t.name for t in existing_tags}
    
    final_tags = list(existing_tags)
    
    # DBに存在しない新しいタグを作成
    new_names = unique_names - existing_names
    for name in new_names:
        new_tag = Tag(name=name)
        db.session.add(new_tag)
        final_tags.append(new_tag)
    
    # 呼び出し元のcommit()でDBに保存される
    return final_tags
# ▲▲▲ ヘルパー関数 完了 ▲▲▲


# ====== 🔽 ブロックリスト取得のヘルパー関数 🔽 ======
def get_blocked_user_ids():
    """現在ログイン中のユーザーがブロックしている、またはされているユーザーIDのリストを返す"""
    if "user_id" not in session:
        return []

    current_user = User.query.get(session["user_id"])
    if not current_user:
        return []

    blocked_ids = {u.user_id for u in current_user.blocked_users}
    blocked_by_ids = {u.user_id for u in current_user.blocked_by}

    return list(blocked_ids.union(blocked_by_ids))
# ====== 🔼 追加完了 🔼 ======


# ====== 🔽 変更: 機能制限チェック用のデコレータ 🔽 ======
def check_restriction(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" in session:
            user = User.query.get(session["user_id"])
            # ユーザーが制限されている場合
            if user and user.is_restricted:
                # 許可されたページリスト
                allowed_endpoints = ['notice_board', 'logout', 'login', 'static', 'uploaded_file', 'index']
                # 現在のアクセス先が許可リストにない場合、通知用掲示板へリダイレクト
                if request.endpoint not in allowed_endpoints:
                    # flashメッセージの代わりにセッションにフラグを立てる
                    session['show_restriction_modal'] = True
                    return redirect(url_for('notice_board'))
        return f(*args, **kwargs)
    return decorated_function
# ====== 🔼 変更完了 🔼 ======

# === 以下、ルートやSocketIOイベントハンドラなどを記述 ===

# ユーザーIDとセッションIDを管理するための辞書
user_sids = {}

## 五目並べ用のデータ構造
gomoku_waiting_player = None
gomoku_games = {}

@app.route("/game/gomoku")
@check_restriction
def gomoku_lobby():
    if "user_id" not in session:
        return redirect(url_for("login"))
    return render_template("gomoku.html")

@socketio.on('connect')
def handle_connect():
    user_id = session.get('user_id')
    if user_id:
        user_sids[user_id] = request.sid
        # ユーザー自身の部屋に入る（通知などに利用可能）
        join_room(user_id)

@app.route("/gomoku_ranking")
@check_restriction
def gomoku_ranking_page():
    if "user_id" not in session:
        return redirect(url_for("login"))

    # User テーブルをクエリ
    # スコアが 0 より大きいプレイヤーのみ表示 (あなたのリクエスト)
    # スコアの高い順 (desc) に並び替え
    # (N+1問題対策: school 情報も一緒にロード)
    rankers = User.query.options(
        joinedload(User.school)
    ).filter(
        User.gomoku_score > 0
    ).order_by(
        User.gomoku_score.desc()
    ).limit(20).all() # (例: 上位20名のみ表示)
    
    return render_template("gomoku_ranking.html", rankers=rankers)

@socketio.on('find_gomoku_game')
def handle_find_gomoku_game():
    global gomoku_waiting_player # グローバル変数を参照
    user_id = session.get("user_id")
    if not user_id:
        return 

    # 待機室にいるのが自分自身なら、何もしない
    if gomoku_waiting_player == user_id:
        return

    # 1. 待機室が空の場合
    if gomoku_waiting_player is None:
        gomoku_waiting_player = user_id
        # クライアントに「待機中」のステータスを送信
        emit('gomoku_status', {'message': '対戦相手を待っています...'}, room=request.sid)
    
    # 2. 待機室に誰かいる場合、対戦開始！
    else:
        player1_id = gomoku_waiting_player
        player2_id = user_id
        gomoku_waiting_player = None # 待機室を空にする

        # 両プレイヤーのソケットID (sid) を取得
        # (user_sids はDM機能 で既に使用中の辞書)
        player1_sid = user_sids.get(player1_id)
        player2_sid = user_sids.get(player2_id)

        # どちらかのプレイヤーが切断していた場合
        if not (player1_sid and player2_sid):
            # プレイヤー1を待機室に戻す
            gomoku_waiting_player = player1_id
            if player1_sid:
                emit('gomoku_status', {'message': '相手が切断しました。再度待機します...'}, room=player1_sid)
            return

        # 3. 新しいゲームルームを作成
        room_id = f"gomoku_{player1_id}_{player2_id}"
        game_state = {
            'board': [[None for _ in range(15)] for _ in range(15)], # 15x15 の碁盤
            'players': {player1_id: 'black', player2_id: 'white'}, # P1 が黒, P2 が白
            'turn': player1_id # P1 (黒) が先手
        }
        gomoku_games[room_id] = game_state # サーバー側でゲーム状態を保存

        # 4. 両プレイヤーを SocketIO のルームに参加させる
        join_room(room_id, sid=player1_sid)
        join_room(room_id, sid=player2_sid)

        # 5. P1 にゲーム開始を通知
        emit('gomoku_game_start', {
            'room_id': room_id,
            'opponent_name': User.query.get(player2_id).name, # P2の名前をP1に送信
            'your_color': 'black',
            'turn': player1_id
        }, room=player1_sid)
        
        # 6. P2 にゲーム開始を通知
        emit('gomoku_game_start', {
            'room_id': room_id,
            'opponent_name': User.query.get(player1_id).name, # P1の名前をP2に送信
            'your_color': 'white',
            'turn': player1_id
        }, room=player2_sid)


@socketio.on('make_gomoku_move')
def handle_gomoku_move(data):
    user_id = session.get("user_id")
    room_id = data.get("room_id")
    row = data.get("row")
    col = data.get("col")

    game = gomoku_games.get(room_id)

    # --- バリデーション (検証) ---
    if not game:
        return emit('gomoku_error', {'message': '無効なゲームです'})
    if game['turn'] != user_id:
        return emit('gomoku_error', {'message': 'あなたのターンではありません'})
    # 配列の範囲チェックを追加
    if not (0 <= row < 15 and 0 <= col < 15):
        return emit('gomoku_error', {'message': '無効な場所です'})
    if game['board'][row][col] is not None:
        return emit('gomoku_error', {'message': 'そこには既に石があります'})
    # --- 検証完了 ---

    # 1. サーバー側の碁盤に石を置く
    color = game['players'][user_id]
    game['board'][row][col] = color

    # 2. この一手（着手）をルーム全員にブロードキャスト（送信）
    emit('gomoku_move_made', {
        'row': row, 
        'col': col, 
        'color': color
    }, room=room_id)

    # 3. 勝敗判定 (最も難しいロジック)
    if check_gomoku_win(game['board'], row, col, color):
        winner = User.query.get(user_id)
        loser_id = [pid for pid in game['players'] if pid != user_id][0]
        loser = User.query.get(loser_id)

        # 4. スコアの加算/減算 (最低 0 ポイント)
        winner.gomoku_score += 10 # 勝ち +10
        loser.gomoku_score = max(0, loser.gomoku_score - 5) # 負け -5 (最低 0)
        db.session.commit()

        # 5. ゲーム終了をブロードキャスト
        emit('gomoku_game_over', {
            'winner_name': winner.name,
            'winner_score': winner.gomoku_score,
            'loser_score': loser.gomoku_score,
            'winner_id': winner.user_id
        }, room=room_id)
        
        # 6. サーバーからゲームルームを削除 (メモリ解放)
        if room_id in gomoku_games:
            del gomoku_games[room_id]
        
    else:
        # 7. ゲーム続行、ターンを交代
        next_player_id = [pid for pid in game['players'] if pid != user_id][0]
        game['turn'] = next_player_id
        
        # 8. 次のターンをブロードキャスト
        emit('gomoku_turn_update', {'turn': next_player_id}, room=room_id)


# 5連鎖をチェックするためのヘルパー関数
def check_gomoku_win(board, r, c, color):
    directions = [(0, 1), (1, 0), (1, 1), (1, -1)] # 水平, 垂直, 右下, 右上
    for dr, dc in directions:
        count = 1
        # 一方向にチェック
        for i in range(1, 5):
            nr, nc = r + dr*i, c + dc*i
            if 0 <= nr < 15 and 0 <= nc < 15 and board[nr][nc] == color:
                count += 1
            else:
                break
        # 反対方向にチェック
        for i in range(1, 5):
            nr, nc = r - dr*i, c - dc*i
            if 0 <= nr < 15 and 0 <= nc < 15 and board[nr][nc] == color:
                count += 1
            else:
                break
        
        if count >= 5:
            return True
    return False

# 🔽 プレイヤー切断時の処理 (disconnect ハンドラを修正) 🔽
@socketio.on('disconnect')
def handle_disconnect():
    global gomoku_waiting_player
    user_id = session.get('user_id')
    
    # DM用の処理 (既存)
    if user_id and user_id in user_sids:
        if request.sid == user_sids[user_id]:
            del user_sids[user_id]

    # 五目並べ待機中のプレイヤーが切断した場合
    if user_id and user_id == gomoku_waiting_player:
        gomoku_waiting_player = None

# ▼▼▼ ここからが「ゲーム中切断」の処理ロジック ▼▼▼
    game_to_remove = None
    opponent_sid = None
    winner = None
    loser = None

    # 1. すべてのゲームルームから切断者を探す
    for room_id, game in gomoku_games.items():
        if user_id in game['players']:
            game_to_remove = room_id
            
            # 2. 対戦相手 (opponent) を特定
            opponent_id = [pid for pid in game['players'] if pid != user_id][0]
            opponent_sid = user_sids.get(opponent_id)
            
            # 3. 対戦相手 (opponent) を勝者とする
            winner = User.query.get(opponent_id)
            loser = User.query.get(user_id) # user_id が切断者
            break # ゲームが見つかったらループを抜ける

    # 4. ゲームが見つかり、かつ相手がまだオンラインの場合
    if game_to_remove and opponent_sid and winner and loser:
        
        # 5. スコアを更新 (要望：勝ち+10, 負け-5, 最低0)
        winner.gomoku_score += 10
        loser.gomoku_score = max(0, loser.gomoku_score - 5)
        db.session.commit()

        # 6. 相手に「相手が切断したため勝利」と通知
        emit('gomoku_game_over', {
            'winner_name': winner.name,
            'winner_score': winner.gomoku_score,
            'loser_score': loser.gomoku_score,
            'winner_id': winner.user_id,
            'disconnected': True # ◀️ 切断フラグを追加
        }, room=opponent_sid) # 相手にだけ通知

        # 7. サーバーからこのゲームルームを削除
        if game_to_remove in gomoku_games:
            try:
                del gomoku_games[game_to_remove]
            except KeyError:
                pass # 既に削除済みの場合を考慮
    # ▲▲▲ 切断ロジック追加完了 ▲▲▲

# ====== 🔽 追加: DMメッセージ履歴取得API 🔽 ======
@app.route("/api/messages/<int:recipient_id>")
def get_messages(recipient_id):
    if "user_id" not in session:
        return jsonify({"error": "ログインが必要です"}), 401

    sender_id = session["user_id"]

    messages = DirectMessage.query.filter(
        or_(
            (DirectMessage.sender_id == sender_id) & (DirectMessage.recipient_id == recipient_id),
            (DirectMessage.sender_id == recipient_id) & (DirectMessage.recipient_id == sender_id)
        )
    ).order_by(DirectMessage.created_at.asc()).all()

    message_list = []
    for msg in messages:
        message_list.append({
            "message_id": msg.message_id,
            "sender_id": msg.sender_id,
            "recipient_id": msg.recipient_id,
            "content": msg.content,
            "created_at": msg.created_at.strftime('%Y/%m/%d %H:%M')
        })

    return jsonify(message_list)
# ====== 🔼 追加完了 🔼 ======

# ====== 🔽 追加: 会話履歴のあるユーザー一覧を取得するAPI 🔽 ======
@app.route('/api/conversations')
def get_conversations():
    if "user_id" not in session:
        return jsonify({"error": "ログインが必要です"}), 401

    user_id = session['user_id']

    # 自分が送信した相手のIDを取得
    sent_to_ids = db.session.query(distinct(DirectMessage.recipient_id)).filter(
        DirectMessage.sender_id == user_id
    )
    # 自分に送信してきた相手のIDを取得
    received_from_ids = db.session.query(distinct(DirectMessage.sender_id)).filter(
        DirectMessage.recipient_id == user_id
    )

    # 両方のIDを結合して、ユニークなIDリストを作成
    partner_ids_query = sent_to_ids.union(received_from_ids)

    # ユーザーオブジェクトを取得
    partners = User.query.filter(User.user_id.in_(partner_ids_query)).all()

    # フロントエンドで使いやすいように整形
    conversations = [
        {
            "user_id": partner.user_id,
            "name": partner.name,
            "icon_path": partner.icon_path if partner.icon_path and partner.icon_path.startswith('http') else None
        } for partner in partners
    ]

    return jsonify(conversations)
# ====== 🔼 追加完了 🔼 ======


# ====== 🔽 変更: DM送信用SocketIOイベントにアカウント制限チェックを追加 🔽 ======
@socketio.on('send_dm')
def handle_send_dm(data):
    if 'user_id' not in session:
        return

    sender_id = session['user_id']
    recipient_id = data.get('recipient_id')
    content = data.get('content')

    if not recipient_id or not content:
        return

    sender = User.query.get(sender_id)

    # ▼▼▼【ここから追加】アカウント制限のチェック ▼▼▼
    if sender and sender.is_restricted:
        emit('dm_error', {'message': 'アカウントが制限されているため、メッセージを送信できません。'}, room=request.sid)
        return
    # ▲▲▲【追加完了】▲▲▲

    recipient = User.query.get(recipient_id)

    # 相互にブロック関係をチェック
    is_blocking = sender.blocked_users.filter_by(user_id=recipient_id).first() is not None
    is_blocked_by = recipient.blocked_users.filter_by(user_id=sender_id).first() is not None

    if is_blocking or is_blocked_by:
        emit('dm_error', {'message': 'ブロックしている、またはブロックされているためメッセージを送信できません。'}, room=request.sid)
        return

    # メッセージをDBに保存
    new_message = DirectMessage(
        sender_id=sender_id,
        recipient_id=recipient_id,
        content=content
    )
    db.session.add(new_message)
    db.session.commit()

    # 送信者と受信者にメッセージを送信
    message_payload = {
        'message_id': new_message.message_id,
        'sender_id': sender_id,
        'recipient_id': recipient_id,
        'content': content,
        'created_at': new_message.created_at.strftime('%Y/%m/%d %H:%M')
    }

    # 受信者がオンラインなら直接送信
    recipient_sid = user_sids.get(recipient_id)
    if recipient_sid:
        emit('receive_dm', message_payload, room=recipient_sid)

    # 送信者自身にも送信（UI更新のため）
    emit('receive_dm', message_payload, room=request.sid)
# ====== 🔼 変更完了 🔼 ======

@app.route("/")
def index():
    if "role" in session:
        role = session.get("role")
        if role == "admin":
            return redirect(url_for("admin_dashboard"))
        if role == "student":
            return redirect(url_for("home"))
    return redirect(url_for("login"))

@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        student_id = request.form["username"]
        password = request.form["password"]

        user = User.query.filter_by(student_id=student_id).first()

        if user and check_password_hash(user.password_hash, password) or user and user.password_hash == password:
            school_info = School.query.filter_by(school_id=user.school_id).first()
            department_info = Department.query.filter_by(department_id=user.department_id).first()

            session["user_id"] = user.user_id
            session["student_id"] = user.student_id
            session["role"] = user.role
            session["name"] = user.name
            session["school_id"] = user.school_id
            session["school_name"] = school_info.school_name if school_info else "不明"
            session["department_name"] = department_info.department_name if department_info else "不明"
            session["year"] = user.year

            session["school_identifier"] = student_id[0]

            user.last_login = datetime.now()
            db.session.commit()

            if user.role == "student":
                return redirect(url_for("home"))
            elif user.role == "admin":
                return redirect(url_for("admin_dashboard"))

        error = "ユーザー名またはパスワードが違います"
        return render_template("login.html", error=error, username=student_id)


    return render_template("login.html")

@app.route("/home")
@check_restriction # ◀️ デコレータを追加
def home():
    return redirect(url_for("school_specific_board"))

@app.route("/home/school_wide")
@check_restriction # ◀️ デコレータを追加
def school_wide_board():
    if "role" in session and session["role"] == "student":
        page = request.args.get('page', 1, type=int)

        # 🔽 変更: ブロックしている/されているユーザーの投稿を除外
        blocked_ids = get_blocked_user_ids()
        
        # 🔽🔽🔽 N+1問題対策: 著者、タグ、コメント(＋著者)、コメントのタグ を一括読み込み 🔽🔽🔽
        posts_query = Post.query.options(
            joinedload(Post.author),
            subqueryload(Post.tags), 
            subqueryload(Post.comments).joinedload(Comment.user),
            subqueryload(Post.comments).subqueryload(Comment.tags)
        ).filter_by(scope="public")
        # ▲▲▲ 変更完了 ▲▲▲
        
        if blocked_ids:
            posts_query = posts_query.filter(Post.user_id.notin_(blocked_ids))

        posts_pagination = posts_query.order_by(Post.created_at.desc()).paginate(
            page=page, per_page=POSTS_PER_PAGE, error_out=False
        )
        # 🔼 変更完了

        posts = posts_pagination.items

        if posts:
            post_ids = [p.post_id for p in posts]
            user_id = session.get("user_id")

            reaction_counts = db.session.query(
                Reaction.post_id,
                Reaction.reaction_type,
                func.count(Reaction.reaction_id)
            ).filter(Reaction.post_id.in_(post_ids)).group_by(
                Reaction.post_id,
                Reaction.reaction_type
            ).all()

            reactions_by_post = defaultdict(dict)
            for post_id, emoji, count in reaction_counts:
                reactions_by_post[post_id][emoji] = count

            user_reactions_query = db.session.query(
                Reaction.post_id,
                Reaction.reaction_type
            ).filter(
                Reaction.post_id.in_(post_ids),
                Reaction.user_id == user_id
            ).all()

            user_reactions_set = set(user_reactions_query)

            for post in posts:
                post.reaction_counts = reactions_by_post.get(post.post_id, {})
                post.user_reacted_emojis = {emoji for pid, emoji in user_reactions_set if pid == post.post_id}

        return render_template("home.html",
                               user=session["name"],
                               posts=posts,
                               pagination=posts_pagination,
                               board_title="校舎間掲示板",
                               current_scope="public")
    return redirect(url_for("login"))


@app.route("/home/school_specific")
@check_restriction # ◀️ デコレータを追加
def school_specific_board():
    if "role" in session and session["role"] == "student":
        user_school_id = session.get("school_id")
        if user_school_id is None:
            return redirect(url_for("login"))

        # 🔽 変更: ブロックしている/されているユーザーの投稿を除外
        blocked_ids = get_blocked_user_ids()
        school_scope = f"school{user_school_id}"
        
        # 🔽🔽🔽 N+1問題対策: 著者、タグ、コメント(＋著者)、コメントのタグ を一括読み込み 🔽🔽🔽
        posts_query = Post.query.options(
            joinedload(Post.author),
            subqueryload(Post.tags), 
            subqueryload(Post.comments).joinedload(Comment.user),
            subqueryload(Post.comments).subqueryload(Comment.tags)
        ).filter_by(scope=school_scope)
        # ▲▲▲ 変更完了 ▲▲▲

        if blocked_ids:
            posts_query = posts_query.filter(Post.user_id.notin_(blocked_ids))

        page = request.args.get('page', 1, type=int)

        posts_pagination = posts_query.order_by(Post.created_at.desc()).paginate(
            page=page, per_page=POSTS_PER_PAGE, error_out=False
        )
        # 🔼 変更完了

        posts = posts_pagination.items

        if posts:
            post_ids = [p.post_id for p in posts]
            user_id = session.get("user_id")

            reaction_counts = db.session.query(
                Reaction.post_id,
                Reaction.reaction_type,
                func.count(Reaction.reaction_id)
            ).filter(Reaction.post_id.in_(post_ids)).group_by(
                Reaction.post_id,
                Reaction.reaction_type
            ).all()

            reactions_by_post = defaultdict(dict)
            for post_id, emoji, count in reaction_counts:
                reactions_by_post[post_id][emoji] = count

            user_reactions_query = db.session.query(
                Reaction.post_id,
                Reaction.reaction_type
            ).filter(
                Reaction.post_id.in_(post_ids),
                Reaction.user_id == user_id
            ).all()

            user_reactions_set = set(user_reactions_query)

            for post in posts:
                post.reaction_counts = reactions_by_post.get(post.post_id, {})
                post.user_reacted_emojis = {emoji for pid, emoji in user_reactions_set if pid == post.post_id}

        school_info = School.query.filter_by(school_id=user_school_id).first()
        board_title = f"{school_info.school_name} 掲示板" if school_info else "校舎別掲示板"

        return render_template("home.html",
                               user=session["name"],
                               posts=posts,
                               pagination=posts_pagination,
                               board_title=board_title,
                               current_scope=school_scope)
    return redirect(url_for("login"))

@app.route("/home/following")
@check_restriction # ◀️ デコレータを追加
def following_board():
    if "user_id" not in session:
        return redirect(url_for("login"))

    page = request.args.get('page', 1, type=int)
    current_user = User.query.get(session["user_id"])

    followed_users_ids = [user.user_id for user in current_user.followed]

    # 🔽🔽🔽 N+1問題対策: 著者、タグ、コメント(＋著者)、コメントのタグ を一括読み込み 🔽🔽🔽
    posts_pagination = Post.query.options(
        joinedload(Post.author),
        subqueryload(Post.tags), 
        subqueryload(Post.comments).joinedload(Comment.user),
        subqueryload(Post.comments).subqueryload(Comment.tags)
    ).filter(Post.user_id.in_(followed_users_ids)).order_by(Post.created_at.desc()).paginate(
    # ▲▲▲ 変更完了 ▲▲▲
        page=page, per_page=POSTS_PER_PAGE, error_out=False
    )
    posts = posts_pagination.items

    if posts:
        post_ids = [p.post_id for p in posts]
        user_id = session.get("user_id")

        reaction_counts = db.session.query(
            Reaction.post_id,
            Reaction.reaction_type,
            func.count(Reaction.reaction_id)
        ).filter(Reaction.post_id.in_(post_ids)).group_by(
            Reaction.post_id,
            Reaction.reaction_type
        ).all()

        reactions_by_post = defaultdict(dict)
        for post_id, emoji, count in reaction_counts:
            reactions_by_post[post_id][emoji] = count

        user_reactions_query = db.session.query(
            Reaction.post_id,
            Reaction.reaction_type
        ).filter(
            Reaction.post_id.in_(post_ids),
            Reaction.user_id == user_id
        ).all()

        user_reactions_set = set(user_reactions_query)

        for post in posts:
            post.reaction_counts = reactions_by_post.get(post.post_id, {})
            post.user_reacted_emojis = {emoji for pid, emoji in user_reactions_set if pid == post.post_id}

    return render_template("home.html",
                           user=session["name"],
                           posts=posts,
                           pagination=posts_pagination,
                           board_title="フォロー中のユーザーの投稿",
                           current_scope="following")


# ====== 🔽 変更: 通知用掲示板のルート 🔽 ======
@app.route("/home/notice_board")
def notice_board():
    if "role" not in session or session["role"] != "student":
        return redirect(url_for("login"))

    # セッションからモーダル表示フラグを取得し、テンプレートに渡す
    show_modal = session.pop('show_restriction_modal', False)

    page = request.args.get('page', 1, type=int)

    user_school_id = session.get("school_id")
    notice_scopes = []

    if user_school_id is not None:
        notice_scopes.append(f'notice{user_school_id}')

    if user_school_id == 0:
        notice_scopes.append('notice0')

    # 🔽🔽🔽 N+1問題対策: 著者、タグ、コメント(＋著者)、コメントのタグ を一括読み込み 🔽🔽🔽
    posts_pagination = Post.query.options(
        joinedload(Post.author),
        subqueryload(Post.tags), 
        subqueryload(Post.comments).joinedload(Comment.user),
        subqueryload(Post.comments).subqueryload(Comment.tags)
    ).filter(Post.scope.in_(notice_scopes)).order_by(Post.created_at.desc()).paginate(
    # ▲▲▲ 変更完了 ▲▲▲
        page=page, per_page=POSTS_PER_PAGE, error_out=False
    )
    posts = posts_pagination.items

    if posts:
        post_ids = [p.post_id for p in posts]
        user_id = session.get("user_id")

        reaction_counts = db.session.query(
            Reaction.post_id,
            Reaction.reaction_type,
            func.count(Reaction.reaction_id)
        ).filter(Reaction.post_id.in_(post_ids)).group_by(
            Reaction.post_id,
            Reaction.reaction_type
        ).all()

        reactions_by_post = defaultdict(dict)
        for post_id, emoji, count in reaction_counts:
            reactions_by_post[post_id][emoji] = count

        user_reactions_query = db.session.query(
            Reaction.post_id,
            Reaction.reaction_type
        ).filter(
            Reaction.post_id.in_(post_ids),
            Reaction.user_id == user_id
        ).all()

        user_reactions_set = set(user_reactions_query)

        for post in posts:
            post.reaction_counts = reactions_by_post.get(post.post_id, {})
            post.user_reacted_emojis = {emoji for pid, emoji in user_reactions_set if pid == post.post_id}

    return render_template("home.html",
                           user=session["name"],
                           posts=posts,
                           pagination=posts_pagination,
                           board_title="通知用掲示板",
                           current_scope="notice0",
                           # テンプレートにフラグ変数を渡す
                           show_restriction_modal=show_modal)
# ====== 🔼 変更完了 🔼 ======

@app.route("/post", methods=["POST"])
@check_restriction # ◀️ デコレータを追加
def submit_post():
    if "user_id" not in session or session["role"] != "student":
        return redirect(url_for("login"))

    content = request.form.get("content")
    scope = request.form.get("scope")

    if not content or not scope:
        flash("投稿内容が不正です。", "error")
        return redirect(url_for("home"))

    # 🔽🔽🔽 投稿内容からタグを抽出 🔽🔽🔽
    tags = extract_and_get_tags(content)
    # ▲▲▲ 処理追加 ▲▲▲

    new_post = Post(
        user_id=session["user_id"],
        content=content,
        scope=scope
    )
    
    # 🔽🔽🔽 投稿にタグを関連付け 🔽🔽🔽
    new_post.tags = tags
    # ▲▲▲ 処理追加 ▲▲▲
    
    db.session.add(new_post)
    db.session.commit()

    if scope == "public":
        return redirect(url_for("school_wide_board"))
    elif scope.startswith("school"):
        return redirect(url_for("school_specific_board"))
    else:
        return redirect(url_for("home"))

@app.route("/post/delete/<int:post_id>", methods=["POST"])
def delete_post(post_id):
    if "user_id" not in session:
        return jsonify({"success": False, "message": "ログインが必要です"}), 401

    post = Post.query.get(post_id)

    if not post:
        return jsonify({"success": False, "message": "投稿が見つかりませんでした"}), 404

    if post.user_id != session["user_id"] and session["role"] != "admin":
        return jsonify({"success": False, "message": "削除権限がありません"}), 403

    # ◀️ 関連する通報も削除
    Report.query.filter_by(post_id=post.post_id).delete()
    Comment.query.filter_by(post_id=post.post_id).delete()
    db.session.delete(post)
    db.session.commit()

    return jsonify({"success": True, "message": "投稿を削除しました"})

@app.route("/comment/<int:post_id>", methods=["POST"])
@check_restriction # ◀️ デコレータを追加
def add_comment(post_id):
    if "user_id" not in session:
        return jsonify({"success": False, "message": "ログインが必要です"}), 401

    content = request.form.get("comment_content")
    if not content:
        return jsonify({"success": False, "message": "コメント内容を入力してください"}), 400
    
    # 🔽🔽🔽 コメント内容からタグを抽出 🔽🔽🔽
    tags = extract_and_get_tags(content)
    # ▲▲▲ 処理追加 ▲▲▲

    post = Post.query.get(post_id)
    if not post:
        return jsonify({"success": False, "message": "投稿が見つかりません"}), 404

    comment = Comment(
        post_id=post_id,
        user_id=session["user_id"],
        content=content
    )
    
    # 🔽🔽🔽 コメントにタグを関連付け 🔽🔽🔽
    comment.tags = tags
    # ▲▲▲ 処理追加 ▲▲▲
    
    db.session.add(comment)
    db.session.commit()

    user = User.query.get(session["user_id"])

    return jsonify({
        "success": True,
        "message": "コメントを追加しました",
        "comment": {
            "comment_id": comment.comment_id,
            "content": comment.content,
            "user_id": user.user_id,
            "user_name": user.name if user else "不明",
            "created_at": comment.created_at.strftime('%Y/%m/%d %H:%M'),
            # 🔽🔽🔽 抽出したタグをJSONレスポンスに追加 🔽🔽🔽
            "tags": [{"name": tag.name} for tag in comment.tags]
            # ▲▲▲ 処理追加 ▲▲▲
        }
    })

@app.route("/profile", defaults={'user_id': None})
@app.route("/profile/<int:user_id>")
@check_restriction # ◀️ デコレータを追加
def profile_view(user_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    viewed_user_id = user_id if user_id is not None else session["user_id"]
    is_own_profile = (viewed_user_id == session["user_id"])

    user = User.query.get(viewed_user_id)
    if not user:
        flash("ユーザーが見つかりませんでした。", "error")
        return redirect(request.referrer or url_for("home"))

    # ▼▼▼【ここから修正】▼▼▼
    is_following = False
    is_blocking = False
    is_blocked_by = False # 相手からブロックされているかどうかのフラグを追加

    if not is_own_profile:
        current_user = User.query.get(session["user_id"])
        is_following = current_user.followed.filter_by(user_id=user.user_id).first() is not None

        # 自分が相手をブロックしているか
        is_blocking = current_user.blocked_users.filter_by(user_id=user.user_id).first() is not None

        # 相手が自分をブロックしているか
        is_blocked_by = user.blocked_users.filter_by(user_id=current_user.user_id).first() is not None

        # ブロックしている、またはされている場合は専用ページを表示
        if is_blocking or is_blocked_by:
            return render_template("error_blocked.html", user_name=user.name), 403 # テンプレートとステータスコードを返す
    # ▲▲▲【修正完了】▲▲▲

    return render_template("profile.html",
                           user=user,
                           is_own_profile=is_own_profile,
                           is_following=is_following,
                           is_blocking=is_blocking,
                           # is_blocked_by も渡す（今回は使用しないが、将来的な拡張のため）
                           is_blocked_by=is_blocked_by,
                           current_user_id=session["user_id"])


@app.route('/follow/<int:user_id>', methods=['POST'])
@check_restriction # ◀️ デコレータを追加
def follow_user(user_id):
    if "user_id" not in session:
        return jsonify({'success': False, 'message': 'ログインが必要です'}), 401

    user_to_follow = User.query.get(user_id)
    current_user = User.query.get(session['user_id'])

    if not user_to_follow:
        return jsonify({'success': False, 'message': 'ユーザーが見つかりません'}), 404

    if user_to_follow.user_id == current_user.user_id:
        return jsonify({'success': False, 'message': '自分自身をフォローすることはできません'}), 400

    is_following = current_user.followed.filter_by(user_id=user_id).first()

    if is_following:
        current_user.followed.remove(user_to_follow)
        db.session.commit()
        return jsonify({
            'success': True,
            'action': 'unfollowed',
            'message': f'{user_to_follow.name}さんのフォローを解除しました',
            'followers_count': user_to_follow.followers.count(),
            'following_count': current_user.followed.count()
        })
    else:
        current_user.followed.append(user_to_follow)
        db.session.commit()

        follower_info = {
            'user_id': current_user.user_id,
            'name': current_user.name,
            'icon_path': current_user.icon_path if current_user.icon_path and current_user.icon_path.startswith('http') else None
        }

        return jsonify({
            'success': True,
            'action': 'followed',
            'message': f'{user_to_follow.name}さんをフォローしました',
            'followers_count': user_to_follow.followers.count(),
            'following_count': current_user.followed.count(),
            'follower_info': follower_info
        })

# ====== 🔽 ここからがブロック機能のコードです。この位置に配置してください。 🔽 ======
@app.route('/block/<int:user_id>', methods=['POST'])
@check_restriction
def block_user(user_id):
    if "user_id" not in session:
        return jsonify({'success': False, 'message': 'ログインが必要です'}), 401

    user_to_block = User.query.get(user_id)
    current_user = User.query.get(session['user_id'])

    if not user_to_block:
        return jsonify({'success': False, 'message': 'ユーザーが見つかりません'}), 404

    if user_to_block.user_id == current_user.user_id:
        return jsonify({'success': False, 'message': '自分自身をブロックすることはできません'}), 400

    is_blocking = current_user.blocked_users.filter_by(user_id=user_id).first()

    if is_blocking:
        # ブロック解除
        current_user.blocked_users.remove(user_to_block)
        db.session.commit()
        return jsonify({
            'success': True,
            'action': 'unblocked',
            'message': f'{user_to_block.name}さんのブロックを解除しました',
        })
    else:
        # ブロック実行
        current_user.blocked_users.append(user_to_block)

        # フォロー関係を双方向で解除
        if current_user.followed.filter_by(user_id=user_id).first():
            current_user.followed.remove(user_to_block)
        if user_to_block.followed.filter_by(user_id=current_user.user_id).first():
            user_to_block.followed.remove(current_user)

        db.session.commit()
        return jsonify({
            'success': True,
            'action': 'blocked',
            'message': f'{user_to_block.name}さんをブロックしました',
        })
# ====== 🔼 ブロック機能のコードはここまでです 🔼 ======

# def allowed_file(filename):
#     return '.' in filename and \
#            filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route("/profile/edit", methods=["GET", "POST"])
@check_restriction
def edit_profile():
    if "user_id" not in session:
        return redirect(url_for("login"))

    user = User.query.get(session["user_id"])

    import boto3
    s3 = boto3.client('s3')

    if request.method == "POST":
        user.introduction = request.form.get("introduction")
        user.tags = request.form.get("tags")

        # ▼▼▼ アイコンの処理 (S3対応) ▼▼▼
        if 'icon' in request.files:
            icon_file = request.files['icon']
            if icon_file.filename != '' and allowed_file(icon_file.filename):
                # ファイル名をセキュアにし、一意性を持たせる
                filename = secure_filename(f"icon_{user.user_id}_{icon_file.filename}")

                try:
                    # S3にアップロード
                    s3.upload_fileobj(
                        icon_file,
                        S3_BUCKET_NAME,
                        filename
                    )
                    user.icon_path = f"https://{S3_BUCKET_NAME}.s3.amazonaws.com/{filename}"
                
                except Exception as e:
                    # ▼▼▼ 呢句係新加嘅 ▼▼▼
                    print(f"!!! ICON UPLOAD ERROR: {e}") 
                    # ▲▲▲ 呢句係新加嘅 ▲▲▲
                    flash(f"アイコンのアップロードに失敗しました: {e}", "error")
                    return redirect(url_for("edit_profile"))

        # ▼▼▼ ヘッダーの処理 (S3対応) ▼▼▼
        if 'header' in request.files:
            header_file = request.files['header']
            if header_file.filename != '' and allowed_file(header_file.filename):
                filename = secure_filename(f"header_{user.user_id}_{header_file.filename}")

                try:
                    # S3にアップロード
                    s3.upload_fileobj(
                        header_file,
                        S3_BUCKET_NAME,
                        filename
                    )
                    # S3のURLをデータベースに保存
                    user.header_path = f"https://{S3_BUCKET_NAME}.s3.amazonaws.com/{filename}"

                except Exception as e:
                    flash(f"ヘッダーのアップロードに失敗しました: {e}", "error")
                    return redirect(url_for("edit_profile"))

        # すべての処理が成功したらコミット
        db.session.commit()
        flash("プロフィールを更新しました。", "success")
        return redirect(url_for("profile_view"))

    # GETリクエストの場合
    return render_template("edit_profile.html", user=user)

# @app.route('/uploads/<filename>')
# def uploaded_file(filename):
#     return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


@app.route("/settings")
def settings():
    if "user_id" not in session:
        return redirect(url_for("login"))

    return render_template("settings.html")

@app.route("/settings/change_password", methods=["GET", "POST"])
def change_password():
    if "user_id" not in session:
        return redirect(url_for("login"))

    user = User.query.get(session["user_id"])
    if not user:
        return redirect(url_for("logout"))

    if request.method == "POST":
        current_password = request.form.get("current_password")
        new_password = request.form.get("new_password")
        confirm_password = request.form.get("confirm_password")

        if not check_password_hash(user.password_hash, current_password):
            flash("現在のパスワードが正しくありません。", "error")
            return redirect(url_for("change_password"))

        if new_password != confirm_password:
            flash("新しいパスワードが一致しません。", "error")
            return redirect(url_for("change_password"))

        user.password_hash = generate_password_hash(new_password)
        db.session.commit()

        flash("パスワードが正常に変更されました。", "success")
        return redirect(url_for("settings"))

    return render_template("change_password.html")

@app.route("/settings/block_list")
@check_restriction
def block_list():
    if "user_id" not in session:
        return redirect(url_for("login"))

    user = User.query.get(session["user_id"])
    blocked_users = user.blocked_users.all()

    return render_template("block_list.html", blocked_users=blocked_users)

@app.route("/my_posts")
@check_restriction # ◀️ デコレータを追加
def my_posts():
    if "user_id" not in session:
        return redirect(url_for("login"))

    page = request.args.get('page', 1, type=int)

    # 🔽🔽🔽 N+1問題対策: 著者、タグ、コメント(＋著者)、コメントのタグ を一括読み込み 🔽🔽🔽
    posts_pagination = Post.query.options(
        joinedload(Post.author),
        subqueryload(Post.tags), 
        subqueryload(Post.comments).joinedload(Comment.user),
        subqueryload(Post.comments).subqueryload(Comment.tags)
    ).filter_by(user_id=session["user_id"]).order_by(Post.created_at.desc()).paginate(
    # ▲▲▲ 変更完了 ▲▲▲
        page=page, per_page=POSTS_PER_PAGE, error_out=False
    )
    posts = posts_pagination.items

    if posts:
        post_ids = [p.post_id for p in posts]
        user_id = session.get("user_id")

        reaction_counts = db.session.query(
            Reaction.post_id,
            Reaction.reaction_type,
            func.count(Reaction.reaction_id)
        ).filter(Reaction.post_id.in_(post_ids)).group_by(
            Reaction.post_id,
            Reaction.reaction_type
        ).all()

        reactions_by_post = defaultdict(dict)
        for post_id, emoji, count in reaction_counts:
            reactions_by_post[post_id][emoji] = count

        user_reactions_query = db.session.query(
            Reaction.post_id,
            Reaction.reaction_type
        ).filter(
            Reaction.post_id.in_(post_ids),
            Reaction.user_id == user_id
        ).all()

        user_reactions_set = set(user_reactions_query)

        for post in posts:
            post.reaction_counts = reactions_by_post.get(post.post_id, {})
            post.user_reacted_emojis = {emoji for pid, emoji in user_reactions_set if pid == post.post_id}

    return render_template("home.html",
                           user=session["name"],
                           posts=posts,
                           pagination=posts_pagination,
                           board_title=f"{session['name']}さんの投稿一覧",
                           current_scope="my_posts")

# 🔽🔽🔽 タグ検索用の新しいルートを追加 🔽🔽🔽
@app.route("/tag/<string:tag_name>")
@check_restriction
def search_by_tag(tag_name):
    """
    タグ名で投稿を検索し、home.htmlを再利用して表示する
    """
    if "role" not in session:
        return redirect(url_for("login"))

    page = request.args.get('page', 1, type=int)
    tag = Tag.query.filter_by(name=tag_name).first()

    if not tag:
        # タグが見つからない場合
        return render_template("home.html",
                               user=session["name"],
                               posts=[],
                               pagination=None,
                               board_title=f"#{tag_name} の投稿",
                               current_scope="tag_search", # 検索ページ用のスコープ
                               current_tag_name=tag_name) # ページネーション用
    
    # ブロックしている/されているユーザーを除外
    blocked_ids = get_blocked_user_ids()
    
    # タグに関連する投稿を取得 (N+1対策も)
    posts_query = tag.posts.filter(Post.user_id.notin_(blocked_ids)) \
                    .options(
                        joinedload(Post.author),
                        subqueryload(Post.tags), 
                        subqueryload(Post.comments).joinedload(Comment.user),
                        subqueryload(Post.comments).subqueryload(Comment.tags)
                    )

    posts_pagination = posts_query.order_by(Post.created_at.desc()).paginate(
        page=page, per_page=POSTS_PER_PAGE, error_out=False
    )
    posts = posts_pagination.items

    # --- リアクション処理 (homeのルートからコピー) ---
    if posts:
        post_ids = [p.post_id for p in posts]
        user_id = session.get("user_id")

        reaction_counts = db.session.query(
            Reaction.post_id,
            Reaction.reaction_type,
            func.count(Reaction.reaction_id)
        ).filter(Reaction.post_id.in_(post_ids)).group_by(
            Reaction.post_id,
            Reaction.reaction_type
        ).all()

        reactions_by_post = defaultdict(dict)
        for post_id, emoji, count in reaction_counts:
            reactions_by_post[post_id][emoji] = count

        user_reactions_query = db.session.query(
            Reaction.post_id,
            Reaction.reaction_type
        ).filter(
            Reaction.post_id.in_(post_ids),
            Reaction.user_id == user_id
        ).all()

        user_reactions_set = set(user_reactions_query)

        for post in posts:
            post.reaction_counts = reactions_by_post.get(post.post_id, {})
            post.user_reacted_emojis = {emoji for pid, emoji in user_reactions_set if pid == post.post_id}
    # --- リアクション処理ここまで ---

    return render_template("home.html",
                           user=session["name"],
                           posts=posts,
                           pagination=posts_pagination,
                           board_title=f"#{tag_name} の投稿",
                           current_scope="tag_search",
                           current_tag_name=tag_name)
# ▲▲▲ 新規ルート追加完了 ▲▲▲


# ====== 🔽 ここから新規・修正のルートを追加 🔽 ======

# ◀️ 追加: 通報を受け付けるAPI
@app.route("/report", methods=["POST"])
def submit_report():
    if "user_id" not in session:
        return jsonify({"success": False, "message": "ログインが必要です"}), 401

    data = request.get_json()
    reason = data.get("reason")
    post_id = data.get("post_id")
    comment_id = data.get("comment_id")

    if not reason or reason.strip() == "":
        return jsonify({"success": False, "message": "通報理由を入力してください"}), 400

    item = None
    reported_user_id = None
    if post_id:
        item = Post.query.get(post_id)
        if item: reported_user_id = item.user_id
    elif comment_id:
        item = Comment.query.get(comment_id)
        if item: reported_user_id = item.user_id

    if not item:
        return jsonify({"success": False, "message": "通報対象が見つかりませんでした"}), 404

    # 自分自身を通報することはできない
    if reported_user_id == session["user_id"]:
        return jsonify({"success": False, "message": "自分自身の投稿やコメントは通報できません。"}), 400

    report = Report(
        reporter_id=session["user_id"],
        reported_user_id=reported_user_id,
        post_id=post_id,
        comment_id=comment_id,
        reason=reason
    )
    db.session.add(report)
    db.session.commit()

    return jsonify({"success": True, "message": "通報が送信されました。ご協力ありがとうございます。"})

# ◀️ 追加: 管理者向けの通報管理ページ
@app.route("/admin/reports")
def admin_reports():
    if session.get("role") != "admin":
        return redirect(url_for("login"))

    # 未解決の通報を新しい順に取得
    reports = Report.query.filter_by(is_resolved=False).order_by(Report.created_at.desc()).all()
    return render_template("admin_reports.html", reports=reports)

# ◀️ 追加: ユーザーの機能制限を切り替えるAPI
@app.route("/admin/user/toggle_restriction/<int:user_id>", methods=["POST"])
def toggle_user_restriction(user_id):
    if session.get("role") != "admin":
        return redirect(url_for("login"))

    user = User.query.get(user_id)
    if user:
        # 現在の状態を反転 (True -> False, False -> True)
        user.is_restricted = not user.is_restricted
        db.session.commit()
        status = "制限" if user.is_restricted else "解除"
        flash(f"ユーザー '{user.name}' のアカウントを {status} しました。", "success")
    else:
        flash("対象のユーザーが見つかりませんでした。", "error")

    return redirect(request.referrer or url_for('admin_reports'))

# ◀️ 追加: 通報を「解決済み」としてマークするAPI
@app.route("/admin/report/resolve/<int:report_id>", methods=["POST"])
def resolve_report(report_id):
    if session.get("role") != "admin":
        return redirect(url_for("login"))

    report = Report.query.get(report_id)
    if report:
        report.is_resolved = True
        db.session.commit()
        flash(f"通報ID {report.report_id} を解決済みにしました。", "success")
    else:
        flash("対象の通報が見つかりませんでした。", "error")

    return redirect(url_for("admin_reports"))

# ====== 🔼 新規・修正のルート追加完了 🔼 ======

@app.route("/admin")
def admin_dashboard():
    if "role" in session and session["role"] == "admin":
        return render_template("admin_dashboard.html", user=session["name"])
    return redirect(url_for("login"))


@app.route("/admin/create_notice", methods=["GET", "POST"])
def create_notice():
    if "role" not in session or session["role"] != "admin":
        return redirect(url_for("login"))

    if request.method == "POST":
        content = request.form.get("content")
        notice_scope = request.form.get("notice_scope")

        if not content or not notice_scope:
            flash("投稿内容または通知先が不正です。", "error")
            return redirect(url_for("create_notice"))

        new_post = Post(
            user_id=session["user_id"],
            content=content,
            scope=notice_scope
        )
        db.session.add(new_post)
        db.session.commit()

        return redirect(url_for("admin_post_management"))

    schools = School.query.all()
    return render_template("create_notice.html", schools=schools)


@app.route("/admin/post_management", methods=["GET"])
def admin_post_management():
    if "role" not in session or session["role"] != "admin":
        return redirect(url_for("login"))

    scope_filter = request.args.get('scope')
    user_name_filter = request.args.get('user_name')
    page = request.args.get('page', 1, type=int)

    query = Post.query

    if scope_filter:
        query = query.filter_by(scope=scope_filter)

    if user_name_filter:
        query = query.join(Post.author).filter(User.name.like(f"%{user_name_filter}%"))

    posts_pagination = query.order_by(Post.created_at.desc()).paginate(
        page=page, per_page=10, error_out=False
    )

    schools = School.query.all()

    return render_template("admin_post_management.html",
                           posts=posts_pagination.items,
                           pagination=posts_pagination,
                           schools=schools,
                           current_scope=scope_filter,
                           current_user_name=user_name_filter)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/create_account", methods=["GET", "POST"])
def create_account():
    if request.method == "POST":
        name = request.form["name"]
        student_id = request.form["student_id"]
        school_id = request.form["school"]
        department_id = request.form["department"]
        password = request.form["password"]
        year = request.form["year"]

        hashed_password = generate_password_hash(password)

        new_user = User(
            name=name,
            student_id=student_id,
            school_id=school_id,
            department_id=department_id,
            password_hash=hashed_password,
            year=year,
            role="student"
        )

        db.session.add(new_user)
        db.session.commit()

        return redirect(url_for("user_management"))


    schools = School.query.all()
    departments = Department.query.all()
    return render_template(
        "Create_Account.html",
        schools=schools,
        departments=departments
    )

@app.route("/user_management/select", methods=["GET", "POST"])
def user_management_select():
    if "role" not in session or session["role"] != "admin":
        return redirect(url_for("login"))


    schools = School.query.all()

    if request.method == "POST":
        school_id = request.form.get("school_id")
        department_id = request.form.get("department_id")
        year = request.form.get("year")

        return redirect(url_for("user_management",
                                 school_id=school_id,
                                 department_id=department_id,
                                 year=year))
    return render_template("user_management_select.html", schools=schools)


# 🔽🔽🔽 ここが変更点です 🔽🔽🔽
@app.route("/user_management")
def user_management():
    if "role" not in session or session["role"] != "admin":
        return redirect(url_for("login"))

    # 絞り込み条件
    school_id = request.args.get("school_id", type=int)
    department_id = request.args.get("department_id", type=int)
    year = request.args.get("year", type=int)

    # 🔽 変更: ソート条件を受け取る
    sort_by = request.args.get("sort_by", "student_id") # デフォルトは学籍番号
    order = request.args.get("order", "asc") # デフォルトは昇順

    # 🔽 変更: Department と join (isouter=Trueで学科未設定でも表示)
    # joinedload(User.department) で N+1 問題を回避
    query = User.query.options(joinedload(User.department)).join(User.department, isouter=True).filter(User.role == "student")

    # --- 既存の絞り込み処理 (変更なし) ---
    school_name = "吉田学園グループ全体"
    if school_id is not None and school_id != -1:
        query = query.filter(User.school_id == school_id)
        school = School.query.get(school_id)
        if school:
            school_name = school.school_name
    if department_id and department_id != -1:
        query = query.filter(User.department_id == department_id)
    if year and year != -1:
        query = query.filter(User.year == year)
    # --- 絞り込み処理ここまで ---

    # 🔽 変更: ソート処理
    if sort_by == "department":
        # 学科名でソート
        sort_column = Department.department_name
    else:
        # デフォルト (student_id)
        sort_column = User.student_id

    # 順序（昇順/降順）の適用
    if order == "desc":
        query = query.order_by(sort_column.desc())
    else:
        query = query.order_by(sort_column.asc())

    users = query.all()

    # 🔽 変更: render_template にソート情報と絞り込み条件を渡す
    return render_template(
        "user_management.html",
        users=users,
        school_name=school_name,
        # 現在のソート状態
        current_sort=sort_by,
        current_order=order,
        # 絞り込み条件 (ソートリンク生成時に必要)
        school_id=school_id,
        department_id=department_id,
        year=year
    )
# 🔼🔼🔼 変更点はここまでです 🔼🔼🔼


@app.route("/user_management/delete/<int:user_id>", methods=["POST"])
def delete_user(user_id):
    if "role" not in session or session["role"] != "admin":
        return redirect(url_for("login"))

    user = User.query.get(user_id)
    if not user:
        return redirect(url_for("user_management"))

    if session.get("user_id") == user.user_id:
        return redirect(url_for("user_management"))

    Post.query.filter_by(user_id=user_id).delete()
    db.session.delete(user)
    db.session.commit()

    return redirect(url_for("user_management"))


@app.route("/user_management/reset_password/<int:user_id>", methods=["POST"])
def reset_password(user_id):
    if "role" not in session or session["role"] != "admin":
        return redirect(url_for("login"))

    user = User.query.get(user_id)
    if not user:
        return redirect(url_for("user_management", msg="ユーザーが見つかりません"))

    temp_password = user.student_id
    user.password_hash = generate_password_hash(temp_password)
    db.session.commit()

    return redirect(url_for("user_management", msg=f"ユーザー {user.student_id} のパスワードをリセットしました（新しいパスワード: {temp_password}）"))


@app.route("/user_management/edit/<int:user_id>", methods=["GET", "POST"])
def edit_user(user_id):
    if "role" not in session or session["role"] != "admin":
        return redirect(url_for("login"))

    user = User.query.get(user_id)
    if not user:
        return redirect(url_for("user_management", msg="ユーザーが見つかりません"))

    if request.method == "POST":
        user.name = request.form.get("name")
        student_id = request.form.get("student_id")
        school_id = request.form.get("school")
        department_id = request.form.get("department") or None
        year = request.form.get("year")

        if student_id and school_id:
            if len(student_id) > 1:
                student_id = str(school_id) + student_id[1:]

        user.student_id = student_id
        user.school_id = int(school_id) if school_id else user.school_id
        user.department_id = int(department_id) if department_id else None
        user.year = int(year) if year else None

        db.session.commit()

        return redirect(url_for("user_management", msg=f"ユーザー {user.student_id} を更新しました"))

    schools = School.query.all()
    departments = Department.query.filter_by(school_id=user.school_id).all()
    return render_template("edit_user.html", user=user, schools=schools, departments=departments)

@app.route("/api/departments")
def api_departments():
    school_id = request.args.get("school_id", type=int)
    departments = Department.query.filter_by(school_id=school_id).all()
    return [{"department_id": d.department_id, "department_name": d.department_name} for d in departments]

@app.route("/qa")
@check_restriction # ◀️ デコレータを追加
def qa_page():
    if "user_id" not in session:
        return redirect(url_for("login"))

    page = request.args.get('page', 1, type=int)
    tab = request.args.get('tab', 'unanswered')

    if tab == 'answered':
        qas_pagination = QA.query.filter(QA.answer.isnot(None)).order_by(QA.created_at.desc()).paginate(
            page=page, per_page=POSTS_PER_PAGE, error_out=False
        )
    else:
        qas_pagination = QA.query.filter(QA.answer.is_(None)).order_by(QA.created_at.desc()).paginate(
            page=page, per_page=POSTS_PER_PAGE, error_out=False
        )

    unanswered_count = QA.query.filter(QA.answer.is_(None)).count()
    answered_count = QA.query.filter(QA.answer.isnot(None)).count()

    return render_template("qa.html",
                         qas=qas_pagination.items,
                         pagination=qas_pagination,
                         current_tab=tab,
                         unanswered_count=unanswered_count,
                         answered_count=answered_count)

@socketio.on('ask_question')
def handle_question(data):
    if 'user_id' not in session:
        return

    question = data.get('question')
    if not question:
        return

    new_qa = QA(
        user_id=session['user_id'],
        question=question
    )
    db.session.add(new_qa)
    db.session.commit()

    unanswered_count = QA.query.filter(QA.answer.is_(None)).count()
    answered_count = QA.query.filter(QA.answer.isnot(None)).count()

    emit('new_question', {
        'qa_id': new_qa.qa_id,
        'user': session['name'],
        'question': question,
        'created_at': new_qa.created_at.strftime('%Y-%m-%d %H:%M:%S'),
        'is_admin': session.get('role') == 'admin',
        'is_own_question': True,
        'unanswered_count': unanswered_count,
        'answered_count': answered_count
    }, broadcast=True)

@socketio.on('post_answer')
def handle_answer(data):
    if 'role' not in session or session['role'] != 'admin':
        return

    qa_id = data.get('qa_id')
    answer = data.get('answer')

    qa = QA.query.get(qa_id)
    if qa and answer:
        qa.answer = answer
        qa.answered_at = datetime.now()
        db.session.commit()

        unanswered_count = QA.query.filter(QA.answer.is_(None)).count()
        answered_count = QA.query.filter(QA.answer.isnot(None)).count()

        emit('new_answer', {
            'qa_id': qa_id,
            'answer': answer,
            'answered_at': qa.answered_at.strftime('%Y-%m-%d %H:%M:%S'),
            'user': qa.user.name,
            'question': qa.question,
            'created_at': qa.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'is_admin': True,
            'is_own_question': False,
            'unanswered_count': unanswered_count,
            'answered_count': answered_count
        }, broadcast=True)

@socketio.on('update_answer')
def handle_update_answer(data):
    if 'role' not in session or session['role'] != 'admin':
        return

    qa_id = data.get('qa_id')
    answer = data.get('answer')

    qa = QA.query.get(qa_id)
    if qa and answer:
        qa.answer = answer
        qa.answered_at = datetime.now()
        db.session.commit()

        emit('answer_updated', {
            'qa_id': qa_id,
            'answer': answer,
            'answered_at': qa.answered_at.strftime('%Y-%m-%d %H:%M:%S')
        }, broadcast=True)


@app.route("/admin/comment/delete/<int:comment_id>", methods=["POST"])
def delete_comment(comment_id):
    if "role" not in session or session["role"] != "admin":
        return jsonify({"success": False, "message": "権限がありません"}), 403

    comment = Comment.query.get(comment_id)
    if not comment:
        return jsonify({"success": False, "message": "コメントが見つかりませんでした"}), 404

    # ◀️ 関連する通報も削除
    Report.query.filter_by(comment_id=comment_id).delete()
    db.session.delete(comment)
    db.session.commit()

    return jsonify({"success": True, "message": "コメントを削除しました"})

@socketio.on('delete_qa')
def handle_delete_qa(data):
    qa_id = data.get('qa_id')
    qa = QA.query.get(qa_id)

    if not qa:
        return

    if session.get('role') != 'admin' and qa.user_id != session.get('user_id'):
        return

    db.session.delete(qa)
    db.session.commit()

    unanswered_count = QA.query.filter(QA.answer.is_(None)).count()
    answered_count = QA.query.filter(QA.answer.isnot(None)).count()

    emit('qa_deleted', {
        'qa_id': qa_id,
        'unanswered_count': unanswered_count,
        'answered_count': answered_count
    }, broadcast=True)

# リアクション関連のAPIエンドポイント
@app.route("/api/reaction/<int:post_id>", methods=["POST"])
def toggle_reaction(post_id):
    if "user_id" not in session:
        return jsonify({"error": "ログインが必要です"}), 401

    data = request.get_json()
    emoji = data.get("emoji")

    if not emoji:
        return jsonify({"error": "無効なリアクションです"}), 400

    user_id = session["user_id"]
    existing_reaction = Reaction.query.filter_by(
        post_id=post_id,
        user_id=user_id,
        reaction_type=emoji
    ).first()

    if existing_reaction:
        db.session.delete(existing_reaction)
        active = False
    else:
        new_reaction = Reaction(
            post_id=post_id,
            user_id=user_id,
            reaction_type=emoji
        )
        db.session.add(new_reaction)
        active = True

    db.session.commit()

    count = Reaction.query.filter_by(post_id=post_id, reaction_type=emoji).count()

    return jsonify({
        "count": count,
        "active": active
    })


@app.route("/api/users/search")
def api_user_search():
    query = request.args.get('q', '')
    if not query:
        return []

    users = User.query.filter(User.name.like(f"%{query}%")).limit(10).all()

    results = [{"id": user.user_id, "name": user.name, "student_id": user.student_id} for user in users]
    return results

@app.route("/comment/delete/<int:comment_id>", methods=["POST"])
def user_delete_comment(comment_id):
    if "user_id" not in session:
        return jsonify({"success": False, "message": "ログインが必要です"}), 401

    comment = Comment.query.get(comment_id)
    if not comment:
        return jsonify({"success": False, "message": "コメントが見つかりませんでした"}), 404

    if comment.user_id != session["user_id"] and session["role"] != "admin":
        return jsonify({"success": False, "message": "削除権限がありません"}), 403

    # ◀️ 関連する通報も削除
    Report.query.filter_by(comment_id=comment.comment_id).delete()
    db.session.delete(comment)
    db.session.commit()

    return jsonify({"success": True, "message": "コメントを削除しました"})

@app.route("/comment/edit/<int:comment_id>", methods=["POST"])
def edit_comment(comment_id):
    if "user_id" not in session:
        return jsonify({"success": False, "message": "ログインが必要です"}), 401

    comment = Comment.query.get(comment_id)
    if not comment:
        return jsonify({"success": False, "message": "コメントが見つかりませんでした"}), 404

    if comment.user_id != session["user_id"] and session["role"] != "admin":
        return jsonify({"success": False, "message": "編集権限がありません"}), 403

    new_content = request.form.get("content")
    if not new_content:
        return jsonify({"success": False, "message": "コメント内容を入力してください"}), 400

    # 🔽🔽🔽 編集時にタグを更新 🔽🔽🔽
    tags = extract_and_get_tags(new_content)
    comment.content = new_content
    comment.tags = tags
    # ▲▲▲ 処理追加 ▲▲▲
    
    db.session.commit()

    return jsonify({
        "success": True, 
        "message": "コメントを更新しました", 
        "content": new_content,
        # 🔽🔽🔽 更新後のタグをJSONレスポンスに追加 🔽🔽🔽
        "tags": [{"name": tag.name} for tag in comment.tags]
        # ▲▲▲ 処理追加 ▲▲▲
    })

@app.route("/post/edit/<int:post_id>", methods=["POST"])
def edit_post(post_id):
    if "user_id" not in session:
        return jsonify({"success": False, "message": "ログインが必要です"}), 401

    post = Post.query.get(post_id)
    if not post:
        return jsonify({"success": False, "message": "投稿が見つかりませんでした"}), 404

    if post.user_id != session["user_id"]:
        return jsonify({"success": False, "message": "編集権限がありません"}), 403

    new_content = request.form.get("content")
    if not new_content:
        return jsonify({"success": False, "message": "投稿内容を入力してください"}), 400

    # 🔽🔽🔽 編集時にタグを更新 🔽🔽🔽
    tags = extract_and_get_tags(new_content)
    post.content = new_content
    post.tags = tags
    # ▲▲▲ 処理追加 ▲▲▲
    
    db.session.commit()

    return jsonify({
        "success": True, 
        "message": "投稿を更新しました", 
        "content": new_content,
        # 🔽🔽🔽 更新後のタグをJSONレスポンスに追加 🔽🔽🔽
        "tags": [{"name": tag.name} for tag in post.tags]
        # ▲▲▲ 処理追加 ▲▲▲
    })

# ！！！！！！注意！！！！！！
# この if __name__ == "__main__": ブロックより上に
# @app.route(...) を定義してください。
if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    socketio.run(app, debug=True)