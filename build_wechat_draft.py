"""阶段 B · B3 公众号草稿一键构建（DRAFT ONLY，不发布）。

前置：AppSecret 通过环境变量 WECHAT_APPSECRET 提供（配置文件中缺 secret）。
  set WECHAT_APPSECRET=xxxx
  python build_wechat_draft.py

流程（全部走 curl，规避 managed Python 的 TLS 问题）：
  1. token
  2. cover.jpg -> material/add_material（thumb_media_id + cover_url）
  3. cover.jpg -> media/uploadimg（正文头图 header_url，from=appmsg）
  4. ecosystem_banner.png / recruit_banner.gif -> media/uploadimg
  5. 替换 LDA_公众号文章_B3_开源EDA护城河.html 占位符
  6. draft/add -> 返回 media_id（草稿箱）
"""
import os
import sys
import json
import subprocess

ROOT = os.path.dirname(os.path.abspath(__file__))
# 读 appid + secret（配置文件已含 AppSecret）
_cfg = os.path.join(os.path.expanduser("~"), ".workbuddy", "wechat_credentials.json")
_cfg_data = json.load(open(_cfg, encoding="utf-8"))
APPID = _cfg_data.get("appid")
SECRET = _cfg_data.get("appsecret") or os.environ.get("WECHAT_APPSECRET")
if not SECRET:
    print("ERROR: 请在 ~/.workbuddy/wechat_credentials.json 中填入 AppSecret"); sys.exit(2)

COVER = os.path.join(ROOT, "docs/images/cover_lda_b3.jpg")
ECOSYS = r"C:\Users\Administrator\WorkBuddy\2026-05-29-19-34-45\.workbuddy\assets\ecosystem_banner.png"
RECRUIT = r"C:\Users\Administrator\WorkBuddy\2026-05-29-19-34-45\.workbuddy\assets\recruit_banner.gif"
HTML = os.path.join(ROOT, "LDA_公众号文章_B3_开源EDA护城河.html")


def curl_json(url, data=None, file_field=None, file_path=None):
    cmd = ["curl", "-sS"]
    if file_field and file_path:
        cmd += ["-F", f"{file_field}=@{file_path}"]
    if data:
        cmd += ["--data-binary", data]
    cmd.append(url)
    out = subprocess.run(cmd, capture_output=True, text=True, timeout=60).stdout
    return json.loads(out)


def get_token():
    url = f"https://api.weixin.qq.com/cgi-bin/token?grant_type=client_credential&appid={APPID}&secret={SECRET}"
    r = curl_json(url)
    if "access_token" not in r:
        print("TOKEN FAIL:", r); sys.exit(1)
    return r["access_token"]


def main():
    tok = get_token()
    print("token ok")
    # 2) 永久素材（缩略图）
    r = curl_json(f"https://api.weixin.qq.com/cgi-bin/material/add_material?access_token={tok}&type=image",
                  file_field="media", file_path=COVER)
    cover_media_id = r.get("media_id")
    cover_url = r.get("url")
    print("cover_media_id:", cover_media_id)
    # 3) 正文头图（uploadimg）
    r = curl_json(f"https://api.weixin.qq.com/cgi-bin/media/uploadimg?access_token={tok}",
                  file_field="media", file_path=COVER)
    header_url = r.get("url")
    print("header_url:", header_url)
    # 4) 生态图 + 招募动图
    r = curl_json(f"https://api.weixin.qq.com/cgi-bin/media/uploadimg?access_token={tok}",
                  file_field="media", file_path=ECOSYS)
    eco_url = r.get("url")
    r = curl_json(f"https://api.weixin.qq.com/cgi-bin/media/uploadimg?access_token={tok}",
                  file_field="media", file_path=RECRUIT)
    recruit_url = r.get("url")
    print("eco/recruit urls ok")
    # 5) 替换占位符
    html = open(HTML, encoding="utf-8").read()
    html = (html.replace("{{COVER_URL}}", cover_url or "")
                .replace("{{HEADER_IMG_URL}}", header_url or "")
                .replace("{{ECOSYSTEM_URL}}", eco_url or "")
                .replace("{{RECRUIT_URL}}", recruit_url or ""))
    # 占位符自检（防止漏填）
    for ph in ["{{COVER_URL}}", "{{HEADER_IMG_URL}}", "{{ECOSYSTEM_URL}}", "{{RECRUIT_URL}}"]:
        if ph in html:
            print(f"WARN 未替换占位符: {ph}")
    # 6) 建草稿
    draft = {"articles": [{
        "title": "为什么我们需要一个开源的 Agent-native EDA？——LDA 的定位与护城河",
        "thumb_media_id": cover_media_id,
        "author": "杜玉河",
        "digest": "AI 写内核、确定性裁判验收——LDA 的开源 Agent-native EDA 定位与护城河。",
        "show_cover_pic": 1,
        "content": html,
        "content_source_url": "https://github.com/iduyuhe/LDA",
        "need_open_comment": 0,
        "only_fans_can_comment": 0,
    }]}
    payload = json.dumps(draft, ensure_ascii=False).encode("utf-8")
    cmd = ["curl", "-sS", "-H", "Content-Type: application/json; charset=utf-8",
           "--data-binary", "@-",
           f"https://api.weixin.qq.com/cgi-bin/draft/add?access_token={tok}"]
    p = subprocess.run(cmd, input=payload, capture_output=True, timeout=60)
    res = json.loads(p.stdout.decode("utf-8"))
    print("DRAFT RESULT:", res)
    if "media_id" in res:
        print("✅ 草稿已创建 media_id =", res["media_id"])
        print("请到公众号后台【草稿箱】审核后发布。")


if __name__ == "__main__":
    main()
