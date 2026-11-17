# Sheetwise · motion page

A single-file, scroll-driven page for the Sheetwise pitch. No build step is required. The page itself works offline, and its sign-in links lead to the existing Sheetwise web application.

```
sheetwise-motion/
  index.html      ← the whole page (HTML + CSS + JS + inline screenshot + inline QR)
  assets/
    review.png    ← source of the embedded screenshot (not loaded by the page)
  README.md
```

`index.html` is ~157 KB because the real screenshot and the QR are embedded as data. Nothing is fetched at runtime.

## Open it

Double-click `index.html`, or serve it for correct anchor behaviour:

```powershell
python -m http.server 8090
# http://127.0.0.1:8090
```

## Language

English and Chinese are both in the DOM, switched by `html[data-lang]`:

```
html[data-lang="en"] [lang="zh"] { display:none }
html[data-lang="zh"] [lang="en"] { display:none }
```

The choice is remembered in `localStorage`, can be forced with `?lang=zh` / `?lang=en`, and otherwise follows the browser language. A tiny script in `<head>` sets the attribute before first paint, so there is no flash of the wrong language.

Every string is duplicated rather than injected by JavaScript — this keeps the animation state intact and means the page still reads correctly if JS fails. If you add a string, add both `lang="en"` and `lang="zh"` copies.

## What is on the page

| # | Scene | Effect |
|---|---|---|
| 1 | Hero and cleaning archive | browse five illustrative completed tasks with the wheel, arrows, keyboard or a horizontal swipe. The number rail follows the active card, and pulling out a card reveals its cleaning summary |
| 2 | Three cells | cards lift on hover; space / phone blue (folded), amount amber (waits) |
| 3 | Fifty rows in, five out | **real review screen** in a glass window, live dot, three numbered notes, counters 0 → 50 / 45 / 5 |
| 4 | The pause | explains why the review waits for a decision and links back to the cleaning archive |
| 5 | Close | invitation to try 50 rows, product sign-in and a QR code |

## The screenshot

Scene 3 uses a real capture of the running product (`/review`), cropped to the content area and embedded as a base64 PNG. It sits in a glass “window” with a 10 px uppercase path label and a green live dot, so it reads as a screen, not as a picture dropped onto the page.

Two rules keep it consistent:

- **No frame of its own.** The screenshot has no border, shadow or rounded corner of its own — the glass panel owns all of that, exactly like every other card.
- **Semantic colour survives.** Blue stays “the system handled it”, amber stays “you must decide”. The notes under the image use the same numbered-blue treatment as the section eyebrows.

The sample sheet in the capture is Chinese while the UI is English. Note 03 says so on purpose: the demo tables ship in both languages, and a new analysis follows the interface language. That turns a potential inconsistency into evidence for the bilingual claim instead of hiding it.

To swap the screenshot: replace `assets/review.png`, then re-embed it (or change the `src` to the file path and drop the single-file promise).

## Design tokens

| Token | Value | Where |
|---|---|---|
| `--ink` | `#0A1224` | body text |
| `--blue` | `#2E5BFF` | accent, folded fixes |
| `--amber` | `#B45309` | anything waiting for a human |
| `--line` | `rgba(20,45,100,.10)` | hairlines |
| glass | `rgba(255,255,255,.44–.80)` + `blur(22px) saturate(150%)` | all panels |
| backdrop | `#F3F6FF` + three blurred blobs + SVG grain | fixed layer |

Chinese mode swaps the CJK stack to PingFang / YaHei / Noto Sans, loosens tracking on display type (`-.012em` instead of `-.045em`) and opens up line height — Latin tightness looks wrong on Han characters.

## Behaviour and fallbacks

- **Reduced motion**: entrance and progress transitions are disabled.
- **No JavaScript**: the page reads as a static poster in English, with the completed tasks shown as a list.
- **Touch**: tilt and magnetic buttons are off; scroll effects remain.
- **Mobile**: single column, shorter blur, a three-column order table with tappable cells, and stats in a row.

## 发布与搜索收录

1. **部署宣传页。** 由现有 Sheetwise 服务器的维护者将 `index.html` 部署到 `/welcome`，保留产品首页 `/`、登录页 `/login` 和现有 `/api/` 路由。用手机流量访问宣传页，确认它无需登录即可打开并返回 HTTP 200。
2. **启用 HTTPS 并更新登录入口。** 当前顶部和页尾登录按钮以及二维码指向 `http://124.222.174.101:8080/login`，可用于确认路由。正式发布前，为产品配置有效的 HTTPS，将登录链接、二维码及页面中显示的旧地址更新为最终地址。在同一个 HTTPS 站点发布时，按钮可用 `/login`，二维码须编码完整的 HTTPS 登录网址。上线前用测试账号验证登录、进入产品和退出，并确认服务端通过 HTTPS 设置带 `Secure` 属性的会话 Cookie。
3. **申请收录宣传页。** 在 Google Search Console 验证站点，使用「网址检查」提交最终的 HTTPS 宣传页网址并查看收录状态。宣传页的标题和描述已包含产品名称和用途。搜索结果由搜索引擎决定，申请收录后需要等待。参见 [Google 的网址检查与收录说明](https://developers.google.com/search/docs/crawling-indexing/ask-google-to-recrawl)。

## Known gaps

- No `<picture>` / art direction: one screenshot serves both languages.
- The screenshot is a 2026-11 capture; if the review UI changes, note 01/02 may drift from what the image shows.
- The page is a narrative, not a poster: it needs scrolling, so it is for a link or a screen, not for print.
