"""只在服务器上读取 DeepSeek 密钥。网页拿不到这把钥匙。"""

import json
import os
import urllib.request


def configured():
    return bool(os.environ.get("DEEPSEEK_API_KEY", "").strip())


def chat(messages):
    key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if not key:
        return None
    model = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat").strip() or "deepseek-chat"
    payload = {
        "model": model,
        "temperature": 0.1,
        "messages": messages,
        "response_format": {"type": "json_object"},
    }
    request = urllib.request.Request(
        "https://api.deepseek.com/chat/completions",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=25) as response:
            body = json.loads(response.read().decode("utf-8"))
        content = body["choices"][0]["message"]["content"].strip()
        usage = body.get("usage") or {}
        return {
            "content": content,
            "prompt_tokens": int(usage.get("prompt_tokens") or 0),
            "completion_tokens": int(usage.get("completion_tokens") or 0),
        }
    except Exception:
        return None


def chat_text(messages):
    key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if not key:
        return None
    model = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat").strip() or "deepseek-chat"
    payload = {"model": model, "temperature": 0.2, "messages": messages}
    request = urllib.request.Request(
        "https://api.deepseek.com/chat/completions",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=25) as response:
            body = json.loads(response.read().decode("utf-8"))
        content = body["choices"][0]["message"]["content"].strip()
        usage = body.get("usage") or {}
        return {
            "content": content,
            "prompt_tokens": int(usage.get("prompt_tokens") or 0),
            "completion_tokens": int(usage.get("completion_tokens") or 0),
        }
    except Exception:
        return None
