import requests
import os
import re
from shuati.core.date_utils import normalize_datetime_text
from shuati.core.config import (
    JIELONG_API_BASE, BASE_HEADERS,
    FAVORITE_LIST_TYPE, PAGE_SIZE, IMAGES_DIR
)
from shuati.core.auth import get_auth_headers


def _headers() -> dict:
    h = dict(BASE_HEADERS)
    h.update(get_auth_headers())
    return h


# ── 收藏列表 ──────────────────────────────────────────────

def fetch_favorites(page: int = 1) -> list[dict]:
    """
    获取收藏的接龙列表。
    返回简化后的列表：[{thread_id, subject, author, date_created}, ...]
    """
    url = f"{JIELONG_API_BASE}/Thread/Threads"
    params = {
        "pageIndex": page,
        "pageSize": PAGE_SIZE,
        "listType": FAVORITE_LIST_TYPE,
    }
    print(f"[API] Fetching favorites: page={page}, params={params}")
    resp = requests.get(url, headers=_headers(), params=params, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    if data is None:
        data = {}
    
    # 兼容 Data 字段直接返回列表的情况
    raw_data = data.get("Data", [])
    if isinstance(raw_data, list):
        items = raw_data
    elif isinstance(raw_data, dict):
        items = raw_data.get("Threads", []) or []
    else:
        items = []
    
    print(f"[API] Response items: {len(items)}")
    result = []
    for item in items:
        result.append({
            "thread_id": item.get("ThreadStrId"),
            "subject": item.get("Subject", ""),
            "author": item.get("Author", ""),
            "date_created": item.get("DateCreated", ""),
        })
    return result


def fetch_all_favorites() -> list[dict]:
    """翻页拉取所有收藏"""
    all_items = []
    page = 1
    while True:
        items = fetch_favorites(page)
        if not items:
            break
        all_items.extend(items)
        if len(items) < PAGE_SIZE:
            break
        page += 1
    print(f"[API] 共获取 {len(all_items)} 条收藏")
    return all_items


# ── 接龙详情 ──────────────────────────────────────────────

def fetch_thread_detail(thread_id: str) -> dict | None:
    """
    获取单个接龙的详情，返回解析后的结构：
    {
        thread_id, subject, date_str, author,
        blocks: [
            {content_type, text, image_url, image_local}
        ]
    }
    """
    url = f"{JIELONG_API_BASE}/CheckIn/Detail"
    params = {"threadId": thread_id}
    print(f"[API] Requesting detail: url={url}, params={params}")
    resp = requests.get(url, headers=_headers(), params=params, timeout=15)
    resp.raise_for_status()
    raw = resp.json()
    print(f"[API] Detail response raw keys: {list(raw.keys())}")
    if "Data" in raw:
        print(f"[API] Detail response Data keys: {list(raw['Data'].keys()) if isinstance(raw['Data'], dict) else 'Not a dict'}")

    # 尝试从 Data 直接获取 Thread，或者从 Data.Thread 获取
    data_obj = raw.get("Data", {})
    if data_obj is None:
         data_obj = {}
         
    if "Thread" in data_obj:
        # 新版接口：Data -> Thread -> ...
        thread = data_obj["Thread"]
    elif "CheckIn" in data_obj:
        # 另一种可能：Data -> CheckIn/Thread 并列
        thread = data_obj.get("Thread", {})
    else:
        # 有可能 Data 本身就是 Thread 对象（视接口版本而定）
        # 暂时假设 Data 就是 Thread 对象，或者它里面没有 Thread 字段
        thread = data_obj
    
    if not thread:
        print("[API] No thread data found")
        return None

    subject = thread.get("Subject", "")
    author = thread.get("Author", "")
    
    date_created = thread.get("DateCreated", "")
    data_modified = thread.get("DataModified", "")
    date_str = normalize_datetime_text(date_created, subject) or normalize_datetime_text(data_modified, subject) or normalize_datetime_text("", subject)

    blocks = []
    for item in thread.get("ThreadBody", []):
        ctype = item.get("ContentType")

        if ctype == 11:  # 文字
            text_obj = item.get("Text", {})
            content = text_obj.get("Content", "").strip()
            # 过滤掉不需要的固定文案
            if content and "请各位同学将当日完成的作业拍照上传" not in content:
                blocks.append({
                    "content_type": 11,
                    "text": content,
                    "image_url": None,
                    "image_local": None,
                })

        elif ctype == 4:  # 图片
            img_obj = item.get("Image", {})
            # 优先用无水印的原始 URL（去掉 imageMogr 参数）
            url_raw = img_obj.get("RelativePath", "")
            url_full = img_obj.get("Url", "")
            # 取原始 URL（不带压缩参数）
            image_url = _clean_image_url(url_full)
            if image_url:
                blocks.append({
                    "content_type": 4,
                    "text": None,
                    "image_url": image_url,
                    "image_local": None,
                })

    return {
        "thread_id": thread_id,
        "subject": subject,
        "date_str": date_str,
        "author": author,
        "blocks": blocks,
    }


def _clean_image_url(url: str) -> str:
    """去掉腾讯云 CDN 的图片处理参数，保留原图 URL"""
    if not url:
        return url
    # 去掉 ? 之后的压缩参数，但保留域名和路径
    return url.split("?")[0]


def _parse_date(subject: str, fallback: str) -> str:
    """
    从标题中提取日期，例如 '20260312小六打卡' → '2026-03-12'
    失败则用 DataModified 字段
    """
    m = re.search(r"(\d{4})(\d{2})(\d{2})", subject)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    return fallback or ""


# ── 图片下载 ──────────────────────────────────────────────

def download_image(image_url: str, thread_id: str) -> str | None:
    """
    下载图片到本地，返回本地路径。
    文件名：{thread_id}_{url末尾hash}.jpg
    """
    try:
        os.makedirs(IMAGES_DIR, exist_ok=True)
        # 从 URL 中提取文件名
        filename = image_url.split("/")[-1]
        if not filename.endswith((".jpg", ".jpeg", ".png")):
            filename += ".jpg"
        local_path = os.path.join(IMAGES_DIR, f"{thread_id}_{filename}")

        if os.path.exists(local_path):
            return local_path  # 已下载，跳过

        resp = requests.get(image_url, timeout=30, stream=True)
        resp.raise_for_status()
        with open(local_path, "wb") as f:
            for chunk in resp.iter_content(8192):
                f.write(chunk)
        print(f"[Download] {filename}")
        return local_path
    except Exception as e:
        print(f"[Download] 图片下载失败 {image_url}: {e}")
        return None
