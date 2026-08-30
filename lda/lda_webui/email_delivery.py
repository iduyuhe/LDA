"""LDA 创新超市订单交付邮件模块（零外部依赖，仅标准库）。

职责：
- 向客户发送「下载码 / 交付」邮件（SMTP 465 SSL）
- 从收件箱拉取未读订单邮件信封（IMAP 993 SSL），供后续解析

凭据安全（与项目既有 LDA_ADMIN_TOKEN 模式一致）：
- 邮箱地址 / 服务器固定写在代码（非机密）
- 客户端专用密码从环境变量 LDA_STORE_EMAIL_PASS 读取，绝不进仓库 / 不进 git
- 生产环境通过 systemd drop-in 注入该环境变量（见 deploy 流程）
"""
import os
import imaplib
import smtplib
import ssl
from email.message import EmailMessage
from email.parser import BytesParser
from email.policy import default as _default_policy

EMAIL_USER = "duyuhe@shdute.cn"
IMAP_HOST = "imap.exmail.qq.com"
IMAP_PORT = 993
SMTP_HOST = "smtp.exmail.qq.com"
SMTP_PORT = 465


def _ctx() -> ssl.SSLContext:
    return ssl.create_default_context()


def _password() -> str:
    pw = os.environ.get("LDA_STORE_EMAIL_PASS")
    if not pw:
        raise RuntimeError(
            "未设置环境变量 LDA_STORE_EMAIL_PASS（duyuhe@shdute.cn 客户端专用密码）"
        )
    return pw


def send_download_code(recipient: str, item_name: str, code: str,
                       *, sender_name: str = "LDA 创新超市") -> bool:
    """向客户发送下载码交付邮件。成功返回 True，异常向上抛出。"""
    recipient = (recipient or "").strip()
    if not recipient or "@" not in recipient:
        raise ValueError(f"收件人邮箱非法: {recipient!r}")
    msg = EmailMessage()
    msg["From"] = f"{sender_name} <{EMAIL_USER}>"
    msg["To"] = recipient
    msg["Subject"] = f"【LDA 创新超市】您订购的「{item_name}」下载码"
    body = (
        f"尊敬的用户：\n\n"
        f"感谢您通过 LDA 创新超市订购「{item_name}」。\n"
        f"您的专属下载码如下：\n\n"
        f"    {code}\n\n"
        f"请在 LDA 平台「我的订单」中输入该下载码以获取交付内容。\n"
        f"如有疑问，请直接回复本邮件。\n\n"
        f"—— LDA 创新超市 交付中心\n"
    )
    msg.set_content(body, charset="utf-8")
    with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=_ctx(), timeout=30) as s:
        s.login(EMAIL_USER, _password())
        s.send_message(msg)
    return True


def fetch_unread_envelopes(limit: int = 20):
    """拉取收件箱未读邮件信封列表。

    返回 [(uid:bytes, from_addr:str, subject:str, date:str), ...]
    仅读信封（BODY.PEEK），不标记已读、不下载正文，避免误吞订单邮件。
    """
    out = []
    with imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT, ssl_context=_ctx()) as im:
        im.login(EMAIL_USER, _password())
        im.select("INBOX")
        typ, data = im.search(None, "UNSEEN")
        uids = data[0].split() if data and data[0] else []
        for uid in uids[-limit:]:
            typ, d = im.fetch(uid, "(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE)])")
            if not d or d[0] is None:
                continue
            raw = d[0][1]
            if isinstance(raw, bytes):
                head = BytesParser(policy=_default_policy).parsebytes(raw)
                frm = head.get("From", "")
                subj = head.get("Subject", "")
                date = head.get("Date", "")
                out.append((uid, str(frm), str(subj), str(date)))
    return out


def _cli():
    import sys
    args = sys.argv[1:]
    if not args:
        print("用法: email_delivery.py send <收件人> <商品名> <下载码> | inbox")
        return
    cmd = args[0]
    if cmd == "send" and len(args) >= 4:
        ok = send_download_code(args[1], args[2], args[3])
        print("SEND_OK" if ok else "SEND_FAIL")
    elif cmd == "inbox":
        envs = fetch_unread_envelopes()
        print(f"UNREAD={len(envs)}")
        for uid, frm, subj, date in envs:
            print(f"  [{uid.decode()}]\n    From: {frm}\n    Subj: {subj}\n    Date: {date}")
    else:
        print("未知子命令或参数不足")


if __name__ == "__main__":
    _cli()
