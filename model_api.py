import json
import re
import uuid
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener


LOOPBACK = ('localhost', '127.0.0.1', '::1')


class ModelError(Exception):
    pass


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def api_url(base, route):
    try:
        parts = urlsplit(base.strip())
        host = parts.hostname
        _ = parts.port
    except ValueError as exc:
        raise ModelError('Base URL 格式错误。') from exc
    if not host or parts.username or parts.password or parts.query or parts.fragment:
        raise ModelError('请填写服务商的 Base URL，例如 https://api.openai.com/v1。')
    if parts.scheme != 'https':
        if parts.scheme != 'http' or host not in LOOPBACK:
            raise ModelError('远程服务需要 HTTPS。本机服务可以使用 HTTP。')
    return parts.geturl().rstrip('/') + '/' + route


def post_json(url, key, body, content_type):
    headers = {'Content-Type': content_type, 'Accept': 'application/json'}
    if key:
        headers['Authorization'] = 'Bearer ' + key
    request = Request(url, data=body, headers=headers, method='POST')
    opener = (build_opener(NoRedirect(), ProxyHandler({}))
              if urlsplit(url).hostname in LOOPBACK else build_opener(NoRedirect()))
    try:
        with opener.open(request, timeout=45) as response:
            return json.loads(response.read(2_000_001))
    except HTTPError as exc:
        with exc:
            tips = {
                400: '请核对模型 ID 和接口兼容性。',
                401: '请核对 API Key。',
                403: '请检查 API Key 是否有该模型权限。',
                404: '请核对 Base URL 和模型 ID。',
                429: '请检查请求频率、额度或账户余额。',
            }
            raise ModelError(f'服务返回 HTTP {exc.code}。{tips.get(exc.code, "请检查服务状态和接口设置。")}') from None
    except (URLError, TimeoutError, OSError) as exc:
        raise ModelError('连接失败或超时，请检查网络和服务地址。') from exc
    except (UnicodeError, ValueError) as exc:
        raise ModelError('服务返回了无法解析的数据。') from exc


def chat(base, key, model, messages):
    payload = json.dumps({'model': model, 'messages': messages, 'stream': False}, ensure_ascii=False)
    data = post_json(api_url(base, 'chat/completions'), key, payload.encode('utf-8'), 'application/json')
    try:
        reply = data['choices'][0]['message']['content']
        if isinstance(reply, str) and reply.strip():
            return reply.strip()[:10000]
    except (KeyError, IndexError, TypeError):
        pass
    raise ModelError('服务返回了空回复或不兼容的回复格式。')


def transcribe(base, key, model, wav_data):
    boundary = uuid.uuid4().hex
    model_part = f'--{boundary}\r\nContent-Disposition: form-data; name="model"\r\n\r\n{model}\r\n'
    file_part = (
        f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="recording.wav"\r\n'
        'Content-Type: audio/wav\r\n\r\n'
    )
    payload = model_part.encode() + file_part.encode() + wav_data + f'\r\n--{boundary}--\r\n'.encode()
    data = post_json(api_url(base, 'audio/transcriptions'), key, payload, 'multipart/form-data; boundary=' + boundary)
    reply = data.get('text') if isinstance(data, dict) else None
    if not isinstance(reply, str) or not reply.strip():
        raise ModelError('没有识别到文字，可以再录一次。')
    return reply.strip()[:2000]


def demo_reply(message):
    if re.search(r'你好|在吗|嗨|hello|^hi\b', message, re.IGNORECASE):
        return '嘀嘀，曳尔沐在线！你的信号满格。'
    if re.search(r'晚安|睡觉|困了', message):
        return '那我先把铃声调低。晚安，明天再接通！'
    return '收到，我在听。这是离线演示。填好模型设置后，就可以和我自由聊天啦。'
