# -*- coding: utf-8 -*-
"""端到端流程自测（Flask test client）"""
import os
import re
import sqlite3
import sys
import tempfile
import uuid

os.environ["FLEA_DB"] = os.path.join(tempfile.gettempdir(), f"wall_test_{uuid.uuid4().hex}.db")

from app import app, DB_PATH, init_db, SEED_PASSWORD as SEED_PW

FAILED = False


def check(label, cond):
    global FAILED
    print(("  ✅ " if cond else "  ❌ ") + label)
    if not cond:
        FAILED = True


def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def main():
    init_db(seed=True)

    print("1. 游客访问")
    c = app.test_client()
    html = c.get("/").get_data(as_text=True)
    check("首页 200", c.get("/").status_code == 200)
    check("游客只看到 6 条信息", html.count('class="card"') == 6)
    check("首页出现解锁提示", "条信息等你查看" in html)
    check("首页强调任何人都可发布", "谁都可以" in html)
    check("首页无演示账号痕迹", "演示账号" not in html and "123456" not in html)
    r = c.get("/browse")
    check("游客访问 /browse 跳转登录", r.status_code == 302 and "/login" in r.headers["Location"])
    h = c.get("/item/1").get_data(as_text=True)
    check("游客可看详情，但联系方式不公开", "双方同意后可选发送" in h)
    r = c.post("/item/5/contact", data={})
    check("游客发起联系被拦截", r.status_code == 302 and "/login" in r.headers["Location"])

    print("2. 注册（年级不限制身份）")
    c = app.test_client()
    r = c.post("/register", data={
        "username": "freshman", "password": SEED_PW, "password2": SEED_PW,
        "nickname": "小新生", "grade": "大一", "campus": "北区 2 号楼", "contact": "",
    }, follow_redirects=True)
    check("注册成功", "欢迎加入校园闲置信息墙" in r.get_data(as_text=True))
    conn = db()
    row = conn.execute("SELECT * FROM users WHERE username='freshman'").fetchone()
    check("用户写入数据库", row is not None and row["grade"] == "大一")
    check("联系方式可为空", row["contact"] == "")
    r = c.get("/publish")
    check("大一也能打开发布页", r.status_code == 200 and "贴上信息墙" in r.get_data(as_text=True))
    r = c.post("/publish", data={
        "title": "大一也能发布的小风扇", "category": "life", "condition": "九成新",
        "price": "20", "location": "北区 2 号楼",
        "description": "宿舍小风扇，风力够用，夏天过完就闲置了，便宜出。",
    }, follow_redirects=True)
    check("大一发布成功", "信息已发布" in r.get_data(as_text=True))
    conn = db()
    check("商品写入数据库", conn.execute("SELECT 1 FROM items WHERE title='大一也能发布的小风扇'").fetchone() is not None)

    print("3. 登录与浏览")
    c = app.test_client()
    r = c.post("/login", data={"username": "chenchen", "password": SEED_PW}, follow_redirects=True)
    check("登录成功", "登录成功" in r.get_data(as_text=True))
    r = c.get("/browse")
    check("登录后可浏览全部（>6 条）", r.status_code == 200 and r.get_data(as_text=True).count('class="card"') > 6)
    check("关键词搜索命中", "小米米家台灯" in c.get("/browse?q=台灯").get_data(as_text=True))
    check("分类筛选生效", "高等数学" in c.get("/browse?cat=books").get_data(as_text=True))
    check("价格排序可用", c.get("/browse?sort=price_asc").status_code == 200)

    print("4. 发起联系 -> 待对方同意")
    conn = db()
    item_id = conn.execute("SELECT id FROM items WHERE title LIKE '%罗技%'").fetchone()["id"]
    r = c.post(f"/item/{item_id}/contact", data={"message": "同学好，这个鼠标还在吗？"})
    check("发起联系后跳转沟通页", r.status_code == 302 and "/chat/" in r.headers["Location"])
    inquiry_id = int(re.search(r"/chat/(\d+)", r.headers["Location"]).group(1))
    h = c.get(f"/chat/{inquiry_id}").get_data(as_text=True)
    check("申请状态为待同意", "联系申请已发送，等待对方同意" in h)
    check("待同意时不能发消息", "等待对方同意后才能发送消息" in h)
    r = c.post(f"/chat/{inquiry_id}/send", data={"content": "偷偷发一条"}, follow_redirects=True)
    check("强行发消息被拦截", "对方同意联系后" in r.get_data(as_text=True))
    conn = db()
    check("会话状态 pending", conn.execute("SELECT status FROM inquiries WHERE id=?", (inquiry_id,)).fetchone()["status"] == "pending")
    check("默认未共享联系方式", conn.execute(
        "SELECT buyer_contact_ok, seller_contact_ok FROM inquiries WHERE id=?", (inquiry_id,)
    ).fetchone()[:] == (0, 0))

    print("5. 发布者同意 -> 开始沟通")
    s = app.test_client()
    s.post("/login", data={"username": "zhezhe", "password": SEED_PW})
    h = s.get("/my?tab=inbox").get_data(as_text=True)
    check("发布者在收件箱看到申请", "陈同学" in h and "同意" in h)
    r = s.post(f"/inquiry/{inquiry_id}/accept", follow_redirects=True)
    check("同意联系", "已同意联系" in r.get_data(as_text=True))
    conn = db()
    check("会话状态 chatting", conn.execute("SELECT status FROM inquiries WHERE id=?", (inquiry_id,)).fetchone()["status"] == "chatting")
    r = s.post(f"/chat/{inquiry_id}/send", data={"content": "在的，明天下午可以来看看。"}, follow_redirects=True)
    check("同意后可以发消息", "明天下午可以来看看" in r.get_data(as_text=True))

    print("6. 联系方式自愿交换")
    h = c.get(f"/chat/{inquiry_id}").get_data(as_text=True)
    check("未发送时对方看不到联系方式", "对方还没有发送" in h)
    r = c.post(f"/inquiry/{inquiry_id}/share-contact", follow_redirects=True)
    check("买家发送自己的联系方式", "已把你的联系方式发给对方" in r.get_data(as_text=True))
    h = s.get(f"/chat/{inquiry_id}").get_data(as_text=True)
    check("发布者看到买家联系方式", "微信 chen_0214" in h)
    check("买家尚未看到卖家联系方式", "对方还没有发送" in c.get(f"/chat/{inquiry_id}").get_data(as_text=True))
    s.post(f"/inquiry/{inquiry_id}/share-contact", follow_redirects=True)
    h = c.get(f"/chat/{inquiry_id}").get_data(as_text=True)
    check("买家看到卖家联系方式", "微信 zhezhe_go" in h)
    s.post(f"/inquiry/{inquiry_id}/share-contact", follow_redirects=True)
    conn = db()
    check("可以撤回联系方式", conn.execute("SELECT seller_contact_ok FROM inquiries WHERE id=?", (inquiry_id,)).fetchone()[0] == 0)

    print("7. 约好与标记已出")
    r = c.post(f"/inquiry/{inquiry_id}/agree", follow_redirects=True)
    check("标记已约好", "已约好" in r.get_data(as_text=True))
    r = s.post(f"/item/{item_id}/status", data={"action": "closed"}, follow_redirects=True)
    check("发布者标记已出", "已标记为「已出」" in r.get_data(as_text=True))
    conn = db()
    check("信息状态 closed", conn.execute("SELECT status FROM items WHERE id=?", (item_id,)).fetchone()["status"] == "closed")

    print("8. 婉拒流程")
    conn = db()
    other_item = conn.execute("SELECT id FROM items WHERE title LIKE '%瑜伽垫%'").fetchone()["id"]
    r = c.post(f"/item/{other_item}/contact", data={"message": "想看看这辆自行车"})
    qid2 = int(re.search(r"/chat/(\d+)", r.headers["Location"]).group(1))
    s.post(f"/inquiry/{qid2}/decline", follow_redirects=True)
    conn = db()
    check("婉拒后状态 declined", conn.execute("SELECT status FROM inquiries WHERE id=?", (qid2,)).fetchone()["status"] == "declined")
    check("买家看到被婉拒提示", "对方婉拒了这次联系" in c.get(f"/chat/{qid2}").get_data(as_text=True))

    print("9. 权限校验")
    x = app.test_client()
    x.post("/login", data={"username": "amay", "password": SEED_PW})
    check("他人无法进入私聊（403）", x.get(f"/chat/{inquiry_id}").status_code == 403)
    check("他人无法同意别人申请（403）", x.post(f"/inquiry/{qid2}/accept", data={}).status_code == 403)
    check("无法操作他人信息（403）", x.post(f"/item/{item_id}/status", data={"action": "off"}).status_code == 403)
    check("登录页没有演示账号提示", "演示账号" not in app.test_client().get("/login").get_data(as_text=True))

    print()
    print("结果：" + ("存在失败项 ❌" if FAILED else "全部通过 ✅"))
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
