# -*- coding: utf-8 -*-
"""校园闲置信息墙

定位：一面只负责牵线的信息墙。谁都可以贴停用的闲置信息，谁都可以联系发布者。
     平台内不交易、不收款、不担保；双方同意后，可自行决定是否交换联系方式，
     再约好时间地点在校园里当面交接。

规则：
  1. 未登录：只能浏览首页部分信息，看不到联系方式
  2. 任何登录用户：都可以发布闲置信息、发起联系
  3. 联系需要对方同意后才能开始沟通（避免骚扰）
  4. 联系方式不默认公开：双方各自决定是否把自己的联系方式发给对方，
     也可以全程只用站内沟通
"""
import os
import sqlite3
import uuid
from datetime import datetime, timedelta
from functools import wraps

from flask import (Flask, abort, flash, g, redirect, render_template, request,
                   session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INSTANCE_DIR = os.path.join(BASE_DIR, "instance")
DB_PATH = os.environ.get("FLEA_DB") or os.path.join(INSTANCE_DIR, "campus_flea.db")
UPLOAD_DIR = os.path.join(BASE_DIR, "static", "uploads")
ALLOWED_EXT = {"png", "jpg", "jpeg", "gif", "webp"}

app = Flask(__name__)
app.config.update(
    SECRET_KEY=os.environ.get("FLEA_SECRET", "campus-flea-market-2026-graduation"),
    MAX_CONTENT_LENGTH=8 * 1024 * 1024,
    JSON_AS_ASCII=False,
)

# --------------------------------------------------------------------------
# 常量配置
# --------------------------------------------------------------------------
GRADES = ["大一", "大二", "大三", "大四", "研究生", "已毕业"]

CATEGORIES = [
    {"key": "books", "name": "教材书籍", "icon": "📚"},
    {"key": "digital", "name": "电子数码", "icon": "💻"},
    {"key": "life", "name": "生活用品", "icon": "🧺"},
    {"key": "dorm", "name": "宿舍家具", "icon": "🪑"},
    {"key": "sports", "name": "运动健身", "icon": "🏀"},
    {"key": "beauty", "name": "美妆个护", "icon": "🧴"},
    {"key": "clothes", "name": "衣物鞋包", "icon": "👕"},
    {"key": "other", "name": "其他闲置", "icon": "🎁"},
]
CAT_MAP = {c["key"]: c for c in CATEGORIES}
CONDITIONS = ["全新未拆", "几乎全新", "九成新", "八成新", "有使用痕迹"]

STATUS_TEXT = {
    "open": "信息有效",
    "closed": "已出",
    "off": "已下架",
}
INQUIRY_TEXT = {
    "pending": "待同意",
    "chatting": "沟通中",
    "agreed": "已约好",
    "declined": "已婉拒",
    "closed": "已结束",
}
INQUIRY_ACTIVE = ("pending", "chatting", "agreed")

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    nickname      TEXT NOT NULL,
    grade         TEXT NOT NULL,
    campus        TEXT,
    contact       TEXT,
    created_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS items (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    seller_id     INTEGER NOT NULL REFERENCES users(id),
    title         TEXT NOT NULL,
    description   TEXT,
    price         REAL,
    original_price REAL,
    category      TEXT NOT NULL,
    condition     TEXT NOT NULL,
    location      TEXT,
    image         TEXT,
    status        TEXT NOT NULL DEFAULT 'open',
    views         INTEGER NOT NULL DEFAULT 0,
    created_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS favorites (
    user_id    INTEGER NOT NULL REFERENCES users(id),
    item_id    INTEGER NOT NULL REFERENCES items(id),
    created_at TEXT NOT NULL,
    PRIMARY KEY (user_id, item_id)
);

CREATE TABLE IF NOT EXISTS inquiries (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id           INTEGER NOT NULL REFERENCES items(id),
    buyer_id          INTEGER NOT NULL REFERENCES users(id),
    seller_id         INTEGER NOT NULL REFERENCES users(id),
    status            TEXT NOT NULL DEFAULT 'pending',
    buyer_contact_ok  INTEGER NOT NULL DEFAULT 0,
    seller_contact_ok INTEGER NOT NULL DEFAULT 0,
    created_at        TEXT NOT NULL,
    updated_at        TEXT NOT NULL,
    UNIQUE (item_id, buyer_id)
);

CREATE TABLE IF NOT EXISTS messages (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    inquiry_id INTEGER NOT NULL REFERENCES inquiries(id),
    sender_id  INTEGER NOT NULL REFERENCES users(id),
    content    TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_items_status ON items(status);
CREATE INDEX IF NOT EXISTS idx_items_category ON items(category);
CREATE INDEX IF NOT EXISTS idx_inquiries_item ON inquiries(item_id);
CREATE INDEX IF NOT EXISTS idx_inquiries_buyer ON inquiries(buyer_id);
CREATE INDEX IF NOT EXISTS idx_inquiries_seller ON inquiries(seller_id);
CREATE INDEX IF NOT EXISTS idx_messages_inquiry ON messages(inquiry_id);
"""


# --------------------------------------------------------------------------
# 数据库工具
# --------------------------------------------------------------------------
def get_db():
    if "db" not in g:
        os.makedirs(INSTANCE_DIR, exist_ok=True)
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        g.db = conn
    return g.db


@app.teardown_appcontext
def close_db(exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def login_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not g.user:
            flash("该操作需要登录后才能进行，请先登录 ✨", "warn")
            return redirect(url_for("login", next=request.full_path.rstrip("?")))
        return view(*args, **kwargs)

    return wrapper


# --------------------------------------------------------------------------
# 模板工具
# --------------------------------------------------------------------------
@app.before_request
def load_user():
    g.user = None
    uid = session.get("uid")
    if uid:
        row = get_db().execute("SELECT * FROM users WHERE id = ?", (uid,)).fetchone()
        if row:
            g.user = dict(row)
        else:
            session.pop("uid", None)


@app.context_processor
def inject_globals():
    waiting = 0
    fav_count = 0
    my_posts = 0
    if g.user:
        db = get_db()
        waiting = db.execute(
            "SELECT COUNT(*) FROM inquiries WHERE seller_id = ? AND status = 'pending'",
            (g.user["id"],),
        ).fetchone()[0]
        fav_count = db.execute(
            "SELECT COUNT(*) FROM favorites WHERE user_id = ?", (g.user["id"],)
        ).fetchone()[0]
        my_posts = db.execute(
            "SELECT COUNT(*) FROM items WHERE seller_id = ?", (g.user["id"],)
        ).fetchone()[0]
    return {
        "current_user": g.user,
        "CATEGORIES": CATEGORIES,
        "CAT_MAP": CAT_MAP,
        "CONDITIONS": CONDITIONS,
        "GRADES": GRADES,
        "STATUS_TEXT": STATUS_TEXT,
        "INQUIRY_TEXT": INQUIRY_TEXT,
        "waiting_requests": waiting,
        "fav_count": fav_count,
        "my_posts": my_posts,
    }


@app.template_filter("money")
def money(value):
    try:
        v = float(value)
    except (TypeError, ValueError):
        return "0"
    if abs(v - round(v)) < 0.005:
        return f"{int(round(v)):,}"
    return f"{v:,.2f}"


@app.template_filter("timeago")
def timeago(value):
    if not value:
        return ""
    try:
        dt = datetime.strptime(str(value), "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return str(value)
    delta = (datetime.now() - dt).total_seconds()
    if delta < 60:
        return "刚刚"
    if delta < 3600:
        return f"{int(delta // 60)} 分钟前"
    if delta < 86400:
        return f"{int(delta // 3600)} 小时前"
    if delta < 86400 * 30:
        return f"{int(delta // 86400)} 天前"
    return dt.strftime("%Y-%m-%d")


# --------------------------------------------------------------------------
# 首页 / 浏览
# --------------------------------------------------------------------------
@app.route("/")
def index():
    db = get_db()
    guest = g.user is None
    limit = 6 if guest else 12

    items = db.execute(
        """SELECT i.*, u.nickname AS seller_name, u.grade AS seller_grade
           FROM items i JOIN users u ON u.id = i.seller_id
           WHERE i.status = 'open'
           ORDER BY i.created_at DESC, i.id DESC LIMIT ?""",
        (limit,),
    ).fetchall()

    open_total = db.execute("SELECT COUNT(*) FROM items WHERE status = 'open'").fetchone()[0]
    closed_total = db.execute("SELECT COUNT(*) FROM items WHERE status = 'closed'").fetchone()[0]
    user_total = db.execute("SELECT COUNT(*) FROM users").fetchone()[0]

    return render_template(
        "index.html",
        items=items,
        guest=guest,
        open_total=open_total,
        closed_total=closed_total,
        user_total=user_total,
        hidden_total=max(open_total - limit, 0),
    )


@app.route("/browse")
@login_required
def browse():
    db = get_db()
    q = (request.args.get("q") or "").strip()
    cat = (request.args.get("cat") or "").strip()
    cond = (request.args.get("cond") or "").strip()
    sort = (request.args.get("sort") or "new").strip()
    min_p = request.args.get("min", "").strip()
    max_p = request.args.get("max", "").strip()
    page = max(request.args.get("page", 1, type=int) or 1, 1)
    per_page = 9

    where = ["i.status = 'open'"]
    params = []
    if q:
        where.append("(i.title LIKE ? OR i.description LIKE ? OR i.location LIKE ?)")
        like = f"%{q}%"
        params += [like, like, like]
    if cat in CAT_MAP:
        where.append("i.category = ?")
        params.append(cat)
    if cond in CONDITIONS:
        where.append("i.condition = ?")
        params.append(cond)
    for val, op in ((min_p, ">="), (max_p, "<=")):
        if val:
            try:
                where.append(f"i.price IS NOT NULL AND i.price {op} ?")
                params.append(float(val))
            except ValueError:
                pass

    order_sql = {
        "new": "i.created_at DESC, i.id DESC",
        "price_asc": "i.price IS NULL, i.price ASC",
        "price_desc": "i.price IS NULL, i.price DESC",
        "hot": "i.views DESC, i.id DESC",
    }.get(sort, "i.created_at DESC, i.id DESC")

    where_sql = " WHERE " + " AND ".join(where)
    total = db.execute(f"SELECT COUNT(*) FROM items i{where_sql}", params).fetchone()[0]
    pages = max((total + per_page - 1) // per_page, 1)
    page = min(page, pages)
    offset = (page - 1) * per_page

    items = db.execute(
        f"""SELECT i.*, u.nickname AS seller_name, u.grade AS seller_grade
            FROM items i JOIN users u ON u.id = i.seller_id
            {where_sql} ORDER BY {order_sql} LIMIT ? OFFSET ?""",
        params + [per_page, offset],
    ).fetchall()

    cat_counts = {
        row["category"]: row["c"]
        for row in db.execute(
            "SELECT category, COUNT(*) AS c FROM items WHERE status = 'open' GROUP BY category"
        ).fetchall()
    }

    return render_template(
        "browse.html",
        items=items,
        total=total,
        page=page,
        pages=pages,
        q=q,
        cat=cat,
        cond=cond,
        sort=sort,
        min_p=min_p,
        max_p=max_p,
        cat_counts=cat_counts,
    )


@app.route("/item/<int:item_id>")
def item_detail(item_id):
    db = get_db()
    row = db.execute(
        """SELECT i.*, u.nickname AS seller_name, u.grade AS seller_grade,
                  u.campus AS seller_campus, u.contact AS seller_contact
           FROM items i JOIN users u ON u.id = i.seller_id WHERE i.id = ?""",
        (item_id,),
    ).fetchone()
    if not row:
        abort(404)

    item = dict(row)
    if item["status"] == "open":
        db.execute("UPDATE items SET views = views + 1 WHERE id = ?", (item_id,))
        db.commit()
        item["views"] += 1

    is_owner = bool(g.user) and g.user["id"] == item["seller_id"]
    favorited = False
    inquiry = None
    item_inquiries = []
    if g.user:
        favorited = db.execute(
            "SELECT 1 FROM favorites WHERE user_id = ? AND item_id = ?",
            (g.user["id"], item_id),
        ).fetchone() is not None
        inquiry = db.execute(
            "SELECT * FROM inquiries WHERE item_id = ? AND buyer_id = ?",
            (item_id, g.user["id"]),
        ).fetchone()
        if is_owner:
            item_inquiries = db.execute(
                """SELECT q.*, u.nickname, u.grade,
                          (SELECT COUNT(*) FROM messages m WHERE m.inquiry_id = q.id) AS msg_count
                   FROM inquiries q JOIN users u ON u.id = q.buyer_id
                   WHERE q.item_id = ? ORDER BY q.updated_at DESC""",
                (item_id,),
            ).fetchall()

    related = db.execute(
        """SELECT i.*, u.nickname AS seller_name, u.grade AS seller_grade
           FROM items i JOIN users u ON u.id = i.seller_id
           WHERE i.status = 'open' AND i.category = ? AND i.id != ?
           ORDER BY i.created_at DESC LIMIT 3""",
        (item["category"], item_id),
    ).fetchall()

    return render_template(
        "item.html",
        item=item,
        is_owner=is_owner,
        favorited=favorited,
        inquiry=inquiry,
        item_inquiries=item_inquiries,
        related=related,
    )


# --------------------------------------------------------------------------
# 注册 / 登录
# --------------------------------------------------------------------------
@app.route("/register", methods=["GET", "POST"])
def register():
    if g.user:
        return redirect(url_for("index"))
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        password2 = request.form.get("password2") or ""
        nickname = (request.form.get("nickname") or "").strip()
        grade = (request.form.get("grade") or "").strip()
        campus = (request.form.get("campus") or "").strip()
        contact = (request.form.get("contact") or "").strip()

        errors = []
        if not (3 <= len(username) <= 20):
            errors.append("账号长度需为 3-20 个字符")
        if len(password) < 6:
            errors.append("密码至少 6 位")
        if password != password2:
            errors.append("两次输入的密码不一致")
        if not nickname:
            errors.append("请填写昵称")
        if grade not in GRADES:
            errors.append("请选择所在年级")

        db = get_db()
        if username and db.execute("SELECT 1 FROM users WHERE username = ?", (username,)).fetchone():
            errors.append("该账号已被注册，换一个试试")

        if errors:
            for e in errors:
                flash(e, "err")
            return render_template(
                "register.html",
                form={"username": username, "nickname": nickname,
                      "grade": grade, "campus": campus, "contact": contact},
            )

        cur = db.execute(
            """INSERT INTO users (username, password_hash, nickname, grade, campus, contact, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (username, generate_password_hash(password), nickname, grade, campus, contact, now_str()),
        )
        db.commit()
        session["uid"] = cur.lastrowid
        flash(f"欢迎加入校园闲置信息墙，{nickname}！", "ok")
        return redirect(url_for("index"))

    return render_template("register.html", form={})


@app.route("/login", methods=["GET", "POST"])
def login():
    if g.user:
        return redirect(url_for("index"))
    nxt = request.args.get("next") or request.form.get("next") or ""
    if not nxt.startswith("/") or nxt.startswith("//"):
        nxt = ""

    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        db = get_db()
        row = db.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        if row and check_password_hash(row["password_hash"], password):
            session["uid"] = row["id"]
            flash(f"登录成功，{row['nickname']} 回来啦 👋", "ok")
            return redirect(nxt or url_for("index"))
        flash("账号或密码不正确", "err")
        return render_template("login.html", username=username, nxt=nxt)

    return render_template("login.html", username="", nxt=nxt)


@app.route("/logout")
def logout():
    session.pop("uid", None)
    flash("已退出登录，下次见 👋", "ok")
    return redirect(url_for("index"))


@app.route("/me/contact", methods=["POST"])
@login_required
def update_contact():
    contact = (request.form.get("contact") or "").strip()[:40]
    db = get_db()
    db.execute("UPDATE users SET contact = ? WHERE id = ?", (contact, g.user["id"]))
    db.commit()
    flash("联系方式已更新" if contact else "已清空联系方式，仅使用站内沟通", "ok")
    return redirect(request.form.get("back") or url_for("my"))


# --------------------------------------------------------------------------
# 发布 / 管理闲置信息
# --------------------------------------------------------------------------
def save_upload(file_storage):
    if not file_storage or not file_storage.filename:
        return None
    ext = file_storage.filename.rsplit(".", 1)[-1].lower() if "." in file_storage.filename else ""
    if ext not in ALLOWED_EXT:
        return None
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    name = f"{uuid.uuid4().hex}.{ext}"
    file_storage.save(os.path.join(UPLOAD_DIR, name))
    return f"uploads/{name}"


@app.route("/publish", methods=["GET", "POST"])
@login_required
def publish():
    if request.method == "POST":
        db = get_db()
        title = (request.form.get("title") or "").strip()
        description = (request.form.get("description") or "").strip()
        category = (request.form.get("category") or "").strip()
        condition = (request.form.get("condition") or "").strip()
        location = (request.form.get("location") or "").strip()
        price_raw = (request.form.get("price") or "").strip()
        original_raw = (request.form.get("original_price") or "").strip()

        errors = []
        if not (2 <= len(title) <= 40):
            errors.append("标题需要 2-40 个字")
        if category not in CAT_MAP:
            errors.append("请选择物品分类")
        if condition not in CONDITIONS:
            errors.append("请选择成色")
        price = None
        if price_raw:
            try:
                price = float(price_raw)
                if price <= 0 or price > 999999:
                    raise ValueError
            except ValueError:
                errors.append("心理价位填写不正确（不填表示面议）")
                price = None
        original_price = None
        if original_raw:
            try:
                original_price = float(original_raw)
            except ValueError:
                errors.append("原价填写不正确")
        if len(description) < 5:
            errors.append("描述至少写 5 个字，方便同学了解物品")

        image_path = save_upload(request.files.get("image"))
        image_url = (request.form.get("image_url") or "").strip()
        if not image_path and image_url:
            image_path = image_url

        if errors:
            for e in errors:
                flash(e, "err")
            return render_template("publish.html", form=request.form)

        db.execute(
            """INSERT INTO items (seller_id, title, description, price, original_price,
                                  category, condition, location, image, status, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'open', ?)""",
            (g.user["id"], title, description, price, original_price, category,
             condition, location, image_path, now_str()),
        )
        db.commit()
        flash("信息已发布！同学们可以在墙上看到它了 🎉", "ok")
        return redirect(url_for("my", tab="posts"))

    return render_template("publish.html", form={})


@app.route("/item/<int:item_id>/status", methods=["POST"])
@login_required
def change_item_status(item_id):
    db = get_db()
    row = db.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()
    if not row:
        abort(404)
    if row["seller_id"] != g.user["id"]:
        abort(403)
    action = request.form.get("action")
    ts = now_str()
    if action == "off" and row["status"] == "open":
        db.execute("UPDATE items SET status = 'off' WHERE id = ?", (item_id,))
        db.commit()
        flash("已下架这条信息", "ok")
    elif action == "on" and row["status"] in ("off", "closed"):
        db.execute("UPDATE items SET status = 'open' WHERE id = ?", (item_id,))
        db.execute(
            "UPDATE inquiries SET status = 'chatting', updated_at = ? WHERE item_id = ? AND status = 'closed'",
            (ts, item_id),
        )
        db.commit()
        flash("信息已重新上墙", "ok")
    elif action == "closed" and row["status"] in ("open", "off"):
        db.execute("UPDATE items SET status = 'closed' WHERE id = ?", (item_id,))
        db.execute(
            "UPDATE inquiries SET status = 'closed', updated_at = ? WHERE item_id = ? AND status != 'closed'",
            (ts, item_id),
        )
        db.commit()
        flash("已标记为「已出」，其他同学不会再看到这条信息", "ok")
    elif action == "delete":
        db.execute(
            "DELETE FROM messages WHERE inquiry_id IN (SELECT id FROM inquiries WHERE item_id = ?)",
            (item_id,),
        )
        db.execute("DELETE FROM inquiries WHERE item_id = ?", (item_id,))
        db.execute("DELETE FROM favorites WHERE item_id = ?", (item_id,))
        db.execute("DELETE FROM items WHERE id = ?", (item_id,))
        db.commit()
        flash("已删除这条信息", "ok")
    else:
        flash("当前状态下无法执行该操作", "warn")
    return redirect(request.form.get("back") or url_for("my", tab="posts"))


# --------------------------------------------------------------------------
# 联系 / 站内沟通
# --------------------------------------------------------------------------
@app.route("/item/<int:item_id>/contact", methods=["POST"])
@login_required
def contact(item_id):
    db = get_db()
    item = db.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()
    if not item:
        abort(404)

    if item["seller_id"] == g.user["id"]:
        flash("这是你自己发布的信息哦", "warn")
        return redirect(url_for("item_detail", item_id=item_id))

    existing = db.execute(
        "SELECT * FROM inquiries WHERE item_id = ? AND buyer_id = ?",
        (item_id, g.user["id"]),
    ).fetchone()
    if existing:
        flash("你已经联系过发布者，去看看进展吧", "ok")
        return redirect(url_for("chat", inquiry_id=existing["id"]))

    if item["status"] != "open":
        flash("这条信息已经不能联系了，看看别的吧", "warn")
        return redirect(url_for("item_detail", item_id=item_id))

    ts = now_str()
    content = (request.form.get("message") or "").strip()[:500]
    cur = db.execute(
        """INSERT INTO inquiries (item_id, buyer_id, seller_id, status, created_at, updated_at)
           VALUES (?, ?, ?, 'pending', ?, ?)""",
        (item_id, g.user["id"], item["seller_id"], ts, ts),
    )
    inquiry_id = cur.lastrowid
    if not content:
        content = f"你好，我对「{item['title']}」感兴趣，想和你联系一下～"
    db.execute(
        "INSERT INTO messages (inquiry_id, sender_id, content, created_at) VALUES (?, ?, ?, ?)",
        (inquiry_id, g.user["id"], content, ts),
    )
    db.commit()
    flash("联系申请已发送，等对方同意后就能开始聊天了 📮", "ok")
    return redirect(url_for("chat", inquiry_id=inquiry_id))


@app.route("/chat/<int:inquiry_id>")
@login_required
def chat(inquiry_id):
    db = get_db()
    row = db.execute(
        """SELECT q.*, i.title, i.price, i.image, i.category, i.condition,
                  i.location, i.status AS item_status, i.id AS item_id
           FROM inquiries q JOIN items i ON i.id = q.item_id
           WHERE q.id = ?""",
        (inquiry_id,),
    ).fetchone()
    if not row:
        abort(404)

    item = dict(row)
    is_buyer = row["buyer_id"] == g.user["id"]
    is_seller = row["seller_id"] == g.user["id"]
    if not (is_buyer or is_seller):
        abort(403)

    other_id = row["seller_id"] if is_buyer else row["buyer_id"]
    other = db.execute("SELECT * FROM users WHERE id = ?", (other_id,)).fetchone()
    me = db.execute("SELECT * FROM users WHERE id = ?", (g.user["id"],)).fetchone()

    messages = db.execute(
        """SELECT m.*, u.nickname, u.id AS uid FROM messages m
           JOIN users u ON u.id = m.sender_id
           WHERE m.inquiry_id = ? ORDER BY m.id ASC""",
        (inquiry_id,),
    ).fetchall()

    my_contact_ok = (row["buyer_contact_ok"] if is_buyer else row["seller_contact_ok"]) == 1
    other_contact_ok = (row["seller_contact_ok"] if is_buyer else row["buyer_contact_ok"]) == 1

    other_inquiries = []
    if is_seller:
        other_inquiries = db.execute(
            """SELECT q.*, u.nickname FROM inquiries q JOIN users u ON u.id = q.buyer_id
               WHERE q.item_id = ? AND q.id != ? ORDER BY q.updated_at DESC""",
            (row["item_id"], inquiry_id),
        ).fetchall()

    return render_template(
        "chat.html",
        item=item,
        inquiry=row,
        other=other,
        me=me,
        messages=messages,
        is_buyer=is_buyer,
        is_seller=is_seller,
        my_contact_ok=my_contact_ok,
        other_contact_ok=other_contact_ok,
        other_inquiries=other_inquiries,
    )


@app.route("/chat/<int:inquiry_id>/send", methods=["POST"])
@login_required
def chat_send(inquiry_id):
    db = get_db()
    row = db.execute("SELECT * FROM inquiries WHERE id = ?", (inquiry_id,)).fetchone()
    if not row:
        abort(404)
    if g.user["id"] not in (row["buyer_id"], row["seller_id"]):
        abort(403)
    if row["status"] not in ("chatting", "agreed"):
        flash("对方同意联系后才能发送消息", "warn")
        return redirect(url_for("chat", inquiry_id=inquiry_id))

    content = (request.form.get("content") or "").strip()
    if not content:
        flash("消息不能为空", "warn")
        return redirect(url_for("chat", inquiry_id=inquiry_id))

    ts = now_str()
    db.execute(
        "INSERT INTO messages (inquiry_id, sender_id, content, created_at) VALUES (?, ?, ?, ?)",
        (inquiry_id, g.user["id"], content[:1000], ts),
    )
    db.execute("UPDATE inquiries SET updated_at = ? WHERE id = ?", (ts, inquiry_id))
    db.commit()
    return redirect(url_for("chat", inquiry_id=inquiry_id) + "#bottom")


@app.route("/inquiry/<int:inquiry_id>/<action>", methods=["POST"])
@login_required
def inquiry_action(inquiry_id, action):
    db = get_db()
    row = db.execute("SELECT * FROM inquiries WHERE id = ?", (inquiry_id,)).fetchone()
    if not row:
        abort(404)
    is_buyer = row["buyer_id"] == g.user["id"]
    is_seller = row["seller_id"] == g.user["id"]
    if not (is_buyer or is_seller):
        abort(403)

    ts = now_str()
    if action == "accept":
        if not is_seller or row["status"] != "pending":
            abort(403)
        db.execute("UPDATE inquiries SET status = 'chatting', updated_at = ? WHERE id = ?", (ts, inquiry_id))
        db.commit()
        flash("已同意联系，现在可以开始聊天了 💬", "ok")
    elif action == "decline":
        if not is_seller or row["status"] != "pending":
            abort(403)
        db.execute("UPDATE inquiries SET status = 'declined', updated_at = ? WHERE id = ?", (ts, inquiry_id))
        db.commit()
        flash("已婉拒这次联系", "ok")
    elif action == "agree" and row["status"] == "chatting":
        db.execute("UPDATE inquiries SET status = 'agreed', updated_at = ? WHERE id = ?", (ts, inquiry_id))
        db.commit()
        flash("已标记为「已约好」，记得按时当面交接 📍", "ok")
    elif action == "close" and row["status"] in INQUIRY_ACTIVE:
        db.execute("UPDATE inquiries SET status = 'closed', updated_at = ? WHERE id = ?", (ts, inquiry_id))
        db.commit()
        flash("已结束这次联系", "ok")
    elif action == "reopen" and row["status"] in ("closed", "declined"):
        db.execute("UPDATE inquiries SET status = 'chatting', updated_at = ? WHERE id = ?", (ts, inquiry_id))
        db.commit()
        flash("已重新开启沟通", "ok")
    elif action == "share-contact":
        if row["status"] not in ("chatting", "agreed"):
            flash("对方同意联系后，才可以交换联系方式", "warn")
        else:
            field = "buyer_contact_ok" if is_buyer else "seller_contact_ok"
            new_val = 0 if row[field] else 1
            db.execute(f"UPDATE inquiries SET {field} = ?, updated_at = ? WHERE id = ?", (new_val, ts, inquiry_id))
            db.commit()
            flash("已把你的联系方式发给对方 ✅" if new_val else "已撤回联系方式", "ok")
    else:
        flash("当前状态下无法执行该操作", "warn")
    return redirect(request.form.get("back") or url_for("chat", inquiry_id=inquiry_id))


@app.route("/item/<int:item_id>/favorite", methods=["POST"])
@login_required
def favorite(item_id):
    db = get_db()
    item = db.execute("SELECT id FROM items WHERE id = ?", (item_id,)).fetchone()
    if not item:
        abort(404)
    exists = db.execute(
        "SELECT 1 FROM favorites WHERE user_id = ? AND item_id = ?",
        (g.user["id"], item_id),
    ).fetchone()
    if exists:
        db.execute(
            "DELETE FROM favorites WHERE user_id = ? AND item_id = ?", (g.user["id"], item_id)
        )
        flash("已取消收藏", "ok")
    else:
        db.execute(
            "INSERT INTO favorites (user_id, item_id, created_at) VALUES (?, ?, ?)",
            (g.user["id"], item_id, now_str()),
        )
        flash("已收藏，方便下次找到它 ❤️", "ok")
    db.commit()
    return redirect(request.form.get("back") or url_for("item_detail", item_id=item_id))


# --------------------------------------------------------------------------
# 个人中心
# --------------------------------------------------------------------------
@app.route("/my")
@login_required
def my():
    db = get_db()
    uid = g.user["id"]
    post_total = db.execute("SELECT COUNT(*) FROM items WHERE seller_id = ?", (uid,)).fetchone()[0]
    default_tab = "posts" if post_total else "inquiries"
    tab = request.args.get("tab", default_tab)

    posts = db.execute(
        """SELECT i.*,
                  (SELECT COUNT(*) FROM inquiries q WHERE q.item_id = i.id) AS inquiry_count,
                  (SELECT COUNT(*) FROM inquiries q WHERE q.item_id = i.id AND q.status = 'pending') AS pending_count,
                  (SELECT COUNT(*) FROM inquiries q WHERE q.item_id = i.id AND q.status = 'chatting') AS chatting_count
           FROM items i WHERE i.seller_id = ? ORDER BY i.created_at DESC, i.id DESC""",
        (uid,),
    ).fetchall()

    inbox = db.execute(
        """SELECT q.*, i.title, i.price, i.image, i.status AS item_status, i.id AS item_id,
                  u.nickname AS buyer_name, u.grade AS buyer_grade,
                  (SELECT content FROM messages m WHERE m.inquiry_id = q.id ORDER BY m.id DESC LIMIT 1) AS last_msg,
                  (SELECT created_at FROM messages m WHERE m.inquiry_id = q.id ORDER BY m.id DESC LIMIT 1) AS last_at,
                  (SELECT COUNT(*) FROM messages m WHERE m.inquiry_id = q.id) AS msg_count
           FROM inquiries q
           JOIN items i ON i.id = q.item_id
           JOIN users u ON u.id = q.buyer_id
           WHERE q.seller_id = ? ORDER BY q.updated_at DESC""",
        (uid,),
    ).fetchall()

    inquiries = db.execute(
        """SELECT q.*, i.title, i.price, i.image, i.status AS item_status, i.id AS item_id,
                  u.nickname AS seller_name, u.grade AS seller_grade,
                  (SELECT content FROM messages m WHERE m.inquiry_id = q.id ORDER BY m.id DESC LIMIT 1) AS last_msg,
                  (SELECT created_at FROM messages m WHERE m.inquiry_id = q.id ORDER BY m.id DESC LIMIT 1) AS last_at,
                  (SELECT COUNT(*) FROM messages m WHERE m.inquiry_id = q.id) AS msg_count
           FROM inquiries q
           JOIN items i ON i.id = q.item_id
           JOIN users u ON u.id = q.seller_id
           WHERE q.buyer_id = ? ORDER BY q.updated_at DESC""",
        (uid,),
    ).fetchall()

    favs = db.execute(
        """SELECT i.*, u.nickname AS seller_name, u.grade AS seller_grade
           FROM favorites f
           JOIN items i ON i.id = f.item_id
           JOIN users u ON u.id = i.seller_id
           WHERE f.user_id = ? ORDER BY f.created_at DESC""",
        (uid,),
    ).fetchall()

    summary = {
        "posts": len(posts),
        "open": sum(1 for p in posts if p["status"] == "open"),
        "closed": sum(1 for p in posts if p["status"] == "closed"),
        "waiting": sum(1 for q in inbox if q["status"] == "pending"),
    }

    return render_template(
        "my.html", tab=tab, posts=posts, inbox=inbox, inquiries=inquiries,
        favs=favs, summary=summary,
    )


# --------------------------------------------------------------------------
# 错误页
# --------------------------------------------------------------------------
@app.errorhandler(404)
def not_found(e):
    return render_template("error.html", code=404, msg="页面走丢了，这条信息可能已经被撤下"), 404


@app.errorhandler(403)
def forbidden(e):
    return render_template("error.html", code=403, msg="你没有权限进行这个操作"), 403


# --------------------------------------------------------------------------
# 初始化数据库 + 演示数据
# --------------------------------------------------------------------------
SEED_PASSWORD = os.environ.get("FLEA_SEED_PASSWORD", "Campus@2026")

SEED_USERS = [
    ("linxue", "林小满", "大四", "西区 3 号楼", "微信 linxue_2026", "即将毕业，宿舍清仓中"),
    ("zhezhe", "阿哲", "大三", "东区 7 号楼", "微信 zhezhe_go", "实习搬走，闲置急出"),
    ("yuanyuan", "圆圆学姐", "大四", "南苑 1 号楼", "微信 yuan_2333", "考研结束，书本便宜出"),
    ("chenchen", "陈同学", "大二", "北区 5 号楼", "微信 chen_0214", "蹲一个便宜的台灯"),
    ("xiaoxin", "新新", "大一", "北区 2 号楼", "微信 xinxin_666", "刚入学，什么都需要"),
    ("amay", "阿May", "大二", "西区 8 号楼", "", "喜欢淘二手好物，站内联系就好"),
]

SEED_ITEMS = [
    ("linxue", "高等数学 同济第七版 上下册", "教材书籍", 15, 89, "九成新", "西区 3 号楼", 2,
     "课本有少量笔记，公式推导写得很全，期末复习直接抄作业级重点。附赠习题册一本。"),
    ("linxue", "iPad Air 4 64G 深空灰 + 手写笔", "电子数码", 1680, 4399, "八成新", "西区 3 号楼", 6,
     "2021 年买的，边框有轻微使用痕迹，屏幕无划痕，电池健康 86%。配二代笔和磁吸保护壳，看网课记笔记神器。"),
    ("linxue", "小米米家台灯 Pro", "生活用品", 45, 169, "九成新", "西区 3 号楼", 1,
     "亮度色温都能调，宿舍熬夜赶论文必备。搬走前出，可送到楼下。"),
    ("zhezhe", "宿舍折叠小书桌", "宿舍家具", 25, 79, "八成新", "东区 7 号楼", 0,
     "床上可用，桌面很稳，承重没问题。折起来不占地方，毕业搬宿舍刚好用得上。"),
    ("zhezhe", "瑜伽垫 + 2kg 哑铃一对", "运动健身", 30, 120, "八成新", "东区 7 号楼", 0,
     "垫子只用了半个学期，哑铃是包胶款不伤地板。整套带走 30 元。"),
    ("zhezhe", "罗技 MX Master 3 无线鼠标", "电子数码", 380, 699, "九成新", "东区 7 号楼", 4,
     "办公真的舒服，多设备切换很方便。因为公司发了新鼠标所以出掉，配件齐全。"),
    ("yuanyuan", "考研英语真题 + 手写笔记全套", "教材书籍", 20, 65, "有使用痕迹", "南苑 1 号楼", 3,
     "2010-2024 真题，阅读部分做满了批注，附作文模板打印版。上岸了留给学弟学妹。"),
    ("yuanyuan", "雅诗兰黛小棕瓶小样套装", "美妆个护", 88, 260, "全新未拆", "南苑 1 号楼", 0,
     "专柜赠品，一次没用过，全新未拆封。日期新鲜，介意小样勿拍。"),
    ("yuanyuan", "优衣库轻型羽绒服 M 码 米白", "衣物鞋包", 120, 499, "九成新", "南苑 1 号楼", 2,
     "去年冬天买的，只穿过三四次，已干洗。南方冬天够穿，可压缩收纳很小。"),
    ("zhezhe", "北欧风落地衣架", "宿舍家具", 35, 99, "八成新", "东区 7 号楼", 1,
     "实木质感，挂十几件衣服完全没压力。拆开可以带走，男生宿舍也合适。"),
    ("linxue", "捷安特山地自行车", "运动健身", 420, 1580, "有使用痕迹", "西区 3 号楼", 8,
     "骑了两年，链条刚上过油，刹车灵敏。送车锁和打气筒，校内代步很省时间。"),
    ("zhezhe", "电热水壶 + 保温杯组合", "生活用品", 28, 128, "九成新", "东区 7 号楼", 0,
     "水壶 1.5L，宿舍限电也能用（800W）。保温杯基本全新，一起打包便宜出。"),
    ("yuanyuan", "Switch OLED + 塞尔达传说", "电子数码", 1450, 2598, "九成新", "南苑 1 号楼", 7,
     "白色 OLED 版本，屏幕无划痕，附带原装底座和 HDMI 线。游戏一共三张卡带，打包出。"),
    ("linxue", "毛绒玩偶一大袋（6 只）", "其他闲置", None, 0, "八成新", "西区 3 号楼", 0,
     "抓娃娃攒下来的，洗干净了。一只 2 元，打包带走更划算，送给想装饰床位的同学。"),
]


def migrate(db):
    """兼容旧版本数据库"""
    try:
        item_cols = [r["name"] for r in db.execute("PRAGMA table_info(items)").fetchall()]
        if "status" in item_cols:
            db.execute("UPDATE items SET status = 'open' WHERE status IN ('on_sale', 'reserved')")
            db.execute("UPDATE items SET status = 'closed' WHERE status = 'sold'")
        db.execute("DROP TABLE IF EXISTS orders")

        inq_cols = [r["name"] for r in db.execute("PRAGMA table_info(inquiries)").fetchall()]
        if inq_cols:
            if "buyer_contact_ok" not in inq_cols:
                db.execute("ALTER TABLE inquiries ADD COLUMN buyer_contact_ok INTEGER NOT NULL DEFAULT 0")
            if "seller_contact_ok" not in inq_cols:
                db.execute("ALTER TABLE inquiries ADD COLUMN seller_contact_ok INTEGER NOT NULL DEFAULT 0")
            db.execute("UPDATE inquiries SET status = 'chatting' WHERE status = 'contacting'")
    except sqlite3.Error as exc:
        print("migrate skip:", exc)


def init_db(seed=True):
    os.makedirs(INSTANCE_DIR, exist_ok=True)
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    db.executescript(SCHEMA)
    migrate(db)

    if not seed:
        db.commit()
        db.close()
        return

    count = db.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    if count == 0:
        id_map = {}
        for username, nickname, grade, campus, contact, _ in SEED_USERS:
            cur = db.execute(
                """INSERT INTO users (username, password_hash, nickname, grade, campus, contact, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (username, generate_password_hash(SEED_PASSWORD), nickname, grade, campus, contact,
                 now_str()),
            )
            id_map[username] = cur.lastrowid

        base = datetime.now()
        ids = []
        name_to_key = {c["name"]: c["key"] for c in CATEGORIES}
        for idx, (uname, title, cat_name, price, orig, cond, loc, views, desc) in enumerate(SEED_ITEMS):
            cat = name_to_key.get(cat_name, "other")
            created = (base - timedelta(hours=3 * len(SEED_ITEMS) - idx * 3)).strftime("%Y-%m-%d %H:%M:%S")
            cur = db.execute(
                """INSERT INTO items (seller_id, title, description, price, original_price, category,
                                      condition, location, image, status, views, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, '', 'open', ?, ?)""",
                (id_map[uname], title, desc, price, orig or None, cat, cond, loc, views, created),
            )
            ids.append(cur.lastrowid)

        ts = now_str()

        def add_inquiry(item_idx, buyer, seller, status, msgs, flags=(0, 0)):
            cur = db.execute(
                """INSERT INTO inquiries (item_id, buyer_id, seller_id, status,
                                          buyer_contact_ok, seller_contact_ok, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (ids[item_idx], id_map[buyer], id_map[seller], status, flags[0], flags[1], ts, ts),
            )
            qid = cur.lastrowid
            for who, text in msgs:
                db.execute(
                    "INSERT INTO messages (inquiry_id, sender_id, content, created_at) VALUES (?, ?, ?, ?)",
                    (qid, id_map[who], text, ts),
                )
            return qid

        # 已同意、双方都发了联系方式的一段沟通
        add_inquiry(1, "chenchen", "linxue", "chatting", [
            ("chenchen", "学姐你好，iPad 还在吗？想了解一下电池健康度～"),
            ("linxue", "在的，电池 86%，屏幕没划痕。你要是感兴趣，可以来西区 3 号楼看看。"),
            ("chenchen", "好呀，我明天晚上 7 点过去方便吗？"),
        ], flags=(1, 1))

        # 已约好的一段沟通（只有一方留了联系方式）
        add_inquiry(3, "xiaoxin", "zhezhe", "agreed", [
            ("xiaoxin", "学哥好，这个书桌还在吗？我想搬回宿舍用。"),
            ("zhezhe", "在的，25 块，你什么时候方便来东区 7 号楼拿？"),
            ("xiaoxin", "明天上午 10 点可以吗？我带个同学一起搬。"),
            ("zhezhe", "可以，10 点楼下等你。"),
        ], flags=(0, 1))

        # 待处理的联系申请（演示「同意 / 婉拒」）
        add_inquiry(5, "amay", "zhezhe", "pending", [
            ("amay", "同学你好，这个鼠标还在吗？我主要是想用来做设计，方便的话聊聊？"),
        ])

        db.execute("UPDATE items SET status = 'closed' WHERE id = ?", (ids[3],))

        for uid, iid in ((id_map["xiaoxin"], ids[6]), (id_map["amay"], ids[12]),
                         (id_map["amay"], ids[9]), (id_map["chenchen"], ids[0])):
            db.execute(
                "INSERT OR IGNORE INTO favorites (user_id, item_id, created_at) VALUES (?, ?, ?)",
                (uid, iid, ts),
            )
    db.commit()
    db.close()


if __name__ == "__main__":
    init_db(seed=True)
    port = int(os.environ.get("PORT", 5000))
    host = os.environ.get("HOST", "127.0.0.1")
    print(f"校园闲置信息墙已启动 → http://{host}:{port}")
    app.run(host=host, port=port, debug=False, threaded=True)
else:
    # WSGI 部署（gunicorn / PythonAnywhere）时也要保证库表存在
    try:
        init_db(seed=False)
    except Exception as exc:  # noqa: BLE001
        print("init_db on import skipped:", exc)
