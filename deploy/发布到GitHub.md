# 把项目发布到你的 GitHub

本地仓库已经准备好了：`D:\workbuddy\flea market`，分支为 `main`，已有 2 次提交、30 个文件。  
**你只需要把本地仓库推到自己的 GitHub 账号**，下面的步骤二选一。

---

## ⚠️ 先解决网络问题（很关键）

这台电脑上 Git 配置了代理 `http://127.0.0.1:7897`（Clash / Verge 之类），  
**代理软件没开的话，访问 GitHub 会直接失败**，报错长这样：

```
fatal: unable to access 'https://github.com/...': Failed to connect to github.com port 443
```

所以推送之前：**先把你的代理软件打开**，确认浏览器能打开 <https://github.com> ，再推送。

---

## 方法一：GitHub Desktop（推荐，不用敲命令）

1. 下载安装：<https://desktop.github.com/>
2. 打开后 **Sign in to GitHub.com**，用浏览器授权登录
3. 菜单 **File → Add local repository…**
4. 路径选择：`D:\workbuddy\flea market` → 点 **Add**  
   （如果提示不是 Git 仓库，说明选错目录了，重新选）
5. 右上角会出现按钮 **Publish repository**，点它
6. 弹窗里：
   - **Name**：`campus-wall`（或你喜欢的名字）
   - **Description**：可留空或写「校园闲置信息墙」
   - **Keep this code private**：勾上就是私有仓库，不勾就是公开仓库
7. 点 **Publish repository**
8. 完成后，在 GitHub 网页打开 `https://github.com/你的用户名/campus-wall`，应该能看到 30 个文件

> 好处：GitHub Desktop 自带凭据管理，不用手动折腾 token。

---

## 方法二：命令行（4 条命令）

### 1. 在 GitHub 新建空仓库

<https://github.com/new>

- Repository name：`campus-wall`
- **不要**勾选 Add a README file / Add .gitignore / Choose a license（必须留空）
- 点 **Create repository**

### 2. 本地执行（把用户名换成你的）

```bash
cd "D:\workbudy\flea market"
git remote add origin https://github.com/你的用户名/campus-wall.git
git push -u origin main
```

### 3. 登录验证

- 如果弹出 **GitHub 登录窗口** → 选 `Sign in with your browser`，浏览器里点授权即可
- 如果没有弹窗、要求输入用户名密码 → **GitHub 早已不支持输登录密码**，要生成 Token：
  1. 打开 <https://github.com/settings/tokens> （Tokens (classic)）
  2. **Generate new token (classic)** → Note 随便写 → Expiration 选 7 天 → 勾选 **repo**
  3. 生成后复制 `ghp_...` 开头的字符串
  4. 回到终端，用户名填你的 GitHub 用户名，**密码粘贴这个 token**

### 4. 确认

```bash
git log --oneline -2
git remote -v
```

浏览器打开 `https://github.com/你的用户名/campus-wall` 检查文件是否都在。

---

## 常见报错对照

| 报错                                                | 原因 / 解决                              |
| ------------------------------------------------- | ------------------------------------ |
| `Failed to connect to github.com port 443`        | 代理没开，先打开代理软件                         |
| `remote origin already exists`                    | 已有远端：`git remote set-url origin 新地址` |
| `src refspec main does not match any`             | 分支不叫 main：先 `git branch -M main`     |
| `Support for password authentication was removed` | 不能用登录密码，改用 Personal Access Token     |
| 推上去是空的 / 只有 README                                | 检查 GitHub 页面左上分支是否切到 `main`          |
| `Everything up-to-date` 但网页没变化                    | 本地没新提交，或推到了别的分支                      |

---

## 推送成功之后

GitHub 只是**代码托管**，它不会让 Flask 网站跑起来（GitHub Pages 只支持静态页面）。  
要变成能访问的网址，接着做：

- **PythonAnywhere**（推荐，免费 + 固定网址 + 云上运行）：见 `deploy/部署到PythonAnywhere.md`，  
  可以在 Web 页面直接 `git clone https://github.com/你的用户名/campus-wall.git`
- **Render**：连仓库即可跑，但免费版磁盘是临时的，SQLite 数据会丢

> 仓库如果是 **Private**，在 PythonAnywhere 上用 `git clone` 需要用户名 + token，  
> 或者把仓库设为 Public 直接 clone 最省事。
