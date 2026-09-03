# -*- coding: utf-8 -*-
"""公众号性能篇建草稿（v0.8.44 B2 配套 · DRAFT ONLY）。

凭据走环境变量 WECHAT_APPID/WECHAT_APPSECRET（不落盘）。curl 绕 TLS 坑。
"""
import json, os, subprocess, sys

APPID = os.environ["WECHAT_APPID"]
SECRET = os.environ["WECHAT_APPSECRET"]
COVER = r"D:/agent_LDA/build_wechat_lda_perf/cover_lda_perf.jpg"
ECO   = r"C:/Users/Administrator/WorkBuddy/2026-05-29-19-34-45/.workbuddy/assets/ecosystem_banner.png"
RECR  = r"C:/Users/Administrator/WorkBuddy/2026-05-29-19-34-45/.workbuddy/assets/recruit_banner.gif"
QR    = r"E:/agent_industry/zhiyan/docs/智衍EvolvIQ_体验二维码卡.png"
BODY  = r"D:/agent_LDA/build_wechat_lda_perf/body.html"


def curl(url, form=""):
    cmd = ["curl", "-sS", url]
    if form:
        cmd += ["-F", form]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    return r.stdout


def curl_json(url, form=""):
    out = curl(url, form)
    try:
        return json.loads(out)
    except Exception:
        return {"_raw": out, "_stderr": "non-json"}


def must(d, key, where):
    if key not in d:
        print(f"❌ {where} 无 {key}：", d)
        sys.exit(1)


# 1) token
tok = curl_json(
    f"https://api.weixin.qq.com/cgi-bin/token?grant_type=client_credential&appid={APPID}&secret={SECRET}")
must(tok, "access_token", "token")
T = tok["access_token"]
print("✓ token ok")

# 2) permanent 封面（thumb_media_id）
perm = curl_json(
    f"https://api.weixin.qq.com/cgi-bin/material/add_material?access_token={T}&type=image",
    f"media=@{COVER}")
must(perm, "media_id", "permanent cover")
must(perm, "url", "permanent cover")
thumb_id = perm["media_id"]
print(f"✓ permanent cover media_id={thumb_id}")

# 3) uploadimg 封面（正文头图，?from=appmsg URL）
def uploadimg(path, tag):
    r = curl_json(f"https://api.weixin.qq.com/cgi-bin/media/uploadimg?access_token={T}",
                  f"media=@{path}")
    must(r, "url", f"uploadimg {tag}")
    print(f"✓ uploadimg {tag}")
    return r["url"]


cover_url = uploadimg(COVER, "cover")
eco_url = uploadimg(ECO, "ecosystem")
recr_url = uploadimg(RECR, "recruit")
qr_url = uploadimg(QR, "qr")
print("✓ 4 张正文图全部上传")

# 4) 组装 articles.json
body = open(BODY, encoding="utf-8").read()
for tag, url in [("__COVER_URL__", cover_url), ("__ECO_URL__", eco_url),
                 ("__RECRUIT_URL__", recr_url), ("__QR_URL__", qr_url)]:
    assert tag in body, f"HTML 缺占位符 {tag}"
    body = body.replace(tag, url)
# 头图双保险校验（skill 硬要求：正文必须含 mmbiz.qpic.cn URL 的 <img>）
assert cover_url in body, "正文缺头图 URL"
assert "<img" in body[:1000], "正文前 1000 字符缺 <img> 标签"
assert 'src=""' not in body and "COVER_URL_PLACEHOLDER" not in body and "__COVER_URL__" not in body, "占位符未替换"
print("✓ 头图双保险校验通过（正文含 cover_url + <img> + 无残留占位符）")

article = {
    "title": "32k 器件亚秒签核：开源 EDA 的性能纵深是怎样炼成的",
    "thumb_media_id": thumb_id,
    "author": "杜玉河",
    "digest": "我们把万级器件签核从不可迭代的 16 分钟，压到了亚秒——五轮拔钉子的工程实录",
    "show_cover_pic": 1,
    "content": body,
    "content_source_url": "https://github.com/iduyuhe/LDA",
    "need_open_comment": 0,
    "only_fans_can_comment": 0,
}
print("✓ 头图双保险校验通过（正文含 cover_url + <img> + 无残留占位符）")
draft_path = r"D:/agent_LDA/build_wechat_lda_perf/draft.json"
json.dump({"articles": [article]}, open(draft_path, "w", encoding="utf-8"),
          ensure_ascii=False, indent=2)
print(f"✓ articles.json 写盘 {draft_path}")

# 5) 建草稿
r = subprocess.run(
    ["curl", "-sS",
     "-H", "Content-Type: application/json; charset=utf-8",
     "--data-binary", f"@{draft_path}",
     f"https://api.weixin.qq.com/cgi-bin/draft/add?access_token={T}"],
    capture_output=True, text=True, timeout=60)
try:
    rd = json.loads(r.stdout)
except Exception:
    rd = {"_raw": r.stdout, "_stderr": r.stderr}
print("draft/add 返回:", json.dumps(rd, ensure_ascii=False))
if "media_id" in rd:
    print(f"\n✅ 草稿已创建 media_id={rd['media_id']}")
    print(f"   标题：{article['title']}")
    print(f"   封面：cover_url={cover_url}")
    print(f"   正文头图：{cover_url[:80]}...")
    print("   请到公众号后台【草稿箱】审核（默认未发布）")