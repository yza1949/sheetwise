# 智析 Sheetwise

脏表格上传后，规则标出问题。低风险的自动接受，拿不准的留给人工复核，再下载干净表格。数据在服务器的 SQLite 里。

全部代码都在这个文件夹里。你本机现在的目录是 `C:\Users\YZA\Sheetwise\no.2`。

## 目录

| 路径 | 职责 |
|---|---|
| `frontend/` | 网页。只显示和发请求，不算检测 |
| `frontend/app/` | 登录注册、工作区、上传、模板、进度、复核、报告、历史、AI 需求分析、用户、设置 |
| `frontend/components/Shell.tsx` | 左侧导航和顶栏 |
| `frontend/lib/api.ts` | 所有请求。`NEXT_PUBLIC_API_BASE_URL` 留空时走本机 `/api` |
| `frontend/lib/i18n.tsx` | 中文 / 英文界面 |
| `backend/main.py` | 启动接口、读 `.env`、跨域 |
| `backend/database.py` | SQLite，启动时建表。库文件在 `backend/data/sheetwise.db` |
| `backend/auth.py` | 密码和 Cookie 里的 `session_id`。注册要填两次密码 |
| `backend/cleaning.py` | 通用检查，以及模板规则怎么落到每一格 |
| `backend/demo_tables.py` | 五份模板的中英测试表，各约 50 行 |
| `backend/llm_client.py` | 只在服务器上读 `DEEPSEEK_API_KEY` 并调用 DeepSeek |
| `backend/quota.py` | 每人 30 次，另加 10 万 token |
| `backend/records.py` | 一次分析的读写 |
| `backend/routers/` | 登录、上传复核、模板、AI 提问 |
| `docs/api.md` | 接口约定 |

`frontend/node_modules`、`backend/.venv`、`backend/data` 是装出来或跑起来才有的，不是手写代码。

## 这一版做什么

1. 选一份模板，或直接上传。
2. 「智能分析模板」列出准备执行的规则。配了密钥就问 DeepSeek，扣 1 次；没配就用模板里写好的规则，不扣次数。可以去掉某一条。
3. 点「查看测试数据」先展开大约 50 行，看完再点「用这份测试数据开始分析」。也可以改上传同一类列名的真实表。
4. 界面切到 English 后，页面文字、日志、测试表的表头和内容都是英文。
5. 进度页看到规则引擎的日志，然后人工复核，再看报告。报告上可以返回人工复核。左边的进度、复核、报告会打开最近一次分析。
6. 复核页默认只展开还要你看的几条。低风险的在「已自动处理」里，检查后没有问题的行在「没有问题」里，两块都默认收着。
7. 复核完成后，到「AI 需求分析」针对这张表提问。这一问也扣 1 次。
8. 设置页能看剩余次数。充值按钮只留着，不能付钱。

五份模板：销售订单、客户联系人、库存、报销、成绩。大约 50 行里，需要人看的是 4 到 5 条。自动接受的是空格、能唯一读出的日期、电话数字、邮箱、大小写。金额对不上、编号两条内容不同、空着的必填、不在模板名单里的值、分数超出范围，这些留给人。

开放注册。第一个人是管理员。成员只能看自己的分析。注册时密码要填两次。

密钥只写在 `backend/.env` 的 `DEEPSEEK_API_KEY=`。不要写进前端，不要提交 Git。

## 本地启动（Windows PowerShell）

窗口一：

```powershell
cd C:\Users\YZA\Sheetwise\no.2\backend
.\.venv\Scripts\Activate.ps1
fastapi dev main.py
```

窗口二：

```powershell
cd C:\Users\YZA\Sheetwise\no.2\frontend
npm run dev
```

浏览器打开 http://localhost:8080 。接口在 http://127.0.0.1:8000 ，文档是 http://127.0.0.1:8000/docs 。

第一次还没有虚拟环境时，在 `backend` 里先执行 `python -m venv .venv`、激活、`pip install -r requirements.txt`、`copy .env.example .env`。前端第一次执行 `npm install`。`.env.local` 里的接口地址留空。

## 上线（课程 7.1）

1. 服务器装好 `git`、`nginx`、`python3-venv`、Node.js。
2. 代码用 Git 拉到服务器。`.env`、`.venv`、`node_modules`、`backend/data/` 不进仓库。
3. 后端复制 `.env.example` 为 `.env`。`ALLOWED_ORIGINS` 写成 `http://服务器IP`，不要加 `:80`。需要模型再写上 `DEEPSEEK_API_KEY`。
4. `pip install -r requirements.txt` 后执行 `fastapi run main.py --host 0.0.0.0 --port 8000`。安全组放行 8000。
5. 前端 `.env.production` 写 `NEXT_PUBLIC_API_BASE_URL=http://服务器IP:8000`，然后 `npm install` 和 `npm run build`。产物在 `frontend/out/`。
6. Nginx 网站根目录指到 `out/`，监听 80。

反向代理、HTTPS、PostgreSQL 这次不做。
