# 部署到 PythonAnywhere（免费、网址固定、不依赖你的电脑）

> 这是目前最省事的「固定网址」方案：注册免费账号后，网址是 `https://你的用户名.pythonanywhere.com`，永久不变，你的电脑关机也照常访问。
> 全程 10 分钟左右，不需要信用卡。

## 准备

`deploy/campus-wall.zip` 就是完整的部署包（后端 + 模板 + 样式 + 图标，不含本机数据库）。

## 第 1 步：注册

打开 https://www.pythonanywhere.com/register/ ，注册一个 **Beginner（免费）** 账号。
用户名会成为网址的一部分，比如用户名 `xiaoming`，网址就是 `https://xiaoming.pythonanywhere.com`。

## 第 2 步：上传并解压

1. 登录后进入 **Files** 页面
2. 点右上角 **Upload a file**，上传 `campus-wall.zip`（会传到 `/home/你的用户名/`）
3. 打开 **Consoles → Bash**，执行：

```bash
cd ~
unzip -o campus-wall.zip -d campus-wall
```

## 第 3 步：安装依赖

在同一个 Bash 控制台里：

```bash
cd ~/campus-wall
mkvirtualenv --python=/usr/bin/python3.10 venv
pip install -r requirements.txt
```

看到 `Successfully installed Flask...` 即可。

## 第 4 步：创建 Web 应用

1. 顶部菜单 **Web** → **Add a new web app**
2. 选择 **Manual configuration**（不要选 Flask 模板）→ **Python 3.10**
3. 建好后在页面上依次填写：

| 设置项 | 填写内容 |
| --- | --- |
| Source code | `/home/你的用户名/campus-wall` |
| Working directory | `/home/你的用户名/campus-wall` |
| Virtualenv | `/home/你的用户名/.virtualenvs/venv` |

4. 点 **WSGI configuration file** 链接，把里面原有内容**全部删除**，粘贴 `deploy/wsgi.py` 的内容，并把第一行的 `USERNAME` 改成你的用户名：

```python
PROJECT = "/home/你的用户名/campus-wall"
```

5. 回到 Web 页面，找到 **Static files**，添加一条：

| URL | Directory |
| --- | --- |
| `/static/` | `/home/你的用户名/campus-wall/static` |

6. 点最上面的绿色 **Reload 你的用户名.pythonanywhere.com**

## 第 5 步：打开看看

访问 `https://你的用户名.pythonanywhere.com`

- 数据库会自动建表，是**空的**（没有演示数据），直接注册第一个账号即可
- 想先看看效果、要演示数据的话，在 Bash 里执行：

```bash
cd ~/campus-wall
workon venv
python -c "from app import init_db; init_db(seed=True)"
```

## 注意事项

- **每 3 个月要点一次续期**：登录后在 Web 页会提示 *Run until 3 months from today*，点一下就再续 3 个月，完全免费。
- 免费版只有 512MB 磁盘、每天有 CPU 秒数配额，给同学用完全够；图片别传太多超大原图。
- 上传的图片保存在 `~/campus-wall/static/uploads/`，通过 `/static/uploads/...` 访问，不需要额外配置。
- 数据备份：在 Files 页面下载 `~/campus-wall/instance/campus_flea.db` 即可。
- 如果以后想绑自己的域名（如 `wall.example.com`），PythonAnywhere 也支持，但免费版不支持自定义域名。

## 以后要更新代码

本地改完 `app.py` / `templates/` 后，重新打包上传、解压覆盖即可（数据库在 `instance/` 里，只要不覆盖这个目录，数据不会丢）：

```bash
cd ~
unzip -o campus-wall.zip -d campus-wall
```

然后在 Web 页面点一次 **Reload**。
