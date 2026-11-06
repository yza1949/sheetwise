# 接口约定

浏览器带 Cookie：`session_id`。除注册和登录外，都要先登录。

错误时 HTTP 状态不是 200，JSON 是 `{ "detail": "错误码" }`。例如 `BAD_LOGIN`、`EMAIL_TAKEN`、`NOT_FOUND`、`UNREVIEWED`。

| 方法 | 路径 | 作用 |
|---|---|---|
| POST | `/api/auth/register` | `{name, email, password}` → 用户 |
| POST | `/api/auth/login` | `{email, password}` → 用户 |
| POST | `/api/auth/logout` | 退出 |
| GET | `/api/auth/me` | 当前用户 |
| PATCH | `/api/auth/me` | `{name}` 改显示名 |
| GET | `/api/users` | 管理员看用户 |
| DELETE | `/api/users/{id}` | 管理员删除用户及其分析 |
| GET | `/api/datasets?q=&status=` | 列表。成员只有自己的 |
| POST | `/api/datasets` | 表单：file、name、question、lang |
| POST | `/api/datasets/sample` | `{question, lang}` 用示例表 |
| GET | `/api/datasets/{id}?lang=` | 详情、预览、问题列表、提醒和回答 |
| DELETE | `/api/datasets/{id}` | 仅管理员 |
| POST | `/api/datasets/{id}/plan` | `{question, lang}` 生成复核前提醒 |
| POST | `/api/datasets/{id}/anomalies/{anomalyId}` | `{action: accept\|edit\|ignore, value?}` |
| POST | `/api/datasets/{id}/anomalies/{anomalyId}/undo` | 撤销 |
| POST | `/api/datasets/{id}/accept-all` | 接受还没点过的 |
| POST | `/api/datasets/{id}/complete` | `{lang}` 全部点完后完成，并写回答 |
| GET | `/api/datasets/{id}/download` | 干净 CSV |
| GET | `/api/datasets/{id}/report` | JSON 报告 |
