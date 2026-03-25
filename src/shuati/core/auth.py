"""
认证模块 - Playwright 方案

流程：
  1. 检测本地 token 是否有效
  2. 无效时：用 Playwright 打开 Chromium，加载接龙管家登录页
  3. 监听页面 localStorage 变化，检测到 token 写入后自动提取保存
  4. 关闭浏览器，后续所有请求使用保存的 token
  5. token 约 3 天过期，过期后自动重新触发此流程
     （Playwright 保存了持久化 browser profile，微信登录态仍有效，无需重新扫码）
"""

import json
import os
import time
import threading
import base64
import hashlib
import secrets
from datetime import datetime
from shuati.core.config import TOKEN_PATH, DATA_DIR, JIELONG_WEB_BASE

# ── Token 加密 ─────────────────────────────────────────────

def _get_encryption_key() -> bytes:
    """Derive encryption key from machine-specific secret."""
    # Use a fixed key file, create if not exists
    key_file = os.path.join(DATA_DIR, ".key")
    if os.path.exists(key_file):
        with open(key_file, "rb") as f:
            return f.read()
    # Generate new random key
    key = secrets.token_bytes(32)
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(key_file, "wb") as f:
        f.write(key)
    os.chmod(key_file, 0o600)  # Restrict permissions
    return key

def _encrypt_token(token: str) -> str:
    """Encrypt token using AES-like XOR cipher with random IV."""
    key = _get_encryption_key()
    iv = secrets.token_bytes(16)
    encrypted = bytearray()
    for i, c in enumerate(token.encode()):
        encrypted.append(c ^ key[i % len(key)] ^ iv[i % len(iv)])
    # Return IV + encrypted data as base64
    return base64.b64encode(iv + bytes(encrypted)).decode()

def _decrypt_token(encrypted: str) -> str:
    """Decrypt token."""
    try:
        key = _get_encryption_key()
        data = base64.b64decode(encrypted.encode())
        iv = data[:16]
        encrypted_data = data[16:]
        decrypted = bytearray()
        for i, c in enumerate(encrypted_data):
            decrypted.append(c ^ key[i % len(key)] ^ iv[i % len(iv)])
        return decrypted.decode()
    except Exception:
        return ""  # Return empty on decrypt failure

# ── Token 本地存取 ────────────────────────────────────────

def _decode_jwt_exp(token: str) -> int:
    """手动解码 JWT payload 取 exp，不依赖第三方库"""
    try:
        payload = token.split(".")[1]
        payload += "=" * (4 - len(payload) % 4)
        decoded = json.loads(base64.urlsafe_b64decode(payload))
        return decoded.get("exp", 0)
    except Exception:
        return 0


def load_token() -> dict | None:
    if not os.path.exists(TOKEN_PATH):
        return None
    try:
        with open(TOKEN_PATH) as f:
            data = json.load(f)
        # Decrypt token and payload
        encrypted_token = data.get("token", "")
        encrypted_payload = data.get("payload", "")
        data["token"] = _decrypt_token(encrypted_token)
        data["payload"] = _decrypt_token(encrypted_payload) if encrypted_payload else ""
        return data
    except Exception:
        return None


def save_token(bearer_token: str, payload_header: str = ""):
    os.makedirs(DATA_DIR, exist_ok=True)
    exp = _decode_jwt_exp(bearer_token)
    encrypted_token = _encrypt_token(bearer_token)
    encrypted_payload = _encrypt_token(payload_header) if payload_header else ""
    data = {
        "token": encrypted_token,
        "payload": encrypted_payload,
        "exp": exp,
        "saved_at": datetime.now().isoformat(),
    }
    with open(TOKEN_PATH, "w") as f:
        json.dump(data, f, indent=2)
    os.chmod(TOKEN_PATH, 0o600)  # Restrict file permissions
    print(f"[Auth] Token 已保存，过期时间：{datetime.fromtimestamp(exp)}")


def is_token_valid() -> bool:
    data = load_token()
    if not data:
        return False
    return time.time() < data.get("exp", 0) - 600  # 提前 10 分钟视为过期


def get_auth_headers() -> dict:
    data = load_token()
    if not data:
        raise RuntimeError("未登录，请先完成微信扫码登录")
    headers = {"authorization": f"Bearer {data['token']}"}
    if data.get("payload"):
        headers["x-api-request-payload"] = data["payload"]
    return headers


# ── Flask 通知信号（供 /api/auth/status 轮询用）─────────────

_login_event = threading.Event()


def notify_login_success(bearer_token: str, payload_header: str = ""):
    """Playwright 提取到 token 后调用此函数"""
    save_token(bearer_token, payload_header)
    _login_event.set()


# ── Playwright 登录核心 ────────────────────────────────────

# 持久化 browser profile 目录，保存微信登录态
BROWSER_PROFILE_DIR = os.path.join(DATA_DIR, "browser_profile")

_login_in_progress = False
_login_thread: threading.Thread | None = None


def _run_playwright_login():
    """
    在独立线程中运行 Playwright：
    - 打开 Chromium（有界面，用户扫码）
    - 等待 localStorage 出现 token
    - 提取后保存，关闭浏览器
    """
    global _login_in_progress
    try:
        from playwright.sync_api import sync_playwright

        os.makedirs(BROWSER_PROFILE_DIR, exist_ok=True)

        with sync_playwright() as p:
            # 持久化 context：浏览器 profile 保存在本地
            # 下次 token 过期再打开时，微信 session 还在，不需要重新扫码
            context = p.chromium.launch_persistent_context(
                user_data_dir=BROWSER_PROFILE_DIR,
                headless=False,
                no_viewport=True,
                args=[
                    "--window-size=920,700",
                    "--disable-blink-features=AutomationControlled",
                ],
            )

            page = context.new_page()

            # 拦截所有出站请求，捕获 x-api-request-payload 和 authorization
            captured_data = {"payload": "", "token": ""}

            def on_request(request):
                # 捕获 payload
                p_val = request.headers.get("x-api-request-payload", "")
                if p_val and not captured_data["payload"]:
                    captured_data["payload"] = p_val
                    print(f"[Auth] 捕获到 Payload")
                
                # 捕获 Authorization (Bearer token)
                auth_val = request.headers.get("authorization", "")
                if auth_val and "Bearer" in auth_val and not captured_data["token"]:
                    token = auth_val.replace("Bearer ", "").strip()
                    if token:
                        captured_data["token"] = token
                        print(f"[Auth] 通过网络请求捕获到 Token: {token[:15]}...")

            page.on("request", on_request)

            # 打开接龙管家主页（会自动跳到登录页或已登录状态）
            print("[Auth] 正在打开接龙管家，请用微信扫码登录...")
            # 增加超时时间到 60s
            try:
                page.goto(JIELONG_WEB_BASE, wait_until="domcontentloaded", timeout=60000)
            except Exception as e:
                print(f"[Auth] 页面加载警告（不影响登录）：{e}")

            # ── 轮询检测登录成功 ──────────────────────────────
            # 接龙管家登录后写入 localStorage['token']
            max_wait = 300
            poll_start = time.time()
            found_token = None

            while time.time() - poll_start < max_wait:
                # 方法1：localStorage
                try:
                    val = page.evaluate("() => localStorage.getItem('token')")
                    if val and val.startswith("eyJ"):
                        found_token = val
                        print(f"[Auth] 成功从 localStorage 获取 token: {val[:15]}...")
                        break
                except Exception as e:
                    # print(f"[Auth] localStorage 读取失败: {e}")
                    pass

                # 方法2：Cookie（备用）
                try:
                    for c in context.cookies():
                        if c.get("name") == "token" and str(c.get("value", "")).startswith("eyJ"):
                            found_token = c["value"]
                            print(f"[Auth] 成功从 Cookie 获取 token: {found_token[:15]}...")
                            break
                    if found_token:
                        break
                except Exception as e:
                     # print(f"[Auth] Cookie 读取失败: {e}")
                     pass

                # 方法3：SessionStorage (某些版本可能用这个)
                try:
                     val = page.evaluate("() => sessionStorage.getItem('token')")
                     if val and val.startswith("eyJ"):
                         found_token = val
                         print(f"[Auth] 成功从 sessionStorage 获取 token: {val[:15]}...")
                         break
                except Exception:
                     pass

                # 方法4：检查是否通过网络请求捕获到了 Token
                if captured_data["token"]:
                    found_token = captured_data["token"]
                    print(f"[Auth] 确认使用网络请求捕获的 Token")
                    break


                time.sleep(1)

            if not found_token:
                print("[Auth] 超时：5 分钟内未检测到登录成功")
                context.close()
                return

            print("[Auth] 检测到登录成功！正在捕获 payload...")

            # 访问收藏列表，触发 API 请求，捕获 payload
            try:
                page.goto(
                    f"{JIELONG_WEB_BASE}/my-form?tab=5",
                    wait_until="networkidle",
                    timeout=12000,
                )
                time.sleep(2)
            except Exception:
                pass  # payload 捕获失败不影响主功能

            context.close()

            notify_login_success(found_token, captured_data["payload"])
            print("[Auth] 登录完成，浏览器已关闭")

    except ImportError:
        print(
            "[Auth] 缺少依赖，请运行：\n"
            "  pip install playwright\n"
            "  playwright install chromium"
        )
    except Exception as e:
        print(f"[Auth] Playwright 出错：{e}")
    finally:
        _login_in_progress = False


def start_login_browser():
    """
    在后台线程启动 Playwright 登录浏览器（非阻塞）。
    登录完成后 _login_event 会被 set，Flask 前端轮询到后跳转。
    """
    global _login_thread, _login_in_progress
    if _login_in_progress:
        print("[Auth] 登录浏览器已在运行中，请在弹出的窗口中扫码")
        return
    _login_in_progress = True
    _login_event.clear()
    _login_thread = threading.Thread(target=_run_playwright_login, daemon=True)
    _login_thread.start()


def ensure_logged_in(wait: bool = False) -> bool:
    """
    确保已登录。
    - 已登录 → 直接返回 True
    - 未登录 → 启动 Playwright 浏览器（后台线程）
      wait=True 时阻塞等待完成（命令行场景）
      wait=False 时立即返回 False（Web 场景，前端轮询）
    """
    if is_token_valid():
        return True

    print("[Auth] Token 无效，启动 Playwright 登录...")
    start_login_browser()

    if wait:
        print("[Auth] 请在弹出的浏览器窗口中完成微信扫码...")
        _login_event.wait(timeout=300)
        return is_token_valid()

    return False


def get_login_status() -> dict:
    """返回当前登录状态，供前端轮询"""
    valid = is_token_valid()
    data = load_token()
    return {
        "logged_in": valid,
        "in_progress": _login_in_progress,
        "exp": data.get("exp") if data else None,
        "saved_at": data.get("saved_at") if data else None,
    }
