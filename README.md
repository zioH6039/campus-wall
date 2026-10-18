# 校园闲置信息墙

一面只负责牵线的校园闲置信息墙：任何人都可以把闲置信息贴上来，任何人都可以联系发布者。**平台不卖东西、不收款、不担保**，联系需要对方同意；联系方式双方自愿交换，也可以全程只用站内沟通；聊好后自己约时间地点，在校园里当面交接。

## 技术栈

- 后端：Python 3 + Flask 3
- 数据库：SQLite（标准库 `sqlite3`，零配置，数据文件 `instance/campus_flea.db`）
- 前端：Jinja2 + 原生 CSS/JS，无构建、无 CDN 依赖，已支持 PWA（可添加到手机桌面）
- 密码：`werkzeug.security` 哈希存储（scrypt）

## 角色与权限

| 访问者 | 浏览首页 | 浏览全部信息 | 查看联系方式 | 发起联系 | 贴闲置信息 | 收藏 |
| --- | --- | --- | --- | --- | --- | --- |
| 未登录游客 | 仅前 6 条 | ❌ 跳转登录 | ❌ | ❌ | ❌ | ❌ |
| 已注册用户（不限年级） | ✅ | ✅ | 双方同意 + 对方自愿发送后可见 | ✅ 需对方同意 | ✅ | ✅ |

年级只写进个人资料用于展示，**不影响任何权限**。

## 联系流程

```
① 在墙上找到信息
② 点「发起联系」，可附一句留言        → 会话状态：待同意
③ 发布者看到申请，选择「同意」或「婉拒」
④ 同意后双方可在站内自由聊天          → 会话状态：沟通中
⑤ 各自决定是否「把我的联系方式发给 TA」（可随时撤回，也可以一直不发）
⑥ 聊好后任意一方点「已约好」          → 会话状态：已约好
⑦ 线下交接完成，发布者把信息标记「已出」→ 会话状态：已结束
```

- 联系方式默认互相不可见；只有对方点了「发送」，你才能在会话里看到他的微信/QQ/手机号。
- 完全可以在不交换任何联系方式的情况下聊完并约见面。
- 拒绝后不会骚扰对方；如需重新沟通，可手动「重新开启」。

## 运行方式

```bash
pip install -r requirements.txt
python app.py                 # 前台运行，http://127.0.0.1:5000
```

首次启动自动建表并写入演示数据（6 个用户、14 条信息、3 段不同状态的会话）。旧版数据库会自动迁移：`on_sale/reserved → open`、`sold → closed`、`contacting → chatting`，并补齐新增字段。

### 后台常驻（不需要一直开着终端）

```bat
start_wall.bat     :: 后台启动 Flask + 公网隧道，无窗口
stop_wall.bat      :: 全部停止
```

- 启动后公网地址会写进 `public_url.txt`，日志在 `logs/`（`app.log`、`service.log`）。
- `run_service.py` 是守护进程：Flask 或隧道掉线会自动拉起。
- 想让服务开机自启：把 `start_wall.bat` 的快捷方式放进
  `%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup`。
- 注意：这种方式下网站仍然跑在这台电脑上，**电脑关机 / 休眠就访问不了**；隧道重启后域名会变（会重新写入 `public_url.txt`）。

### 固定网址（推荐，需要 5 分钟）

免费隧道每次重连都会换域名，链接一旦变了别人就打不开。解决办法是绑定一个固定子域名：

1. 打开 https://admin.localhost.run ，用邮箱注册（免费）
2. 把本机公钥粘贴进去（已自动生成，位于 `C:\Users\16504\.ssh\wall_tunnel.pub`）
3. 在 `start_wall.bat` 里加两行环境变量后重启服务：

```bat
set FLEA_TUNNEL_SUBDOMAIN=你的子域名
set FLEA_TUNNEL_KEY=C:\Users\16504\.ssh\wall_tunnel
```

`run_service.py` 检测到密钥就会自动带上 `-i`，并把子域名写进 `-R`，之后网址固定不变（形如 `https://你的子域名.lhr.life`）。

### 长期稳定（云服务器）

`gunicorn -w 4 -b 0.0.0.0:8000 app:app` + Nginx 反代 + `FLEA_SECRET` 随机密钥，数据库文件记得定期备份。

## 关于小程序 / 微信一键登录

现阶段的结论：**先不做小程序**。原因很实际：

- 微信小程序需要注册 AppID（个人主体需认证）、配置 HTTPS 合法域名并完成 ICP 备案，还要有公网服务器；这些都需要你的账号与资质，我无法代办。
- 微信「一键登录」需要认证服务号（网页授权）或开放平台网站应用，同样需要 AppID + Secret 和备案域名。

已经做的替代方案：网站是移动端优先的 H5，并且带 PWA manifest —— 在微信里打开后选「在浏览器打开」→「添加到主屏幕」，图标和全屏体验跟小程序接近，且不用审核。

如果后续你拿到了 AppID + 备案域名，可以在此基础上接微信网页授权（`snsapi_userinfo`），把「账号密码登录」换成「微信授权登录」，改动量不大（新增一个 OAuth 回调路由 + 用户表加 `openid` 字段）。

## 演示账号

演示数据中的账号密码统一为 `Campus@2026`，**登录页不会显示任何演示账号提示**，其他人只能注册自己的账号：

| 账号 | 昵称 | 年级 | 说明 |
| --- | --- | --- | --- |
| `linxue` | 林小满 | 大四 | 有 1 条在沟通中的会话 |
| `zhezhe` | 阿哲 | 大三 | 有 1 条待同意的申请、1 段已约好 |
| `yuanyuan` | 圆圆学姐 | 大四 | 多条信息 |
| `chenchen` | 陈同学 | 大二 | 与 iPad 那条会话进行中，双方已交换联系方式 |
| `xiaoxin` | 新新 | 大一 | 与书桌那条已约好 |
| `amay` | 阿May | 大二 | 有一条待同意的申请（未填联系方式） |

正式给同学用之前，建议在「我的信息」里删掉演示信息，或直接把 `instance/campus_flea.db` 换成一个空库（`python -c "from app import init_db; init_db(seed=False)"`）。

## 数据库表

- `users`：id / username / password_hash / nickname / grade / campus / contact / created_at
- `items`：id / seller_id / title / description / price（NULL 表示面议）/ original_price / category / condition / location / image / status / views / created_at
  - status：`open` 信息有效、`closed` 已出、`off` 已下架
- `inquiries`：id / item_id / buyer_id / seller_id / status / buyer_contact_ok / seller_contact_ok / created_at / updated_at
  - status：`pending` 待同意、`chatting` 沟通中、`agreed` 已约好、`declined` 已婉拒、`closed` 已结束
  - `*_contact_ok`：双方各自是否已把自己的联系方式发给对方（可撤回）
- `messages`：id / inquiry_id / sender_id / content / created_at
- `favorites`：user_id / item_id / created_at

## 目录结构

```
flea market/
├── app.py                  # 后端逻辑：路由、权限、会话、播种数据
├── run_service.py          # 后台常驻启动器（Flask + 隧道 + 掉线自动重启）
├── start_wall.bat          # 后台启动（无窗口）
├── stop_wall.bat           # 停止服务
├── selftest.py             # 端到端自测（43 项断言）
├── public_url.txt          # 当前公网地址（运行时生成）
├── instance/campus_flea.db # SQLite 数据库
├── logs/                   # 运行日志
├── static/
│   ├── css/style.css       # 基础视觉
│   ├── css/wall.css        # 信息墙 / 沟通组件
│   ├── js/app.js
│   ├── manifest.webmanifest + icon.svg   # PWA
│   └── uploads/
└── templates/
    ├── base.html  _card.html  index.html  browse.html  item.html
    ├── chat.html  my.html  login.html  register.html  publish.html  error.html
```

## 自测

```bash
python selftest.py
```

覆盖：游客部分浏览、联系方式默认不可见、任何年级都可发布/联系、待同意时不能发消息、同意后开聊、联系方式双向可控（含撤回）、约好、婉拒、标记已出、越权 403、登录页无演示账号，共 43 项断言。
